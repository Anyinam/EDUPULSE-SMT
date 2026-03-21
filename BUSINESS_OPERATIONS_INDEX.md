# EduPulse Business Operations Index

## Purpose

This index brings together the main documents used to operate EduPulse as a business. It is the shortest path for anyone who needs to understand how schools are onboarded, billed, supported, retained, and offboarded.

## Start Here

If you need the big picture first, read these in order:

1. `README.md`
2. `BUSINESS_PROCESS_MODEL.md`
3. `STANDARD_OPERATING_PROCEDURES.md`

## Onboarding And Implementation

- `STANDARD_OPERATING_PROCEDURES.md`
  Master operating rules for onboarding, billing, support, incidents, renewals, and closure.
- `ONBOARDING_CHECKLIST.md`
  Short internal checklist for daily execution.
- `ONBOARDING_CHECKLIST_TEMPLATE.md`
  Reusable per-school template for creating a new onboarding record.
- `ONBOARDING_CHECKLIST_EXAMPLE.md`
  Filled example showing the expected level of completion for one school onboarding record.
- `SCHOOL_IMPLEMENTATION_GUIDE.md`
  School-facing explanation of what implementation looks like.
- `SCHOOL_WELCOME_PACK.md`
  Customer-facing onboarding pack for new schools.
- `ONBOARDING_EMAIL_TEMPLATE.md`
  Standard welcome and information-request email.
- `DATA_IMPORT_GUIDE.md`
  Reference for import expectations and file preparation.
- `DATA_IMPORT_TEMPLATE.csv`
  Base import file format for school data.

## Operational Ownership And Escalation

Assign actual names to the placeholders below before relying on this in production operations.

| Workstream | Primary Owner | Backup Owner | Escalation Trigger | Escalate To |
| --- | --- | --- | --- | --- |
| Lead qualification | `{{growth_owner_name}}` | `{{growth_backup_name}}` | No contact attempt within 1 business day | Head of Growth |
| School onboarding | `{{onboarding_owner_name}}` | `{{onboarding_backup_name}}` | Kickoff or setup milestone missed | Head of Operations |
| Billing and payment verification | `{{billing_owner_name}}` | `{{billing_backup_name}}` | Paid activation blocked, mismatch, or reconciliation issue | Finance Lead |
| Data import | `{{implementation_owner_name}}` | `{{implementation_backup_name}}` | Import failure, data-quality dispute, or rollback risk | Technical Lead |
| Support ticket handling | `{{support_owner_name}}` | `{{support_backup_name}}` | Critical issue not acknowledged within SLA | Support Lead |
| Incident response | `{{incident_commander_name}}` | `{{incident_backup_name}}` | Production outage, data integrity risk, or security event | Executive / Technical Lead |
| Renewal and churn control | `{{account_owner_name}}` | `{{account_backup_name}}` | Renewal at risk, churn signal, or unresolved commercial objection | Head of Operations |

### Escalation Rules

1. Escalate when a committed milestone is likely to be missed, not only after it is missed.
2. Escalate immediately for billing integrity, tenant isolation, or production outage risk.
3. Every escalation must end with a named owner, next checkpoint, and school-facing update plan.
4. If an issue crosses commercial and technical boundaries, both the Finance Lead and Technical Lead must be visible on the thread.

## Billing And Commercial Operations

- `SUBSCRIPTION_BILLING_GUIDE.md`
  Billing model, plan structure, pro-ration, and renewal logic.
- `SUBSCRIPTION_FEATURES.md`
  Feature matrix by subscription tier.
- `USAGE_BASED_BILLING_SUMMARY.md`
  Summary of metering and usage-based charging concepts.
- `PAYMENT_INTEGRATION.md`
  Operational payment-flow reference.
- `PAYMENT_CATEGORIZATION.md`
  Payment classification rules.
- `PAYMENT_REFERENCE_FORMAT.md`
  Reference format standards.
- `BANK_TRANSFER_INTEGRATION.md`
  Bank-transfer flow and operational notes.
- `PAYSTACK_SUBACCOUNT_GUIDE.md`
  Paystack-specific setup and handling details.

## Support And Reliability

- `SUPPORT_SYSTEM_GUIDE.md`
  Ticket handling flow and support communication behavior.
- `RELIABILITY_SCENARIOS.md`
  Real-world failure scenarios and recovery paths.
- `AUDIT_INTEGRITY_SYSTEM.md`
  Audit and ledger integrity reference.

## Compliance And Trust

- `compliance/TERMS_OF_SERVICE.md`
  Commercial and legal usage terms.
- `compliance/PRIVACY_POLICY.md`
  Privacy commitments.
- `compliance/INCIDENT_RESPONSE_PLAN.md`
  Security and incident-response baseline.
- `compliance/DATA_RETENTION_POLICY.md`
  Record retention requirements.
- `compliance/INFORMATION_SECURITY_POLICY.md`
  Security control expectations.

## Deployment And Production Readiness

- `PRODUCTION_DEPLOYMENT.md`
  Production environment and hosting configuration reference.
- `PRODUCTION_SECURITY_GUIDE.md`
  Production hardening checklist.
- `SECURITY.md`
  Security guidance and deployment checks.
- `LAUNCH_GUIDELINE.md`
  Launch-readiness reference.

## When To Use Which Document

- Need the official business process: use `STANDARD_OPERATING_PROCEDURES.md`
- Need to onboard one school today: use `ONBOARDING_CHECKLIST_TEMPLATE.md`
- Need to see a completed example: use `ONBOARDING_CHECKLIST_EXAMPLE.md`
- Need to explain rollout to a school: use `SCHOOL_IMPLEMENTATION_GUIDE.md`
- Need a sendable school-facing starter document: use `SCHOOL_WELCOME_PACK.md`
- Need pricing or billing logic: use `SUBSCRIPTION_BILLING_GUIDE.md`
- Need incident or reconciliation context: use `RELIABILITY_SCENARIOS.md`
- Need ticket workflow and support expectations: use `SUPPORT_SYSTEM_GUIDE.md`
