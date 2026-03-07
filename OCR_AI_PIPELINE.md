# OCR & AI Descriptive Analysis Pipeline

Purpose: Describe a practical, flexible pipeline EduPulse will use to parse diverse Ghanaian report-card formats (scanned or photographed), normalize them to structured student time-series, and generate AI-driven descriptive narratives and trend analyses.

## 1. High-level Flow

1. Image ingestion (mobile/photo upload, scanned PDF)
2. Preprocessing (deskew, color normalization, denoise)
3. Layout detection & template matching
4. OCR (text extraction) with confidence scores
5. Field extraction & parsing (grades, subject names, averages, ranks, remarks)
6. Time-series alignment (map to student record & term)
7. AI analysis & narrative generation (trend detection, anomaly explanation)
8. Human-in-the-loop review for low-confidence outputs
9. Store structured result in `student_reports` table and attach audit log

## 2. Robustness & Flexibility Strategies

- Template Library: Maintain a small library of common Ghanaian report-card templates (schools using GradMan/other systems). Start with 10 common layouts and add new templates via admin UI.
- Heuristic Layout Parser: Use object-detection (lightweight ML model or rule-based table detection) to find tabular regions, headers, remarks area.
- OCR Engine Choice: Use `pytesseract` as baseline, optionally swap to cloud OCR (Google Vision/Azure) for higher accuracy on low-quality photos.
- Fuzzy Subject Mapping: Map OCRed subject labels to canonical subject names via fuzzy matching (Levenshtein) and a configurable alias table (e.g., "Ghanaian Language" → "Ghanaian Language").
- Numeric Validation: Validate extracted marks are within 0-100 and sanity-check averages vs. subject marks (e.g., term average should be within 5-10 points of subject mean).
- Confidence Scores: Keep token-level and field-level confidence; if below threshold, mark record for manual review.
- Privacy & Consent: Require explicit consent before processing parent-submitted images; store minimal PII and log access.

## 3. Data Model (example)

`student_reports` table (simplified):
- id
- school_id
- student_id (nullable until matched)
- term
- year
- raw_text
- parsed_subjects: JSON [{subject, mark, grade, remark, confidence}]
- term_average
- class_average
- overall_performance
- parse_confidence
- reviewer_id (nullable)
- created_at

## 4. AI Analysis & Narrative Generation

- Input: parsed_subjects time-series (this term and previous terms if available) + payments timeline + attendance metrics
- Models:
  - Trend Detector: simple statistical slope + seasonal smoothing (exponential smoothing) to detect improving/declining subjects
  - Anomaly Detector: z-score on recent marks vs. personal baseline and class baseline
  - Risk Scorer: existing "Sack-Risk" model consumes attendance, payment delinquency, trend scores, and outputs 0-100 risk
  - Narrative Generator: small controlled prompt to a GenAI model (or rule-based templates) that produces short descriptive statements and recommended interventions
- Human-in-the-loop: if `parse_confidence < 0.85` or `risk_score > 70`, route to reviewer for approval before sending to parent/proprietor

## 5. Example Anonymized Narrative (from the attached report card image)

Note: the attached image was used only to illustrate a generated narrative; no name or ID is exposed here.

Summary:
- Term average: 81.6% (school average: ~81.1%), Overall performance: 72.5%.
- Strengths: Consistently strong performance in Science, Mathematics, and Computing—these subjects are above the student's average and show positive trend signals.
- Opportunities: English and History are slightly below the student's term average and exhibit flat or mild decline over the last two recorded terms.
- Recommendation: Provide focused reading practice for English comprehension (30 mins/day), maintain current study routines for Science/Maths, and schedule a short intervention session with the class teacher to address gaps in History vocabulary.
- Confidence: 0.88 (parse confidence). Suggested manual review items: confirm subject name mappings for any non-standard labels; verify attendance/payment records for correlation checks.

Short Action Snippets (for teacher dashboard):
- "Assign 2 targeted English exercises this week (reading comprehension)."
- "Schedule 1-on-1 for History vocabulary next Wednesday."
- "Monitor Math performance; student remains strong — praise in weekly report."

## 6. Implementation Roadmap (MVP)

Week 0-2:
- Implement preprocessing + pytesseract extraction
- Build fuzzy subject mapper and basic table parser
- Store parsed outputs and confidence

Week 3-5:
- Implement trend detector and simple narrative templates
- Add human review UI for low-confidence parses

Week 6-8:
- Integrate risk score and payments/attendance correlation
- Run pilot on 50 historical report cards (CCA Ofankor + seed data)

## 7. Metrics & QA

- OCR Field Accuracy (goal): 95% token-level
- Field-level parse confidence threshold: 0.85
- Narrative acceptance rate by reviewer: >90% after Week 6
- Time-to-parse per image: <3s on moderate server

## 8. Next Steps I can take now (pick one)
1. Run a live OCR + parse on the attached image and produce the parsed JSON + narrative (requires running code here).  
2. Produce a minimal runnable prototype (`ocr_demo.py`, `requirements.txt`, README) you can run locally to parse images and generate narratives.  
3. Add unit tests and CI hooks for the parsing pipeline.

If you want (1), I'll run a local prototype here and show the parsed JSON and anonymized narrative. If you prefer to run locally, I can produce the runnable prototype for download.
