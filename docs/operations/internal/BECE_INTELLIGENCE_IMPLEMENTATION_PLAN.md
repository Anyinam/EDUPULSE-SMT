# EduPulse SMT BECE Intelligence Implementation Plan

Effective Date: April 29, 2026

## Purpose

This document converts the BECE discussion into a practical implementation path for EduPulse SMT.

The core product idea is to move EduPulse beyond operations-only school management into school-level academic intelligence by helping schools import, analyze, and act on their own external examination history.

## What Exists Now

The following groundwork is already in place in the product or repository:

1. School registration now records explicit school-side data authority and legacy or exam-notice acknowledgements.
2. Parent admissions now require direct guardian consent confirmation before submission.
3. School settings now include a stored compliance workflow for legacy student migration and WAEC or BECE processing readiness.
4. Privacy and terms documentation now explicitly covers school-controlled examination data and school-side consent responsibility.

This means the legal and workflow foundation has started, but the BECE intelligence product itself is not yet implemented.

## The Product Opportunity

Schools in Ghana often receive result lists or school-specific performance documents but still analyze them manually in PDF or spreadsheet form.

EduPulse SMT can convert that manual process into:

1. structured result import,
2. subject-level performance dashboards,
3. multi-year trend tracking,
4. cohort and gender split analysis,
5. alerts for declining performance, and
6. leadership reporting for proprietors and headmasters.

## Delivery Phases

## Phase 1: Manual Result Import MVP

Goal:
Allow a school to upload its WAEC or BECE result list and convert it into structured records inside EduPulse SMT.

Suggested scope:

1. Add a secure proprietor or headmaster-only upload screen.
2. Accept PDF, CSV, or spreadsheet uploads.
3. Extract candidate data into a normalized per-student and per-subject structure.
4. Save each import as a school-scoped exam batch.
5. Show a review screen before finalizing the import.

Suggested data model additions:

1. Exam batch record
2. Exam candidate result record
3. Per-subject result record
4. Import audit trail
5. Consent or notice evidence link to school compliance settings

## Phase 2: School Analytics Dashboard

Goal:
Convert imported result history into school performance intelligence.

Suggested outputs:

1. Five-year subject trend lines
2. School-wide pass-rate trend summary
3. Gender split comparison by subject
4. Top-improvement and highest-risk subjects
5. Cohort comparison by year
6. Headmaster summary card for performance decline alerts

Suggested first charts:

1. Mathematics performance trend over five years
2. Heat map of subject weakness by exam year
3. Gender comparison in ICT, Mathematics, English, and Science
4. Average score by subject and year

## Phase 3: Internal Benchmarking Layer

Goal:
Help a school understand whether it is improving against public reference points.

Suggested scope:

1. Compare school trends against public national or regional aggregate statistics where available.
2. Show internal trend direction even when cross-school ranking is unavailable.
3. Keep identifiable third-party school data out of the system unless lawfully sourced and contractually approved.

Important rule:

EduPulse SMT should not fabricate cross-school league-table positions if the source data does not legally exist.

## Phase 4: WAEC Partnership Path

Goal:
Explore a formal data-integration relationship rather than relying only on manual school uploads.

Possible pitch areas:

1. Secure intake of school-based continuous-assessment marks
2. Cleaner validation and submission workflow for school-generated exam support data
3. Structured school-side result import instead of ad hoc spreadsheets
4. Audit-ready digital submission logs

This phase should start only after the manual-import MVP proves real school demand.

## Recommended Analytics Logic

The first analytics engine does not need AI.

It can start with rule-based calculations such as:

1. year-over-year average score change,
2. pass-rate movement by subject,
3. female vs male performance difference by subject,
4. repeated underperformance thresholds,
5. trend deterioration warnings for three consecutive years, and
6. subject volatility scoring.

AI can be layered later for narrative summaries such as:

1. "Science performance has declined for three consecutive years."
2. "Girls are outperforming boys in ICT, but not in Mathematics."
3. "English remains stable while Social Studies shows the largest negative shift."

## Compliance Requirements Before Import Goes Live

Before the BECE module is switched on for a school, the product should verify:

1. school registration authority acknowledgement exists,
2. legacy migration or exam-notice workflow has been completed where required,
3. school-side lawful basis is documented,
4. role-based access is limited to authorised leaders and staff,
5. imports are audited, and
6. exported reports avoid unauthorised disclosure of identifiable minors' exam data.

Access control rule:

1. Raw candidate results are restricted to the proprietor and headmaster only.
2. Summary analytics are available to the proprietor and headmaster by default.
3. Teachers receive restricted subject-level summaries automatically for their assigned subjects.
4. Any future class-level teacher summaries must be controlled by a separate school setting and must not expose school-wide raw candidate data.
5. Finance, kitchen, inventory, parents, and students do not receive access to school-wide examination data.

## UI Surfaces To Add Later

1. Proprietor or headmaster exam import dashboard
2. Upload and preview screen for result lists
3. Import validation errors panel
4. BECE trend dashboard
5. Subject performance heat map
6. AI summary card for school leadership
7. Compliance status banner that blocks import until required notices are confirmed

## Operational Questions For Counsel And Product

1. EduPulse should not assume that every school automatically has a lawful basis to import historical BECE records.
	For new applicants, the school may rely on the consent or notice accepted on the school apply page where that matches the school's lawful basis.
	Before a school uploads any student biodata into EduPulse SMT outside that admissions flow, the school must send the parent or guardian consent form provided with registration, or an approved equivalent, and retain the resulting evidence.
	For students already enrolled before EduPulse SMT, the school must send and collect the required manual notice or consent forms before historical exam records are imported.
	EduPulse acts as data processor and may rely on the school, as controller, to carry out that process and retain the supporting evidence.
2. What wording should schools use if they want to analyze existing students' external exam history inside EduPulse SMT?
3. What exact data formats do schools usually receive from WAEC?
4. Is the first importer PDF-first, CSV-first, or spreadsheet-first?
5. What exact class-level summary outputs should be unlocked when the school enables the separate teacher class-summary setting, without exposing school-wide raw candidate data?

## Recommended Next Build Order

1. Design the exam import data model.
2. Add a protected upload-and-preview workflow.
3. Normalize per-subject results into analytics-ready tables.
4. Build the first subject trend dashboard.
5. Add internal benchmark views using lawful public aggregate data.
6. Only then begin WAEC partnership outreach for deeper integration.

## Short Position

The BECE intelligence idea is commercially strong and consistent with EduPulse SMT's expansion from operations tooling into proprietor-level strategy tooling.

What is implemented now is the compliance and consent foundation.

What remains is the actual exam-import, data-model, analytics, and WAEC-engagement product work.