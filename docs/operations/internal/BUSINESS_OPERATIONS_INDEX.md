# EduPulse SMT Business Operations Index

## Purpose

This is the canonical business operations index for EduPulse SMT. It maps the internal and school-facing documents used to onboard schools, manage billing, coordinate support, run incidents, and control renewals or offboarding.

## How To Use These Docs

1. Start here for the business-operations view of the system.
2. Use `../customer/` when the audience is a school or prospect.
3. Use `../internal/` when the audience is EduPulse SMT staff.
4. Treat files at the repo root as redirect stubs only; the canonical versions now live under `docs/operations/`.
5. Before sending templates externally, replace placeholders with real values and remove fields that do not apply.

## Start Here

If you need the big picture first, read these in order:

1. `../../README.md`
2. `../../BUSINESS_PROCESS_MODEL.md`
3. `STANDARD_OPERATING_PROCEDURES.md`

## Standard Placeholder Set

Use these placeholder names consistently across onboarding, launch, email, and incident templates.

| Placeholder | Meaning |
| --- | --- |
| `{{school_name}}` | School display name |
| `{{school_code}}` | Internal or customer-facing school code |
| `{{plan_name}}` | Selected subscription plan |
| `{{estimated_student_count}}` | Estimated or current student count |
| `{{go_live_target_date}}` | Intended go-live date |
| `{{school_owner_name}}` | Main school-side owner or decision maker |
| `{{school_owner_role}}` | School-side owner role |
| `{{school_owner_email}}` | School-side owner email |
| `{{school_owner_phone}}` | School-side owner phone |
| `{{billing_contact_name}}` | School billing contact name |
| `{{billing_contact_email}}` | School billing contact email |
| `{{billing_contact_phone}}` | School billing contact phone |
| `Daniel Asare Anyinam` | Current EduPulse SMT owner across implementation, support, billing, and escalation |
| `danielasareanyinam2020@gmail.com` | Shared support email |

## Onboarding And Implementation

- `STANDARD_OPERATING_PROCEDURES.md`
  Master operating rules for onboarding, billing, support, incidents, renewals, and closure.
- `ONBOARDING_CHECKLIST.md`
  Short internal checklist for daily execution.
- `ONBOARDING_CHECKLIST_TEMPLATE.md`
  Reusable per-school onboarding record template.
- `ONBOARDING_CHECKLIST_EXAMPLE.md`
  Filled example showing expected note quality and sign-off detail.
- `LEGAL_COUNSEL_DOSSIER.md`
  Single-file forwardable legal dossier combining the key counsel materials into one document.
- `LEGAL_COUNSEL_PACKET.md`
  Consolidated entry point for counsel covering incorporation, IP, confidentiality, and Ghana data-protection review.
- `LAWYER_COVER_EMAIL.md`
  Ready-to-send cover email for counsel introducing the legal packet.
- `LAWYER_EXECUTIVE_BRIEF.md`
  One-page executive summary for counsel on EduPulse SMT business, IP, payment, and data-protection positioning.
- `LAWYER_TECHNICAL_SYSTEM_SUMMARY.md`
  Lawyer-facing technical explanation of EduPulse SMT system operation, Paystack routing/split behavior, and cryptography controls.
- `IP_ASSET_INVENTORY.md`
  Inventory of code, workflow, payment, security, and documentation assets that appear protectable as copyright or confidential know-how.
- `GHANA_DATA_PROTECTION_TECHNICAL_BRIEF.md`
  Technical-control briefing mapped to Ghana data-protection issues and supporting repository evidence.
- `FOUNDER_IP_AND_CONFIDENTIALITY_CHECKLIST.md`
  Founder action checklist for ownership, contributor controls, confidentiality, and legal evidence preservation.
- `CONTRIBUTOR_IP_ASSIGNMENT_TEMPLATE.md`
  Draft assignment template for contributors, contractors, advisors, or collaborators creating EduPulse SMT work product.
- `CONFIDENTIALITY_NDA_TEMPLATE.md`
  Draft confidentiality and non-disclosure template for parties receiving EduPulse SMT confidential information.
- `OPERATIONS_HANDOFF.md`
  One-page cross-team coordination sheet for onboarding, billing, support, and escalation.
- `OPERATIONS_HANDOFF_SAMPLE.md`
  Filled handoff example for demos and operational training.
- `INCIDENT_UPDATE_TEMPLATE.md`
  Internal and school-facing incident communications template.
- `INCIDENT_UPDATE_SAMPLE.md`
  Filled incident communication example for demos and operational training.

## Customer-Facing Launch And Rollout Docs

- `../customer/SCHOOL_SEND_PACKAGE.md`
  Master guide for what to send to schools, in what order, and whether to use template or sample assets.
- `../customer/SCHOOL_IMPLEMENTATION_GUIDE.md`
  School-facing explanation of implementation phases and responsibilities.
- `../customer/SCHOOL_IMPLEMENTATION_GUIDE_SAMPLE.md`
  Filled implementation-guide example for demos and presentation-ready sharing.
- `../customer/SCHOOL_WELCOME_PACK.md`
  Short customer-facing onboarding pack.
- `../customer/SCHOOL_WELCOME_PACK_SAMPLE.md`
  Filled welcome-pack example for demos and presentation-ready sharing.
- `../customer/SCHOOL_WELCOME_EMAIL_TEMPLATE.md`
  Primary email-ready school welcome and rollout template.
- `../customer/SCHOOL_WELCOME_EMAIL_TEMPLATE_SAMPLE.md`
  Filled primary welcome-email example for demos and presentation-ready sharing.
- `../customer/SCHOOL_CLIENT_LAUNCH_PACKET.md`
  Combined school-facing launch packet.
- `../customer/SCHOOL_CLIENT_LAUNCH_PACKET_SAMPLE.md`
  Filled sample launch packet for demos and presentation-ready sharing.
- `../customer/ONBOARDING_EMAIL_TEMPLATE.md`
  Short onboarding request email variant.
- `../customer/ONBOARDING_EMAIL_TEMPLATE_SAMPLE.md`
  Filled onboarding request email example for demos and presentation-ready sharing.

## Operations Folder Structure

- `../README.md`
  Entry point for grouped operations docs.
- `../customer/README.md`
  Customer-facing launch and onboarding document map.
- `README.md`
  Internal operations, handoff, and incident document map.

## Operational Ownership And Escalation

Current owner assignment is intentionally single-owner for now and uses Daniel Asare Anyinam across the operating model.

| Workstream | Primary Owner | Backup Owner | Escalation Trigger | Escalate To |
| --- | --- | --- | --- | --- |
| Lead qualification | Daniel Asare Anyinam | Daniel Asare Anyinam | No contact attempt within 1 business day | Daniel Asare Anyinam |
| School onboarding | Daniel Asare Anyinam | Daniel Asare Anyinam | Kickoff or setup milestone missed | Daniel Asare Anyinam |
| Billing and payment verification | Daniel Asare Anyinam | Daniel Asare Anyinam | Paid activation blocked, mismatch, or reconciliation issue | Daniel Asare Anyinam |
| Data import | Daniel Asare Anyinam | Daniel Asare Anyinam | Import failure, data-quality dispute, or rollback risk | Daniel Asare Anyinam |
| Support ticket handling | Daniel Asare Anyinam | Daniel Asare Anyinam | Critical issue not acknowledged within SLA | Daniel Asare Anyinam |
| Incident response | Daniel Asare Anyinam | Daniel Asare Anyinam | Production outage, data integrity risk, or security event | Daniel Asare Anyinam |
| Renewal and churn control | Daniel Asare Anyinam | Daniel Asare Anyinam | Renewal at risk, churn signal, or unresolved commercial objection | Daniel Asare Anyinam |

### Escalation Rules

1. Escalate when a committed milestone is likely to be missed, not only after it is missed.
2. Escalate immediately for billing integrity, tenant isolation, or production outage risk.
3. Every escalation must end with a named owner, next checkpoint, and school-facing update plan.
4. If an issue crosses commercial and technical boundaries, Daniel Asare Anyinam remains the single visible owner on the thread.

## Billing And Commercial Operations

- `../../SUBSCRIPTION_BILLING_GUIDE.md`
  Billing model, plan structure, pro-ration, and renewal logic.
- `../../SUBSCRIPTION_FEATURES.md`
  Feature matrix by subscription tier.
- `../../USAGE_BASED_BILLING_SUMMARY.md`
  Summary of metering and usage-based charging concepts.
- `../../PAYMENT_INTEGRATION.md`
  Operational payment-flow reference.
- `../../PAYMENT_CATEGORIZATION.md`
  Payment classification rules.
- `../../PAYMENT_REFERENCE_FORMAT.md`
  Reference format standards.
- `../../BANK_TRANSFER_INTEGRATION.md`
  Bank-transfer flow and operational notes.
- `../../PAYSTACK_SUBACCOUNT_GUIDE.md`
  Paystack-specific setup and handling details.

## Support And Reliability

- `../../SUPPORT_SYSTEM_GUIDE.md`
  Ticket handling flow and support communication behavior.
- `../../RELIABILITY_SCENARIOS.md`
  Real-world failure scenarios and recovery paths.
- `../../AUDIT_INTEGRITY_SYSTEM.md`
  Audit and ledger integrity reference.

## Compliance And Trust

- `../../compliance/TERMS_OF_SERVICE.md`
  Commercial and legal usage terms.
- `../../compliance/PRIVACY_POLICY.md`
  Privacy commitments.
- `../../compliance/INCIDENT_RESPONSE_PLAN.md`
  Security and incident-response baseline.
- `../../compliance/DATA_RETENTION_POLICY.md`
  Record retention requirements.
- `../../compliance/INFORMATION_SECURITY_POLICY.md`
  Security control expectations.

## Deployment And Production Readiness

- `../../PRODUCTION_DEPLOYMENT.md`
  Production environment and hosting configuration reference.
- `../../PRODUCTION_SECURITY_GUIDE.md`
  Production hardening checklist.
- `../../SECURITY.md`
  Security guidance and deployment checks.
- `../../LAUNCH_GUIDELINE.md`
  Launch-readiness reference.

## When To Use Which Document

- Need the official business process: use `STANDARD_OPERATING_PROCEDURES.md`
- Need one single-file legal dossier for immediate forwarding: use `LEGAL_COUNSEL_DOSSIER.md`
- Need the single entry point for the whole counsel packet: use `LEGAL_COUNSEL_PACKET.md`
- Need the email to send the packet to counsel: use `LAWYER_COVER_EMAIL.md`
- Need a concise lawyer-facing overview first: use `LAWYER_EXECUTIVE_BRIEF.md`
- Need a lawyer-facing technical summary for incorporation, IP, or Ghana data-protection review: use `LAWYER_TECHNICAL_SYSTEM_SUMMARY.md`
- Need the main list of protectable system assets: use `IP_ASSET_INVENTORY.md`
- Need the Ghana data-protection technical control view: use `GHANA_DATA_PROTECTION_TECHNICAL_BRIEF.md`
- Need the founder-side ownership and confidentiality checklist: use `FOUNDER_IP_AND_CONFIDENTIALITY_CHECKLIST.md`
- Need a draft assignment form for contributors or contractors: use `CONTRIBUTOR_IP_ASSIGNMENT_TEMPLATE.md`
- Need a draft confidentiality/NDA form: use `CONFIDENTIALITY_NDA_TEMPLATE.md`
- Need to onboard one school today: use `ONBOARDING_CHECKLIST_TEMPLATE.md`
- Need to see a completed example: use `ONBOARDING_CHECKLIST_EXAMPLE.md`
- Need to explain rollout to a school: use `../customer/SCHOOL_IMPLEMENTATION_GUIDE.md`
- Need one place that tells you what school-facing assets to send: use `../customer/SCHOOL_SEND_PACKAGE.md`
- Need a filled implementation guide example: use `../customer/SCHOOL_IMPLEMENTATION_GUIDE_SAMPLE.md`
- Need a sendable school-facing starter document: use `../customer/SCHOOL_WELCOME_PACK.md`
- Need a filled starter-pack example: use `../customer/SCHOOL_WELCOME_PACK_SAMPLE.md`
- Need the primary ready-to-send onboarding email: use `../customer/SCHOOL_WELCOME_EMAIL_TEMPLATE.md`
- Need a filled primary onboarding email example: use `../customer/SCHOOL_WELCOME_EMAIL_TEMPLATE_SAMPLE.md`
- Need the shorter onboarding request email variant: use `../customer/ONBOARDING_EMAIL_TEMPLATE.md`
- Need a filled onboarding request email example: use `../customer/ONBOARDING_EMAIL_TEMPLATE_SAMPLE.md`
- Need a polished all-in-one launch document: use `../customer/SCHOOL_CLIENT_LAUNCH_PACKET.md`
- Need a presentation-ready filled example: use `../customer/SCHOOL_CLIENT_LAUNCH_PACKET_SAMPLE.md`
- Need a single internal coordination page: use `OPERATIONS_HANDOFF.md`
- Need a filled internal coordination example: use `OPERATIONS_HANDOFF_SAMPLE.md`
- Need an incident communication template: use `INCIDENT_UPDATE_TEMPLATE.md`
- Need a filled incident communication example: use `INCIDENT_UPDATE_SAMPLE.md`
- Need pricing or billing logic: use `../../SUBSCRIPTION_BILLING_GUIDE.md`
- Need incident or reconciliation context: use `../../RELIABILITY_SCENARIOS.md`
- Need ticket workflow and support expectations: use `../../SUPPORT_SYSTEM_GUIDE.md`
