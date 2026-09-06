# Parent Admissions Workflow

## Purpose

This document describes the implemented parent-facing admissions and payment workflow that now sits on top of EduPulse's school-led B2B platform.

It covers:
- the public parent flow
- the school review flow
- the payment-instruction handoff after admission
- public branding and parent notifications
- correction resubmission after school feedback
- the current limits of the AI Registrar MVP

## Current Operating Model

EduPulse remains school-controlled.

The AI Registrar does not make final admissions decisions. It performs triage and recommendation work so staff can review cleaner applications faster.

Current model:
- parent submits application directly to the school
- AI Registrar scores completeness and suggests next action
- school staff reviews and decides
- parent receives a status token and tracking link by email when an email address is available
- admitted learners can be routed into parent-safe payment instructions

## Public Parent Flow

### 1. Submit Application

Route:
- `POST /api/public/schools/<school_id>/admissions/apply`
- `GET /api/public/schools/<school_id>/profile`

Current payload supports:
- applicant name
- preferred class
- guardian contact details
- desired test mode
- internet quality
- passport photo upload
- uploaded supporting documents

Public school profile payload supports:
- school name
- logo and theme color
- motto and contact details
- admission-fee setting and amount if the school enabled it

Current AI Registrar outputs:
- application code
- status token
- completeness summary
- missing items
- AI recommendation
- next-step status
- notification payload with tracking-link email status and SMS preview copy

Typical recommendations:
- `invite_online_test`
- `schedule_school_visit`
- `request_correction`

### 2. Track Status

Route:
- `GET /api/public/schools/<school_id>/admissions/status/<status_token>`
- `POST /api/public/schools/<school_id>/admissions/status/<status_token>/resubmit`

Parents can view:
- current status
- AI summary
- missing items
- reviewer notes
- admitted learner details when available
- public admission-fee checkout on the status page when the school requires admission payment
- school branding on the public page

If the school requests correction:
- parents can upload missing documents and refresh passport-photo evidence
- parents can update guardian contact details
- the AI Registrar re-scores the application immediately after resubmission

### 3. Parent Fee Instructions After Admission

School-side routes:
- `GET /api/students/<student_id>/payment-codes`
- `POST /api/students/<student_id>/payment-codes/<reference_code>/virtual-account`

Current workflow:
- once a learner is approved, school staff opens the payment tracker inside the tenant app
- EduPulse generates fee references per learner
- when staff prints instructions for one learner or a filtered batch, EduPulse can automatically create or reuse tracked transfer accounts for each fee reference
- the printed sheet includes the learner payment identity, per-fee reference, tracked transfer bank details when available, and the school's ordinary bank account only as a fallback/manual route
- the optional online checkout link remains available for special cases, but it is no longer the default school workflow for routine fee sharing

## School Review Flow

### Review Queue

Route:
- `GET /api/admissions/applications`

This queue is available to school leadership roles and returns applications with:
- applicant profile
- uploaded document manifest
- AI summary and recommendation
- current workflow status
- assigned review notes

### Review Actions

Route:
- `POST /api/admissions/applications/<application_id>/review`

Current supported staff actions:
- approve
- invite_online_test
- schedule_visit
- request_correction
- reject

If staff approves an application:
- a real learner record is created
- the application is linked to that learner
- the application passport photo can be copied into `Student.profile_picture`
- uploaded admissions records remain available as linked documents in the learner profile document vault
- the parent status endpoint can expose admission-fee checkout when configured
- the parent receives a fresh status update email when an email address is on file

## Student Profile Linkage

Approved admissions now connect more directly to the learner workspace.

- Admission passport photos can populate the student profile photo.
- Admission documents remain school-scoped files and can be surfaced alongside direct learner uploads.
- Student profiles now support document upload and download through the learner document vault, so schools can keep birth certificates, consent letters, admission forms, and prior reports in one place.

If staff requests correction, schedules a visit, invites a test, or rejects:
- the parent status page reflects the new state
- the parent can receive a notification email when an email address is on file

## Frontend Entry Points

Public routes:
- `/apply/:schoolId`
- `/apply/:schoolId/status/:statusToken`

School-side review surface:
- admissions panel AI Registrar review queue
- payment tracker bulk and single-student instruction printing

## Payment Identity Model

The current payment experience uses a hybrid model.

Preferred parent guidance:
- stable learner payment identity first
- structured reference per fee type
- tracked transfer account on the printed instruction sheet when available

Supported payment rails:
- tracked transfer accounts auto-attached to printed instructions when the school is configured
- structured references across approved phone and digital payment channels
- shortcode or MoMo narration where the school's payment rail supports it

Admission fee rule:
- each school decides whether it charges an admission fee
- the school sets the amount in school settings
- if enabled, the fee is included in parent payment instructions
- if disabled, it does not appear at all

This means the product can move toward cleaner reconciliation without breaking current school setups.

## Current Limits

Current AI Registrar MVP does not yet include:
- autonomous approval without staff review
- advanced OCR extraction scoring across all document formats
- multilingual parent messaging
- automated online test delivery and scoring
- AI Bursar exception handling

Those remain later-phase workflow expansions.