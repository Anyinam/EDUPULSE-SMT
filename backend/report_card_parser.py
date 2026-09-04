import re
from io import BytesIO

SUBJECT_ALIASES = [
    "ENGLISH",
    "ENGLISH LANGUAGE",
    "SCIENCE",
    "MATHEMATICS",
    "MATHS",
    "HISTORY",
    "RELIGIOUS",
    "RELIGIOUS AND MORAL EDUCATION",
    "COMPUTING",
    "CREATIVE ARTS",
    "GHANAIAN LANGUAGE",
    "GHANAIAN LANGUAGE AND CULTURE",
    "FRENCH",
]

TEMPLATE_MAPPINGS = {
    "gradman_v1": {
        "header_tokens": [
            "STUDENT'S TERMINAL REPORT",
            "SAPPHIRE SUMMARY PERFORMANCE STATISTICS",
        ],
        "subject_area_hint": "SUBJECTS",
    },
}

SUBJECT_CANONICAL = {
    "MATHS": "Mathematics",
    "MATHEMATICS": "Mathematics",
    "ENGLISH LANGUAGE": "English Language",
    "ENGLISH": "English Language",
    "SCIENCE": "Science",
    "HISTORY": "History",
    "RELIGIOUS AND MORAL EDUCATION": "Religious and Moral Education",
    "RELIGIOUS": "Religious and Moral Education",
    "COMPUTING": "Computing",
    "CREATIVE ARTS": "Creative Arts and Design",
    "GHANAIAN LANGUAGE": "Ghanaian Language",
    "GHANAIAN LANGUAGE AND CULTURE": "Ghanaian Language",
    "FRENCH": "French",
}


def _safe_imports():
    try:
        import numpy as np
        from PIL import Image, ImageFilter, ImageOps

        try:
            import cv2
        except Exception:
            cv2 = None
        import pytesseract

        return Image, ImageFilter, ImageOps, pytesseract, np, cv2
    except Exception:
        return None, None, None, None, None, None


def preprocess_image_pil(img):
    # basic preprocessing: convert to grayscale, increase contrast, denoise
    try:
        from PIL import ImageFilter, ImageOps

        img = img.convert("L")
        img = ImageOps.invert(img)
        img = img.resize((int(img.width * 1.2), int(img.height * 1.2)))
        img = img.filter(ImageFilter.MedianFilter(size=3))
    except (ImportError, AttributeError, OSError, ValueError):
        return img
    return img


def _apply_crop(img, template_config, cv2):
    if not template_config or not cv2:
        return img

    crop = template_config.get("crop_box")
    if not crop or len(crop) != 4:
        return img

    x, y, w, h = crop
    if all(isinstance(v, float) and 0 < v <= 1 for v in crop):
        height, width = img.shape[:2]
        x = int(x * width)
        y = int(y * height)
        w = int(w * width)
        h = int(h * height)

    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, int(w))
    h = max(1, int(h))
    return img[y : y + h, x : x + w]


def _deskew_image(gray, cv2):
    coords = cv2.findNonZero(255 - gray)
    if coords is None:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _find_table_region(gray, cv2):
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    for cnt in contours[:5]:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 200 or h < 200:
            continue
        aspect = w / float(h)
        if 0.6 <= aspect <= 2.5:
            return (x, y, w, h)
    return None


def ocr_image_bytes(image_bytes, template_config=None):
    Image, ImageFilter, ImageOps, pytesseract, np, cv2 = _safe_imports()
    if not pytesseract:
        raise RuntimeError(
            "pytesseract and Pillow required for OCR. Install pytesseract pillow."
        )

    if cv2 is not None:
        img_arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        img = _apply_crop(img, template_config, cv2)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = _deskew_image(gray, cv2)
        table_box = _find_table_region(gray, cv2)
        if table_box:
            x, y, w, h = table_box
            gray = gray[y : y + h, x : x + w]
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
        )
        text = pytesseract.image_to_string(thresh, config="--psm 6")
    else:
        img = Image.open(BytesIO(image_bytes))
        img = preprocess_image_pil(img)
        text = pytesseract.image_to_string(img, config="--psm 6")
    return text


def parse_ocr_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    parsed = {
        "student_code": None,
        "student_name": None,
        "term": None,
        "year": None,
        "subjects": [],
        "term_average": None,
        "overall_performance": None,
        "raw_text": text,
        "parse_confidence": 0.9,
    }

    # Example subject line: ENGLISH LANGUAGE 37.20 38.10 75.30 B 8 VERY GOOD
    subject_regex = re.compile(
        r"^([A-Z\s&]+?)\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+([A-F])\s+(\d+)\s+(.*)$"
    )

    for ln in lines[:30]:
        m = re.search(r"(20\d{5,})", ln)
        if m:
            parsed["student_code"] = m.group(1)
            break

    for ln in lines[:40]:
        if "TERM" in ln.upper():
            parsed["term"] = ln.strip()
        ym = re.search(r"(20\d{2})-(20\d{2})", ln)
        if ym:
            parsed["year"] = f"{ym.group(1)}/{ym.group(2)}"

    for ln in lines:
        up = ln.upper()
        match = subject_regex.match(up)
        if match:
            subj_raw = match.group(1).strip()
            canon = SUBJECT_CANONICAL.get(subj_raw, subj_raw.title())
            parsed["subjects"].append(
                {
                    "subject": canon,
                    "class_score": float(match.group(2)),
                    "exam_score": float(match.group(3)),
                    "total_score": float(match.group(4)),
                    "grade": match.group(5),
                    "position": int(match.group(6)),
                    "remark": match.group(7).strip(),
                    "raw_line": ln,
                }
            )
            continue

        for subj in SUBJECT_ALIASES:
            if subj in up:
                canon = SUBJECT_CANONICAL.get(subj, subj.title())
                nums = re.findall(r"\d{1,3}(?:\.\d+)?", ln)
                mark = None
                if nums:
                    for n in nums:
                        try:
                            val = float(n)
                            if 0 <= val <= 100:
                                mark = val
                                break
                        except (TypeError, ValueError):
                            continue
                parsed["subjects"].append(
                    {"subject": canon, "mark": mark, "raw_line": ln}
                )
                break

    for ln in lines:
        if "AVERAGE MARK" in ln.upper() or "AVERAGE MARK :" in ln.upper():
            m = re.search(r"(\d{1,3}\.\d{1,2})", ln)
            if m:
                parsed["term_average"] = float(m.group(1))
        if "OVERALL PERFORMANCE" in ln.upper():
            m = re.search(r"(\d{1,3}\.\d{1,2})", ln)
            if m:
                parsed["overall_performance"] = float(m.group(1))

    return parsed


def parse_report_card_image_bytes(
    image_bytes=None, ocr_text=None, template_config=None
):
    """Main helper: accepts raw image bytes or OCR text and returns parsed JSON."""
    if ocr_text:
        return parse_ocr_text(ocr_text)
    if not image_bytes:
        raise RuntimeError("image_bytes required if ocr_text not provided")
    text = ocr_image_bytes(image_bytes, template_config=template_config)
    return parse_ocr_text(text)
