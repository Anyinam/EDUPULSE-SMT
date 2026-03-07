import pytest

from backend.report_card_parser import parse_ocr_text


def test_parse_ocr_text_minimal():
    sample = """
    STUDENT'S TERMINAL REPORT
    Student ID: 20220001 - LAMPTEY NII LARYEA
    SUBJECTS
    ENGLISH LANGUAGE 37.20 75.30
    SCIENCE 38.00 82.00
    MATHEMATICS 38.40 75.60
    AVERAGE MARK : 81.56
    OVERALL PERFORMANCE : 72.50
    """
    parsed = parse_ocr_text(sample)
    assert parsed["term_average"] == 81.56
    assert parsed["overall_performance"] == 72.50
    subjects = {s["subject"] for s in parsed["subjects"]}
    assert "English Language" in subjects
    assert "Science" in subjects


def test_parse_subject_line_structured():
    sample = """
    ENGLISH LANGUAGE 37.20 38.10 75.30 B 8 VERY GOOD
    """
    parsed = parse_ocr_text(sample)
    assert parsed["subjects"]
    subj = parsed["subjects"][0]
    assert subj["subject"] == "English Language"
    assert subj["class_score"] == 37.20
    assert subj["exam_score"] == 38.10
    assert subj["total_score"] == 75.30
    assert subj["grade"] == "B"
