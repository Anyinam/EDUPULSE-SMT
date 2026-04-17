# Student Rescue Agent

Student Rescue Agent is EduPulse SMT's intervention engine for proprietor oversight. It turns scattered financial, attendance, and academic warning signs into one prioritized rescue queue with clear next actions.

## What It Solves

Schools usually discover risk too late.

- A student stops performing well for two terms before leadership notices.
- Tuition debt grows until the family disengages.
- Attendance drops while the school still treats the issue as isolated.
- Feeding-payment exceptions create daily operational friction without a coordinated response.

Student Rescue Agent solves that by identifying students who need intervention now and telling leadership what to do next.

## Current Signals Used

The current MVP prioritizes students using the following signals:

- overdue tuition beyond 30 days
- high outstanding tuition balance
- student present without feeding payment cleared
- low latest term average
- weak attendance in the latest report
- declining academic trend compared with the previous report

Important nuance:

- unpaid tuition alone is not automatically treated as rescue risk immediately after reopening
- the agent now considers reopening grace, recent tuition payment behaviour, scholarships, and supporting attendance or academic signals before escalating tuition-related risk

## Risk Model

The backend computes a severity-oriented `risk_score` from `0` to `100`.

- `Critical`: `70+`
- `High`: `50-69`
- `Moderate`: `30-49`
- `Watch`: below `30`

Current scoring is intentionally transparent and rule-based.

- overdue tuition contributes the largest weight
- feeding-payment exceptions increase urgency for daily operations
- poor academics and attendance add rescue pressure
- a declining trend raises escalation priority
- recent tuition payment activity can reduce false alarms
- scholarship coverage prevents tuition from being treated as a rescue problem when the school already knows tuition is covered
- a school that has just reopened gets a short grace window before tuition debt can drive rescue escalation on its own

This design keeps the system explainable for school leadership and easy to refine as more data is collected.

## API Surface

### Dedicated rescue endpoint

- `GET /api/proprietor/student-rescue-agent`

Returns:

- `agent_name`
- `headline`
- `summary`
- `students`
- `generated_at`

Each student entry includes:

- identity and guardian contact fields
- `risk_score`
- `risk_level`
- `priority_rank`
- `rescue_summary`
- `intervention_reasons`
- `recommended_actions`
- `contact_templates`
- `recent_outcomes`
- `last_outcome`
- `latest_report`

### Contact template endpoint

- `GET /api/proprietor/student-rescue-agent/contact-templates/<student_id>`

Returns call, SMS/WhatsApp, email, and meeting-brief drafts for the selected rescue case.

Note:

- WhatsApp delivery is intentionally deferred for now because of cost control.
- The platform currently provides copy-ready SMS/WhatsApp drafts only.

### Outcome logging endpoint

- `POST /api/proprietor/student-rescue-agent/outcome`

Request body:

- `student_id`
- `action_code`
- `notes` optional

Current action codes:

- `guardian_called`
- `email_sent`
- `payment_plan_agreed`
- `academic_support_assigned`
- `resolved`

Outcomes are stored through the audit log so schools can review what action has already been taken on each flagged student.

### Rescue email send endpoint

- `POST /api/proprietor/student-rescue-agent/send-email`

This sends the generated rescue email template directly to the stored parent email address and automatically logs an `email_sent` rescue outcome.

### Rescue report endpoint

- `GET /api/proprietor/student-rescue-agent/report`

Supports reporting on current rescue work, including:

- open cases
- in-progress cases
- resolved cases
- recent action volume
- action breakdown from the audit trail

Supported filters:

- `status`
- `risk_level`

### Dashboard live-feed integration

- `GET /api/proprietor/live-feed`

Also now returns:

- `student_rescue_agent`

The existing `critical_list` remains available for compatibility, but it is now backed by the rescue-agent prioritization logic.

## Frontend Surface

The proprietor dashboard now includes a dedicated Student Rescue Agent card that shows:

- total flagged students
- critical cases
- contact queue size
- average rescue risk
- ranked rescue queue
- modal detail view with reasons and recommended actions
- one-click outcome logging from the rescue modal
- one-click rescue email sending from the rescue modal
- editable rescue email subject and body before send
- copy-ready guardian contact templates inside the rescue modal
- recent rescue action history per student
- dashboard filters for open, in-progress, resolved, and risk bands
- rescue reporting cards for weekly action volume and closure state

In addition, proprietors now have a dedicated Rescue Activity Center page from the left navigation. This page gives rescue work a permanent home outside the main dashboard.

Free-tier schools see a limited preview while Premium schools can view the full rescue queue.

## Why This Matters Commercially

This feature positions EduPulse away from generic school-management software and generic AI chat.

It gives schools a concrete answer to a high-value question:

"Which students are drifting into financial or academic danger, and what should we do today?"

That creates a stronger sales narrative than broad AI messaging because it connects directly to:

- retention of students
- revenue protection
- proprietor oversight
- intervention accountability
- measurable action rather than passive dashboards

## Demo Script

Use this short flow in product demos:

1. Open the Proprietor Dashboard and show the Student Rescue Agent summary cards.
2. Open one flagged student and point out the exact reasons behind the score.
3. Show the recommended actions and the ready-made guardian contact templates.
4. Log an outcome such as `Guardian Called` or `Payment Plan Agreed`.
5. Show that the rescue history is now visible on the same student.

This demonstrates that EduPulse is not just detecting risk. It is helping schools act, document the action, and stay accountable.

## Likely Next Upgrades

- intervention logging and outcome tracking
- automated parent contact templates tied to recommended actions
- class- or cohort-level rescue trends
- counselor / headmaster assignment workflow
- escalation SLA tracking
- custom school-specific risk weights
- predictive dropout-risk features once sufficient data quality exists