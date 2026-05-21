# EduPulse SMT Standard Operating Procedures

## Purpose

This document defines the official operating procedures for running EduPulse SMT as a real business, not just a software product. It standardizes how the team handles onboarding, activation, billing, support, incident response, renewal, and offboarding.

## Scope

These procedures apply to:

- New school acquisition and onboarding
- Subscription activation and billing control
- Data import and staff training
- Support and issue handling
- Reliability and incident escalation
- Renewals, upgrades, downgrades, and churn prevention
- Account closure and data handover

## Operating Principles

1. Every school must have a named owner on both sides.
2. No paid plan is considered active until payment is confirmed in EduPulse SMT.
3. No production data import happens without school approval and a rollback path.
4. Every operational promise must be tied to a ticket, email thread, or audit log.
5. Billing exceptions must be documented; informal WhatsApp approvals are not enough.
6. Sensitive actions must follow tenant isolation, role permissions, and password verification controls already built into the platform.
7. No live student, guardian, admissions, report-card, or external examination import should proceed until the school has completed the required commercial acceptance and applicable privacy or data-processing paperwork.

## Roles And Ownership

| Role | Responsibility |
| --- | --- |
| Daniel Asare Anyinam | Qualifies the school, captures requirements, confirms decision maker |
| Daniel Asare Anyinam | Runs kickoff, collects setup assets, coordinates training and go-live |
| Daniel Asare Anyinam | Confirms plan, payment status, invoices, reconciliation, and exceptions |
| Daniel Asare Anyinam | Handles tickets, user issues, status updates, and closure confirmation |
| Daniel Asare Anyinam | Owns bugs, incidents, data migration risks, and production fixes |
| School Proprietor | Commercial owner for the school account |
| School Admin / Headmaster | Day-to-day operational contact for activation and training |

## SOP 1: New School Onboarding

### Trigger

A school expresses interest in joining EduPulse SMT through direct sales, referral, marketing, or self-signup.

### Objective

Move the school from interest to first successful login, first core workflow usage, and a clearly documented commercial status.

### Official Procedure

1. Capture lead details.
   Required fields: school name, contact person, role, phone, email, estimated student count, location, target start date, desired plan.
2. Confirm decision maker and use case.
   Identify whether the buyer is the proprietor, headmaster, finance lead, or a school chain coordinator.
3. Classify the opportunity.
   Mark the school as `Free`, `Basic`, `Premium`, or `Enterprise-style` based on student volume and requested features.
4. Send the onboarding email and information request.
   Request authorized signatory, billing contact, data-protection contact, branding assets, import files, and training availability.
5. Verify readiness before account creation.
   Do not proceed until minimum required inputs are available: school identity, owner contact, intended plan, and at least one implementation contact.
6. Create the school organization and proprietor account.
   Generate the tenant, school code, initial proprietor credentials, and tenant-scoped access.
7. Apply plan logic.
   If the school chooses `Free`, activate immediately.
   If the school chooses `Basic` or `Premium`, initialize payment and wait for successful confirmation before considering the plan active.
8. Trigger school verification onboarding.
   Require proprietor submission of school verification profile and track automated KYB outcome (`verified`, `review_required`, or pending fallback outcome).
9. Send welcome and login instructions.
   Include login URL, role expectations, first-week checklist, and support contact path.
10. Schedule kickoff training.
   Book a 60-90 minute session for the proprietor and school operations lead.
11. Track activation milestones.
   Confirm first login, first teacher created, first students added, first attendance entry, and first finance record.
12. Mark onboarding status.
   Move the school to `Activated` only after first-value actions are observed, not merely after signup.

### Exit Criteria

- School account exists in production
- Correct commercial plan is set
- Proprietor can log in
- School verification state is recorded and monitored
- Kickoff training is scheduled or completed
- First-value actions are recorded

## SOP 2: Data Import And Configuration

### Trigger

The school submits student, staff, or historical data for migration.

### Official Procedure

1. Confirm the import owner on the school side.
2. Confirm legal and policy readiness before import.
   Verify the school has accepted the required terms, privacy notices, and any applicable data-processing paperwork for the import type.
3. Receive files through an approved channel.
4. Validate the file format before import.
   Check required columns, duplicate records, class naming consistency, and contact field structure.
5. Confirm lawful-purpose scope for sensitive imports.
   For admissions files, report-card images, WAEC or BECE results, or chief examiner materials, confirm the school is uploading only data it is authorized to use for legitimate educational purposes.
6. Back up the current tenant data state.
7. Run a staging import or dry-run validation when the volume is high or the data is messy.
8. Share import exceptions with the school for correction.
9. Execute production import only after approval.
10. Verify sample records with the school.
   Check at least one student, one class, one staff record, and one guardian/contact path where available.
11. Log completion.
   Record import date, operator, source file, affected modules, and issues found.

### Exit Criteria

- Imported records are visible in the correct tenant
- Exceptions are documented
- School confirms that critical records are accurate

## SOP 3: School Activation And First-Week Success

### Trigger

The school account is created and ready for live use.

### Official Procedure

1. Run kickoff training.
   Cover login, role responsibilities, attendance, report workflow, finance workflow, and support path.
2. Guide the school through first live actions.
   Minimum target: add teachers, add students, record attendance, and record or confirm at least one payment-related workflow.
3. Configure branding and report settings.
4. Confirm staff role assignments.
5. Review billing visibility with the proprietor.
   Explain meter, threshold alerts, trial state, plan changes, and what happens on downgrade.
6. Share the first-week checklist.
7. Perform a 3-7 day activation follow-up.
   Confirm blockers, inactive roles, missing data, and unused modules.

### Success Metrics

- First login within 24 hours
- First data entry within 48 hours
- Multiple role usage within 7 days
- No unresolved blocker preventing day-to-day operations

## SOP 4: Subscription, Billing, And Payment Control

### Trigger

The school selects a paid plan, renews, upgrades, downgrades, or crosses billing thresholds.

### Official Procedure

1. Confirm the requested plan and effective date.
2. Check current student count and current term status.
3. Generate or initiate the correct billing event.
   This may be first subscription payment, term renewal, or pro-rated overage.
4. Use official payment channels only.
   Paystack, approved bank transfer, or other enabled methods.
5. Wait for payment confirmation before manually promising activation.
6. Reconcile the transaction.
   Use webhook confirmation, verification flow, and reconciliation tools. If a mismatch exists, run manual recovery or wait for the scheduled sweep.
7. Notify the school of the result.
   Status must be one of: `Paid and active`, `Pending verification`, `Failed`, or `Needs manual review`.
8. Document exceptions.
   Any waiver, delayed payment, credit, or special pricing must be recorded.

### Verification-State Note

- Financial workflows may be blocked when school verification is not approved.
- Where blocked, route the school to compliance onboarding steps and track resolution in the compliance queue.

### Special Rules

- Downgrade requests do not remove already-paid access immediately. If a paid term is still active, the downgrade is scheduled for the next billing boundary.
- Over-limit admissions must not bypass plan controls. Capacity checks must respect actual active student counts.
- Manual recovery is allowed only through official reconciliation procedures, not by editing database records ad hoc.

## SOP 5: Support Ticket Handling

### Trigger

A school reports a bug, asks a question, requests training help, or raises a billing concern.

### Official Procedure

1. Create or confirm a support ticket.
2. Classify severity.
   Use `Critical`, `High`, `Normal`, or `Low`.
3. Acknowledge receipt.
   Share ticket ID and expected next update time.
4. Triage the issue.
   Determine whether the issue is user error, training gap, data issue, payment issue, or product defect.
5. Assign an owner.
6. Provide status updates until closure.
7. Confirm resolution with the school.
8. Close only after either user confirmation or clear evidence that the requested outcome has been delivered.

### Severity Guidance

- `Critical`: School cannot log in, billing corruption, tenant isolation risk, payment recorded wrongly, or report workflow fully blocked during active use
- `High`: Major feature blocked with workaround unavailable
- `Normal`: Standard bug, training issue, or configuration request
- `Low`: Cosmetic issue, feature question, or enhancement request

## SOP 6: Incident Response And Reliability Escalation

### Trigger

Production outage, failed payment reconciliation, data inconsistency, security alert, or background-job failure.

### Official Procedure

1. Open an incident record immediately.
2. Assign incident commander.
3. Assess impact.
   Determine affected schools, affected modules, and whether any financial or data integrity risk exists.
4. Contain the issue.
   Disable the unsafe flow, stop repeated retries, or isolate the affected path.
5. Use the documented recovery controls.
   For billing and payment mismatches, use reconciliation and audit tools rather than manual shortcuts.
6. Communicate status.
   Send internal updates and, where needed, school-facing updates with current impact and next checkpoint.
7. Restore service.
8. Verify data integrity after the fix.
9. Complete post-incident review within 48 hours.

### Mandatory Outputs

- Incident summary
- Timeline of actions
- Root cause
- Schools impacted
- Recovery actions taken
- Preventive follow-up item owner and due date

## SOP 7: Renewal, Upgrade, Downgrade, And Churn Control

### Trigger

Upcoming billing date, usage threshold alert, downgrade request, cancellation signal, or inactivity trend.

### Official Procedure

1. Review account health before renewal.
   Check plan, payment history, usage, unresolved tickets, and current active student count.
2. Send renewal or billing reminder in advance.
3. If the school is expanding, recommend the correct plan using actual usage data.
4. If the school asks to downgrade, explain the effective date and retained access window.
5. If the school signals churn, run a save conversation.
   Identify whether the cause is price, adoption, support quality, or missing features.
6. Offer the approved remedy.
   Examples: training session, billing clarification, staged downgrade, or implementation help.
7. If cancellation proceeds, move to the offboarding SOP.

## SOP 8: Offboarding And Account Closure

### Trigger

The school cancels, becomes permanently inactive, or requests account closure.

### Official Procedure

1. Confirm the request with the authorized proprietor or billing owner.
2. Verify outstanding obligations.
   Check unpaid invoices, open disputes, unresolved support issues, and pending exports.
3. Offer final export or handover steps according to policy.
4. Set the account to the correct terminal state.
   Example: cancelled, suspended, or archived.
5. Preserve records according to retention and compliance policy.
6. Revoke unneeded active access.
7. Record the churn reason.
8. Close the account operationally.

### Exit Criteria

- Ownership of closure is documented
- Final state is applied correctly
- Retention obligations are preserved
- Churn reason is captured for business analysis

## SOP 9: Monthly Operating Review

### Trigger

First business week of each month.

### Official Procedure

1. Review new schools added.
2. Review schools activated vs. stalled.
3. Review unpaid or partially reconciled billing events.
4. Review support ticket volume and resolution times.
5. Review incidents and postmortem follow-ups.
6. Review upgrade, downgrade, and churn trends.
7. Produce an action list for the next month.

### Core KPIs

- New schools signed
- Activation rate
- Time-to-first-value
- Paid conversion rate
- Renewal rate
- Ticket response time
- Ticket resolution time
- Billing recovery rate
- Churn count and churn reasons

## Required Records

The following must exist for normal operations:

- Lead and onboarding log
- Signed or accepted commercial terms
- Billing contact and authorized owner
- Training completion note
- Support ticket history
- Incident log where relevant
- Churn or cancellation reason on exit

## Source Documents

This SOP should be used alongside the existing system documents:

- README.md
- BUSINESS_PROCESS_MODEL.md
- ONBOARDING_EMAIL_TEMPLATE.md
- SUBSCRIPTION_BILLING_GUIDE.md
- SUPPORT_SYSTEM_GUIDE.md
- RELIABILITY_SCENARIOS.md
- compliance/TERMS_OF_SERVICE.md
- compliance/PRIVACY_POLICY.md
- compliance/INCIDENT_RESPONSE_PLAN.md

## Decision Rule

If a team member is unsure what to do, the default order is:

1. Protect data integrity.
2. Protect billing correctness.
3. Communicate clearly with the school.
4. Leave an audit trail.
5. Escalate instead of improvising.