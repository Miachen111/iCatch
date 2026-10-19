# 後端模組（A／B／C 本地判讀；D 負責整合）

目前有 A 的同步品質判讀函式 `app/services/quality.py`；FastAPI、資料模型和流程仍待 D 建立。拍照介面可在擷取照片後呼叫 D 的 API，D 再同步呼叫 A 並回傳 `accepted`、`retake` 或 `manual_review` 結果。A 的函式只收本地暫存照片路徑，不寫資料庫、不上傳 Object Storage，交由 D 負責保存與流程控制。

## A 品質判讀

從專案根目錄安裝 A 的依賴：

```sh
python3 -m pip install -r backend/requirements-a.txt
```

用一張有權使用的本機照片執行可重現範例：

```sh
python3 -m backend.app.services.quality_example /path/to/authorized-photo.jpg --view front_left
```

六個 `view` 代碼固定為 `front_left`、`front_right`、`rear_left`、`rear_right`、`interior_front`、`interior_rear`。每張照片都會先做清晰度和曝光檢查，再由六分類模型確認實際視角；四個車外視角還要偵測車牌和車輛主體。前／後車內照不要求車牌。

六視角分類和車牌偵測需各自訓練或取得相容的 YOLO 權重，目前專案沒有這些權重。設定 `ICATCH_VIEW_MODEL` 和 `ICATCH_PLATE_MODEL` 後才會執行對應檢查；缺少權重、模型錯誤或信心不足時回傳 `manual_review`，不會誤當通過。六視角模型的類別名稱須與六個固定 `view` 代碼完全一致。車牌模型類別名稱預設接受 `license_plate`、`license plate`、`plate`、`number_plate`、`number plate`，可用 `ICATCH_PLATE_CLASS_NAMES` 覆寫。

外車身車輛主體檢查使用 YOLO11n 權重；首次執行預設會嘗試取得 `yolo11n.pt`。權重不提交 Git，可用 `ICATCH_YOLO_MODEL` 指向本機合法取得的模型檔。

起始門檻可用環境變數調整：`ICATCH_BLUR_THRESHOLD`、`ICATCH_DARK_MEAN_THRESHOLD`、`ICATCH_DARK_PIXEL_RATIO_THRESHOLD`、`ICATCH_BRIGHT_MEAN_THRESHOLD`、`ICATCH_BRIGHT_PIXEL_RATIO_THRESHOLD`、`ICATCH_MIN_VEHICLE_AREA_RATIO`、`ICATCH_MAX_VEHICLE_AREA_RATIO`、`ICATCH_EDGE_MARGIN_RATIO`、`ICATCH_YOLO_CONFIDENCE`、`ICATCH_VIEW_CONFIDENCE`、`ICATCH_PLATE_CONFIDENCE`。門檻為原型值，需以授權校準照片調整。

回傳結構和原因代碼見 `../docs/contracts.md` 與 `../docs/examples/quality_*.json`。接受、退件或人工覆核均為結構化結果；品質函式本身不保存影像。
