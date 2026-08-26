# EduPulse SMT Customer Technical Reference

## Purpose

This document gives school customers a technical, school-facing explanation of how EduPulse SMT works in practice. It is intended for proprietors, headmasters, ICT leads, finance leads, and school decision makers who need a clearer view of platform behavior, billing controls, data handling, access rules, and implementation expectations.

It is not an internal engineering design document. It is a customer-safe technical reference that explains the important operating rules in plain language.

## School Profile

- School name: {{school_name}}
- School code: {{school_code}}
- Selected plan: {{plan_name}}
- Go-live target date: {{go_live_target_date}}
- School-side owner: {{school_owner_name}}
- Billing contact: {{billing_contact_name}}
- Billing contact email: {{billing_contact_email}}
- EduPulse SMT implementation lead: Daniel Asare Anyinam
- Support email: danielasareanyinam2020@gmail.com

## What EduPulse SMT Covers

EduPulse SMT is designed to help a school run core operational workflows in one system. Depending on the plan and the school setup, this includes:

- User and school access management
- Student admissions and student records
- Attendance workflows
- Report card and approval workflows
- Finance and payment oversight
- Subscription and billing visibility
- Governance and role-based control
- School configuration and term management

## Core Operating Model

EduPulse SMT is organized around one school organization at a time. Each school has its own users, records, configuration, and billing state.

The platform uses role-based access so that different school users only see or change the parts of the system relevant to their work.

Typical roles include:

- Proprietor
- Headmaster
- Teacher
- Homeroom teacher
- Finance user

The proprietor remains the main business owner for subscription, billing visibility, and high-level oversight.

## Tenant And Data Separation

EduPulse SMT is a multi-school platform. Each school operates as a separate tenant.

In practical terms, this means:

- Your school data is scoped to your school account
- User access is tied to your school context
- Billing and subscription decisions are evaluated per school
- Reports, finance records, and settings are not intended to cross between schools

## Security And Access Controls

EduPulse SMT uses layered access controls to reduce accidental or unauthorized access.

These controls include:

- Login authentication
- Role-based permissions
- School-level isolation
- Audit-oriented operational records for important billing and finance actions
- Optional or evolving two-factor and account protection flows where configured

Schools are responsible for:

- Protecting proprietor access
- Removing or updating staff access when roles change
- Keeping billing and school-owner contacts current
- Reporting suspected misuse quickly

## School Setup Expectations

To set up a school smoothly, EduPulse SMT typically needs:

1. Proprietor or authorized signatory details
2. Billing contact details
3. School identity and branding details
4. Academic term dates or approval to configure them
5. Student, class, or staff data if import support is required

If required setup information is incomplete, rollout timelines can move.

## Plans And Activation Rules

EduPulse SMT currently works with the following subscription plan structure:

- Free Tier
- Basic
- Premium

Activation rules are:

- Free Tier can become usable after setup is complete
- Paid plans are activated after payment confirmation
- Where trial access is offered, Premium trial access is currently a fixed 30-day window

If a school moves from trial to paid access during an active academic term, the first paid charge may be prorated based on the remaining days in that term.

## Billing And Subscription Rules

EduPulse SMT billing is designed to reduce surprise charges while also preventing unpaid growth from accumulating without control.

The billing model includes:

- Base subscription pricing by plan
- Included student thresholds by plan
- Overage logic when active student counts exceed the included threshold
- Billing visibility inside the proprietor workflow
- Paystack-based subscription payment flows where enabled

## What Counts As A Billable Seat

For subscription growth control, EduPulse SMT primarily evaluates active student count.

In practical terms:

- Students with active enrollment status count toward active billing exposure
- Students moved to non-active statuses such as Withdrawn, Transferred, Inactive, Suspended, or Graduated stop counting as active seats for ongoing growth decisions

Schools should keep student statuses current so billing visibility stays accurate.

## Same-Term Seat Reuse

EduPulse SMT now supports same-term seat reuse logic.

This means:

1. If a student leaves during the current active term and is moved into a non-active status,
2. and another student is later added during that same term,
3. the replacement can reuse that vacated seat,
4. so the school is not charged twice for the same seat exposure in that term.

This rule helps reduce unfair duplicate overage charging during normal student churn.

## Mid-Term Proration

If a school on a paid plan adds students above its included threshold during an active term, EduPulse SMT can calculate a prorated overage amount.

The calculation depends on:

- The plan pricing rules
- The number of students above the included threshold
- The remaining days in the active term
- Same-term seat reuse credits where applicable

If there is no active term configured, some billing actions may be deferred until term activation or later billing processing.

## Billing Protection Rules

EduPulse SMT includes billing protection controls intended to avoid silent revenue leakage and reduce customer confusion.

These controls include:

- Blocking new paid-seat growth when a school would exceed its included threshold without active saved-card auto-billing coverage
- Blocking additional billable growth when an earlier prorated overage invoice is still unpaid
- Blocking removal of the last saved billing card when the school is already above the included threshold
- Blocking disabling of recurring auto-billing when the school is already above the included threshold

These controls are intended to prevent a school from continuing to grow paid-seat liability after removing payment coverage.

## Overdue, Read-Only, And Suspension Behavior

EduPulse SMT does not aim to delete school records because of a billing issue.

Where billing becomes overdue, the platform may move through staged restrictions such as:

- Grace status
- Overdue status
- Suspended or heavily restricted status

Depending on the billing state:

- Some state-changing actions may be blocked
- Billing and recovery paths remain available
- Certain historical or read-only views may remain available so the school can review records while resolving billing

This is designed to balance operational continuity with billing enforcement.

## Term Activation Billing Behavior

For paid plans, activating a new academic term may trigger billing checks.

Current behavior is:

- The platform attempts to confirm required billing before fully activating a paid term
- If automatic card billing is available and succeeds, the term can proceed
- If automatic billing is not available, the platform can return a payment link for settlement first
- The term remains inactive until the required payment step is completed where that rule applies

This avoids activating paid usage first and resolving billing later.

## Saved Cards And Auto-Billing

Where recurring billing is enabled, EduPulse SMT can use a saved reusable card authorization for subscription-related charges.

Important points:

- The saved card flow is intended for recurring subscription and overage billing control
- If no reusable authorization is available, manual payment flow may be required
- Schools should keep their billing contact and payment method current
- Removal of the last saved card may be blocked if doing so would leave unpaid paid-seat exposure without coverage

## Payment Rails

EduPulse SMT currently centers subscription-related billing flows around Paystack where that integration is active.

For customers, the practical meaning is:

- Subscription or billing-payment links may route through Paystack
- Webhook-based confirmation may be used for payment reconciliation
- Test credentials may be used in non-production environments until live business verification is complete

Schools should not treat test-mode behavior as final production settlement policy.

## WhatsApp Status

WhatsApp is not part of the active core customer product flow at this time.

If WhatsApp-related references exist in planning or configuration materials, they should be treated as future-facing placeholders unless EduPulse SMT explicitly confirms activation of that integration for your school.

## Academic Terms And Calendar Control

Schools can manage academic term configuration within EduPulse SMT.

This includes:

- Creating or editing term dates
- Marking the active term
- Importing the published national calendar where available
- Using term dates for reporting and billing-related timing behavior

Accurate term setup matters because reporting and prorated billing behavior may depend on active term dates.

## Student And Academic Workflows

EduPulse SMT can support school workflows such as:

- Student admissions
- Student status updates
- Class assignment
- Attendance
- Report card preparation
- Approval routing for report publication

For the school, the operational rule is simple: data quality and current status updates materially affect billing visibility, reports, and oversight accuracy.

## Finance, Records, And Audit Visibility

EduPulse SMT includes finance and billing visibility features intended to support traceability.

Depending on plan, role, and verification state, the platform may provide:

- Payment summaries
- Transaction history
- Billing timeline visibility
- Ledger or audit-oriented views

Some finance and payment workflows can also be restricted if verification or billing conditions are not satisfied.

## Verification And Governance Controls

Certain payment and finance capabilities may depend on school verification status and other governance checks.

In practice, this means some capabilities can be limited until EduPulse SMT has the information needed to safely enable them.

This is intended to reduce risk for both the school and the platform.

## Data Handling Expectations

Schools should assume EduPulse SMT stores operational school data needed for the workflows the school uses.

Examples include:

- User records
- Student records
- Academic records and report artifacts
- Payment-related records
- Operational logs or audit events tied to important actions

Schools should avoid sharing unnecessary sensitive material and should use official platform workflows rather than ad hoc messaging when records matter.

## Customer Responsibilities

For the best outcome, schools should:

1. Keep proprietor ownership current
2. Keep billing contact details current
3. Keep student statuses accurate
4. Review billing visibility regularly
5. Configure academic terms correctly
6. Attend rollout and training sessions
7. Escalate issues early instead of waiting for deadline pressure

## Support And Escalation

Customers should use the formal EduPulse SMT support path for setup, billing, or technical concerns.

Recommended escalation information includes:

- School code
- Affected user role
- The exact workflow being attempted
- Screenshots where appropriate
- Any payment reference or billing reference involved

Support response targets remain subject to issue severity, business hours, and whether the issue requires deeper technical investigation.

## Known Customer-Side Failure Patterns

The most common causes of customer-side disruption are:

- Incomplete term setup
- Outdated billing contact details
- Student statuses not updated after departures
- Delayed action on payment prompts or billing warnings
- Attempting paid growth after removing payment coverage
- Delayed rollout decisions from the school side

## What This Document Does Not Mean

This document does not guarantee:

- Unlimited feature access regardless of plan
- Automatic billing success in every case
- Immediate activation of paid plans without payment confirmation
- Permanent access to paid workflows if billing obligations are ignored
- Immediate activation of future features such as WhatsApp integration

## Recommended Customer Reading Order

For most schools, this document should be used together with:

1. `SCHOOL_CLIENT_LAUNCH_PACKET.md`
2. `SCHOOL_IMPLEMENTATION_GUIDE.md`
3. `EDUPULSE_SCHOOL_USER_BOOKLET.md`

## Contact Path

For customer-facing technical, onboarding, billing, or rollout questions, use your active EduPulse SMT email thread or contact Daniel Asare Anyinam through the current support path provided during onboarding.