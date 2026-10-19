"""A's photo-quality check, following the shared contract in docs/contracts.md."""

from __future__ import annotations

import os
from functools import lru_cache
from threading import Lock
from typing import Literal, TypedDict

import cv2
import numpy as np


QualityStatus = Literal["accepted", "retake", "manual_review"]
ReasonCode = Literal[
    "blur",
    "dark",
    "overexposed",
    "too_near",
    "too_far",
    "cropped",
    "no_vehicle",
    "wrong_view",
    "plate_not_found",
    "uncertain",
]


class QualityResult(TypedDict):
    status: QualityStatus
    reason_code: ReasonCode | None
    message: str


EXTERIOR_VIEWS = frozenset({"front_left", "front_right", "rear_left", "rear_right"})
INTERIOR_VIEWS = frozenset({"interior_front", "interior_rear"})
SUPPORTED_VIEWS = EXTERIOR_VIEWS | INTERIOR_VIEWS

# COCO class IDs used by YOLO11n: car, motorcycle, bus, and truck.
VEHICLE_CLASS_IDS = (2, 3, 5, 7)
_MODEL_LOCK = Lock()
VIEW_CLASSES = {
    "front_left",
    "front_right",
    "rear_left",
    "rear_right",
    "interior_front",
    "interior_rear",
}


def _retake(reason_code: ReasonCode, message: str) -> QualityResult:
    return {"status": "retake", "reason_code": reason_code, "message": message}


def _manual_review(message: str) -> QualityResult:
    return {"status": "manual_review", "reason_code": "uncertain", "message": message}


@lru_cache(maxsize=2)
def _load_vehicle_model(model_path: str):
    """Load weights lazily; do not download or initialize a model at import time."""
    from ultralytics import YOLO

    return YOLO(model_path)


@lru_cache(maxsize=2)
def _load_view_model(model_path: str):
    """Load a six-class YOLO classification model lazily."""
    from ultralytics import YOLO

    return YOLO(model_path)


@lru_cache(maxsize=2)
def _load_plate_model(model_path: str):
    """Load a license-plate detection model lazily."""
    from ultralytics import YOLO

    return YOLO(model_path)


def _view_classification(photo_path: str) -> tuple[str, float]:
    model_path = os.getenv("ICATCH_VIEW_MODEL")
    if not model_path:
        raise RuntimeError("ICATCH_VIEW_MODEL is not configured")
    model = _load_view_model(model_path)
    with _MODEL_LOCK:
        predictions = model.predict(source=photo_path, verbose=False)
    if not predictions or predictions[0].probs is None:
        raise RuntimeError("view model did not return classification probabilities")
    probabilities = predictions[0].probs
    index = int(probabilities.top1)
    names = predictions[0].names
    label = str(names[index]).strip().lower()
    if label not in VIEW_CLASSES:
        raise RuntimeError(f"unexpected view model class: {label!r}")
    return label, float(probabilities.top1conf.item())


def _license_plate_detected(photo_path: str) -> bool:
    model_path = os.getenv("ICATCH_PLATE_MODEL")
    if not model_path:
        raise RuntimeError("ICATCH_PLATE_MODEL is not configured")
    model = _load_plate_model(model_path)
    confidence_threshold = float(os.getenv("ICATCH_PLATE_CONFIDENCE", "0.30"))
    accepted_names = {
        item.strip().lower()
        for item in os.getenv(
            "ICATCH_PLATE_CLASS_NAMES",
            "license_plate,license plate,plate,number_plate,number plate",
        ).split(",")
        if item.strip()
    }
    with _MODEL_LOCK:
        predictions = model.predict(source=photo_path, conf=confidence_threshold, verbose=False)
    if not predictions or predictions[0].boxes is None:
        return False
    names = predictions[0].names
    for box in predictions[0].boxes:
        class_id = int(box.cls[0].item())
        class_name = str(names[class_id]).strip().lower()
        if class_name in accepted_names:
            return True
    return False


def _vehicle_detections(photo_path: str):
    model_path = os.getenv("ICATCH_YOLO_MODEL", "yolo11n.pt")
    model = _load_vehicle_model(model_path)
    # Keep inference serialized while D calls this function from concurrent requests.
    with _MODEL_LOCK:
        predictions = model.predict(
            source=photo_path,
            classes=list(VEHICLE_CLASS_IDS),
            conf=float(os.getenv("ICATCH_YOLO_CONFIDENCE", "0.30")),
            verbose=False,
        )
    if not predictions:
        return []
    boxes = predictions[0].boxes
    if boxes is None:
        return []
    return [
        (
            float(box.conf[0].item()),
            *(float(value) for value in box.xyxy[0].cpu().tolist()),
        )
        for box in boxes
    ]


def check_quality(photo_path: str, expected_view: str) -> QualityResult:
    """Check one locally staged image and return a structured result.

    ``accepted`` means the image passed the quality, view-classification, and
    (for exterior views) license-plate checks. It does not determine damage or
    cleanliness.
    D owns persistence and review workflow; this function does not write files.
    """
    if expected_view not in SUPPORTED_VIEWS:
        raise ValueError(f"Unsupported view code: {expected_view!r}")

    image = cv2.imread(os.fspath(photo_path), cv2.IMREAD_COLOR)
    if image is None:
        return _retake("uncertain", "無法讀取照片，請重新拍攝。")

    height, width = image.shape[:2]
    if width < 320 or height < 240:
        return _retake("too_far", "照片尺寸太小，請靠近一些並重新拍攝。")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < float(os.getenv("ICATCH_BLUR_THRESHOLD", "75")):
        return _retake("blur", "照片模糊，請拿穩手機、等畫面對焦後重拍。")

    brightness = float(np.mean(gray))
    dark_ratio = float(np.mean(gray < 35))
    if brightness < float(os.getenv("ICATCH_DARK_MEAN_THRESHOLD", "48")) or dark_ratio > float(
        os.getenv("ICATCH_DARK_PIXEL_RATIO_THRESHOLD", "0.55")
    ):
        return _retake("dark", "照片太暗，請移到光線充足處重新拍攝。")

    bright_ratio = float(np.mean(gray > 245))
    if brightness > float(os.getenv("ICATCH_BRIGHT_MEAN_THRESHOLD", "218")) or bright_ratio > float(
        os.getenv("ICATCH_BRIGHT_PIXEL_RATIO_THRESHOLD", "0.45")
    ):
        return _retake("overexposed", "照片過亮，請避開強光或逆光重新拍攝。")

    try:
        actual_view, view_confidence = _view_classification(os.fspath(photo_path))
    except Exception:
        return _manual_review("目前無法確認照片視角，請稍後重試或交由人工覆核。")

    if view_confidence < float(os.getenv("ICATCH_VIEW_CONFIDENCE", "0.55")):
        return _manual_review("無法確定照片視角，請依畫面指示重新取景；仍無法確認時交由人工覆核。")
    if actual_view != expected_view:
        return _retake("wrong_view", f"目前照片判定為「{actual_view}」，但需要「{expected_view}」，請依指示重新拍攝。")

    # Interior views are angle-classified but do not require a license-plate detection.
    if expected_view in INTERIOR_VIEWS:
        return {"status": "accepted", "reason_code": None, "message": "視角、清晰度與曝光合格。"}

    try:
        if not _license_plate_detected(os.fspath(photo_path)):
            return _retake("plate_not_found", "未清楚偵測到車牌，請調整角度與距離後重新拍攝。")
    except Exception:
        return _manual_review("目前無法確認車牌，請稍後重試或交由人工覆核。")

    try:
        detections = _vehicle_detections(os.fspath(photo_path))
    except Exception:
        # A missing weight, model timeout, or inference error must never become acceptance.
        return _manual_review("車輛辨識目前無法可靠完成，請補拍；仍無法確認時交由人工覆核。")

    if not detections:
        return _retake("no_vehicle", "沒有清楚拍到車輛，請確認目前指定角度後重拍。")

    # Choose the most prominent detected vehicle in the frame.
    confidence, x1, y1, x2, y2 = max(
        detections,
        key=lambda box: max(0.0, box[3] - box[1]) * max(0.0, box[4] - box[2]),
    )
    del confidence  # Confidence is used by the detector threshold, not the contract result.
    box_width = max(0.0, x2 - x1)
    box_height = max(0.0, y2 - y1)
    area_ratio = (box_width * box_height) / (width * height)
    width_ratio = box_width / width
    height_ratio = box_height / height

    edge_margin = float(os.getenv("ICATCH_EDGE_MARGIN_RATIO", "0.012"))
    if (
        x1 / width <= edge_margin
        or y1 / height <= edge_margin
        or (width - x2) / width <= edge_margin
        or (height - y2) / height <= edge_margin
    ):
        return _retake("cropped", "車身可能被畫面邊緣裁切，請退後並重新取景。")

    if area_ratio < float(os.getenv("ICATCH_MIN_VEHICLE_AREA_RATIO", "0.10")) or width_ratio < 0.28 or height_ratio < 0.20:
        return _retake("too_far", "車輛太遠或太小，請靠近一些並讓車身完整入鏡。")

    if area_ratio > float(os.getenv("ICATCH_MAX_VEHICLE_AREA_RATIO", "0.92")):
        return _retake("too_near", "車輛太靠近，請退後一些並保留完整車身。")

    return {"status": "accepted", "reason_code": None, "message": "照片品質合格。"}
