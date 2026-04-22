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
- public payment link after successful admission
- school branding on the public page

If the school requests correction:
- parents can upload missing documents
- parents can update guardian contact details
- the AI Registrar re-scores the application immediately after resubmission

### 3. Parent Payment Instructions

Route:
- `GET /api/public/schools/<school_id>/payments/<student_code>`

This route returns a parent-safe payment payload with:
- stable learner payment identity
- supported payment rails
- structured reference examples
- fee-by-fee payment instructions
- fee-route DVA details where configured
- school-office fallback guidance
- school-configured admission fee when enabled

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
- the parent status endpoint can expose the payment link for the admitted learner
- the parent receives a fresh status update email when an email address is on file

If staff requests correction, schedules a visit, invites a test, or rejects:
- the parent status page reflects the new state
- the parent can receive a notification email when an email address is on file

## Frontend Entry Points

Public routes:
- `/apply/:schoolId`
- `/apply/:schoolId/status/:statusToken`
- `/pay/:schoolId/:studentCode`

School-side review surface:
- admissions panel AI Registrar review queue

## Payment Identity Model

The current payment experience uses a transition model.

Preferred parent guidance:
- stable learner payment identity first
- structured reference per fee type

Still supported where schools configured it earlier:
- dedicated fee-route virtual accounts
- shortcode or MoMo route by fee type

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