#!/usr/bin/env python3
"""Simple demo to run the report-card parser locally.

Usage:
  python ocr_demo.py path/to/report.jpg

The script prints parsed JSON and a short anonymized narrative if a student
match is found in the local development DB (it will not connect by default).
"""

import json
import sys
from pathlib import Path

from backend.report_card_parser import parse_report_card_image_bytes


def main():
    if len(sys.argv) < 2:
        print("Usage: python ocr_demo.py path/to/report.jpg")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print("File not found:", path)
        sys.exit(1)

    data = path.read_bytes()
    try:
        parsed = parse_report_card_image_bytes(data)
    except RuntimeError as e:
        print("OCR dependency error:", e)
        print(
            "Install requirements: pip install -r requirements-ocr.txt and system tesseract binary"
        )
        sys.exit(2)

    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    main()
