"""Run A's quality check against one locally available, authorized photo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.services.quality import SUPPORTED_VIEWS, check_quality


def main() -> None:
    parser = argparse.ArgumentParser(description="Run iCatch A's photo-quality check")
    parser.add_argument("photo_path", type=Path, help="Local photo path; no upload or persistence is performed")
    parser.add_argument("--view", required=True, choices=sorted(SUPPORTED_VIEWS))
    args = parser.parse_args()
    if not args.photo_path.is_file():
        parser.error(f"photo does not exist or is not a file: {args.photo_path}")
    print(json.dumps(check_quality(str(args.photo_path), args.view), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
