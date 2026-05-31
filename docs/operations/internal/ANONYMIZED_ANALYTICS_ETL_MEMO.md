# EduPulse SMT Anonymized Analytics ETL Memo

## Purpose

This memo describes the intended technical and governance design for EduPulse SMT's future macro-analytics pipeline. It is written for legal counsel, compliance review, and future implementation planning.

It does not claim that the full analytics warehouse is already in production. It documents the design constraints that must be preserved if EduPulse SMT later commercializes aggregated school-performance benchmarking.

## Intended System Split

EduPulse SMT should treat identifiable school operations data and shared analytics data as separate layers.

### 1. Transactional System

The live application stores tenant-scoped operational data such as:

- student identity and biodata;
- guardian contact records;
- school-specific attendance and academic records;
- admissions and report-card files; and
- school-uploaded WAEC or BECE result data.

This layer remains school-specific and contains personal data.

### 2. Controlled ETL Layer

A scheduled ETL job should extract only the fields needed for approved statistical analysis.

Before data is loaded into the shared analytics store, the ETL step should remove or transform:

- student names;
- student IDs and admissions identifiers;
- phone numbers, email addresses, and other contact details;
- exact dates of birth;
- document file names or raw uploads;
- direct school names; and
- any other direct identifier not required for aggregate reporting.

### 3. Analytics Warehouse

The shared analytics store should keep only broad analytical dimensions such as:

- region;
- district;
- school type;
- academic year;
- class level or cohort;
- subject;
- score, grade, or pass-band;
- payment-timing or liquidity bands where lawfully approved; and
- benchmark segment labels.

This layer should avoid storing direct personal identifiers or direct school identifiers.

## Permitted Analytical Uses

If the source data has been irreversibly anonymized, EduPulse SMT may use the resulting non-personal dataset for:

- national, regional, and district benchmarking;
- yearly performance trend analysis across cohorts;
- curriculum-gap analysis;
- Chief Examiner historical mapping and subject-risk signals;
- customer benchmark dashboards;
- white papers and educational research outputs; and
- system-improvement analytics.

## Minimum Technical Guardrails

The ETL and reporting design should include at least the following controls:

1. Direct identifier stripping before shared analytics storage.
2. Removal or generalization of direct school names except where a separate lawful basis exists.
3. Logical separation between the transactional database and the analytics warehouse.
4. Access restriction so only authorized internal roles can query the shared analytics layer.
5. Audit logging for extract jobs, schema changes, and benchmark report generation.
6. Small-cell suppression or minimum cohort thresholds to reduce re-identification risk.
7. Review of any output that compares narrow cohorts, exceptional outliers, or sparsely populated districts.
8. Contract and UI disclosure that schools remain owners of raw identifiable records while EduPulse SMT claims rights only in the anonymized aggregate outputs.

## Output Suppression Guidance

To reduce re-identification risk, benchmark outputs should avoid publishing slices that are too narrow.

Examples of higher-risk outputs include:

- one named school against one other school;
- one district with very few participating schools;
- a cohort broken down by multiple combined filters that leave very few students; and
- unusual subject-performance outliers tied to a thin segment.

Before public release or customer benchmarking use, EduPulse SMT should apply minimum-threshold rules or suppression logic for small groups.

## Governance And Recordkeeping

Before launch of the analytics warehouse, EduPulse SMT should keep:

- the approved registration notice and DPA wording;
- the current Privacy Policy and Terms of Service;
- the ETL field map showing which source fields are excluded, transformed, or retained;
- any output-threshold policy for suppression or aggregation;
- access-control approvals for analytics users; and
- a release checklist for benchmark dashboards or public reports.

## Counsel Review Questions

Counsel should confirm:

1. whether the proposed anonymization standard is described accurately and not overstated;
2. whether the onboarding checkbox and notice are sufficient for the intended reuse of school data;
3. whether any additional DPC filing or disclosure is advisable before commercial rollout;
4. whether the ownership wording for anonymized aggregate outputs should be retained as drafted or narrowed; and
5. whether any categories, such as fee-payment timing analytics, need extra contractual caution before use in benchmark products.

## Status

As of May 31, 2026, this memo is a design-control document for legal and compliance preparation. Any future implementation should be reviewed against this memo, the current contract documents, and counsel's final advice before launch.
