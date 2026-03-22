# EduPulse SMT Operations Handoff Sample

## Purpose

This is a filled sample of the internal handoff document used when school onboarding, billing, support, and technical coordination need one shared operating view.

## School Snapshot

- School name: Bright Future Academy
- School code: BFA-ACC
- Current plan: Premium
- Student count: 185
- Stage: `Training`
- Internal owner: Daniel Asare Anyinam
- Backup owner: Daniel Asare Anyinam
- Last school-facing update: March 20, 2026 at 16:30 GMT
- Next checkpoint: March 24, 2026 at 11:00 GMT

## Current Status Summary

- Commercial status: Premium plan confirmed and onboarding payment verified.
- Billing status: Activation complete; bursar finance workflow test still pending.
- Product / implementation status: School setup complete, training delivered, first live workflows started.
- Open risk: Finance workflow is not yet validated by the school bursar in production.
- School-side blocker: Bursar requested a short walkthrough before confirming fee workflow readiness.
- Internal blocker: None.

## School Contacts

- School owner name: Mrs. Evelyn Mensah
- School owner role: Proprietor
- School owner email: evelyn.mensah@brightfuture.edu.gh
- School owner phone: +233 24 555 0147
- Billing contact name: Mr. Daniel Ofori
- Billing contact email: bursar@brightfuture.edu.gh
- Billing contact phone: +233 24 555 0182

## Active Owners

| Area | Owner | Backup | Current Action |
| --- | --- | --- | --- |
| Onboarding | Daniel Asare Anyinam | Daniel Asare Anyinam | Confirm first-week follow-up agenda and activation sign-off path |
| Billing | Daniel Asare Anyinam | Daniel Asare Anyinam | Run bursar-led finance workflow validation on March 24 |
| Support | Daniel Asare Anyinam | Daniel Asare Anyinam | Monitor first live usage and capture support questions |
| Technical | Daniel Asare Anyinam | Daniel Asare Anyinam | Remain available during bursar validation in case workflow issue appears |
| Account / Retention | Daniel Asare Anyinam | Daniel Asare Anyinam | Prepare 30-day adoption review checkpoint |

## Immediate Checklist

- [x] School owner confirmed
- [x] Internal owner confirmed
- [x] Current plan and billing state verified
- [x] Payment verification status checked if relevant
- [x] Training status checked
- [x] Open support tickets reviewed
- [x] Escalation need assessed
- [x] Next school-facing update assigned

## Decision Rules

- If billing is incorrect or unverified, do not promise activation until Finance or Billing Ops confirms status.
- If the school is blocked from core daily workflows, Support and Technical must both be visible on the thread.
- If an onboarding milestone is likely to slip, escalate before the deadline is missed.
- If the issue affects data integrity, tenant isolation, or payment correctness, treat it as urgent.

## Escalation Triggers

| Trigger | Escalation Owner | Required Output |
| --- | --- | --- |
| Kickoff or setup milestone likely to be missed | Daniel Asare Anyinam | New owner, recovery plan, next update time |
| Paid activation blocked or payment mismatch | Daniel Asare Anyinam | Payment status, reconciliation path, customer update |
| Import failure or data-quality dispute | Daniel Asare Anyinam | Decision on retry, rollback, or correction path |
| Critical support issue not acknowledged in SLA | Daniel Asare Anyinam | Assigned responder and ETA |
| Production outage, security issue, or tenant risk | Daniel Asare Anyinam | Incident channel, impact summary, containment plan |

## School-Facing Update Format

Use this format when handing off or escalating:

1. Current status in one sentence
2. What has already been completed
3. What is blocking progress
4. Who now owns the next action
5. When the school will receive the next update

## Handoff Notes

- Most recent completed action: Kickoff and admin training completed, with proprietor and headmaster attendance confirmed.
- Current blocker: Finance workflow has not yet been tested by the bursar in the live tenant.
- Next action: Daniel Asare Anyinam to run a guided bursar payment workflow validation session.
- Due date: March 24, 2026
- Owner: Daniel Asare Anyinam

## Closure Criteria

Only close the handoff when:

- A named owner is responsible for the next step
- The school-facing update has been sent or scheduled
- Billing and activation status are unambiguous
- No unresolved escalation is missing an owner