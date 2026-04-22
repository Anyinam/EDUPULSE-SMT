# EduPulse B2B2C AI Employee Roadmap

## Purpose

This document defines EduPulse's planned evolution from a school-led SaaS platform into a school-operated B2B2C system with scoped AI Employees.

It separates:
- what already exists
- what should be built next
- what should remain future-only

## Core Positioning

EduPulse is not becoming a consumer marketplace.

The intended model is:
- B2B at the contract and system-of-record layer
- B2B2C at the workflow layer for parents and guardians
- AI Employees as scoped operational workers inside school-controlled processes

This means:
- the school remains the paying customer
- the school remains the approval authority
- parents get a direct interface for selected workflows
- AI performs labor, but high-trust school decisions remain reviewable and auditable

## What Exists Today

Current implemented capabilities relevant to this roadmap:
- school onboarding and subscription billing
- school-managed admissions and bulk student upload
- public parent admissions application and status tracking
- school-side AI Registrar review queue and review actions
- parent admission update emails and correction resubmission flow
- parent-safe payment instructions using stable learner payment identity plus structured references
- parent payment instructions and payment reference parsing
- optional Paystack fee-route dedicated virtual accounts by payment type
- finance reconciliation and payment tracking
- Student Rescue Agent for intervention workflows
- audited operational workflows across finance and leadership actions

Current commercial position:
- core platform remains subscription-led
- already-shipped AI features such as Student Rescue Agent remain bundled inside Premium
- new scoped AI Employees should be sold as optional add-ons, not forced into every school plan
- charging per AI task completed is not the recommended default for now

## What Should Be Built Next

The first AI Registrar MVP items below are now implemented in baseline form. The remaining work is to deepen automation quality and extend the finance layer.

### 1. AI Registrar MVP

Goal:
- reduce admissions friction for parents and schools without removing school control

Scope:
- public parent admissions form
- document upload
- applicant status tracking
- AI document completeness checks
- AI extraction of key applicant fields
- online-test eligibility recommendation
- school-visit fallback recommendation
- school review queue with AI summary cards

Implementation status:
- baseline MVP implemented
- school review remains the decision point
- document intelligence is currently heuristic-first, not full OCR-native scoring

Recommended approval model:
- AI recommends
- school staff approves, rejects, or requests correction

Do not start with:
- full autonomous approval without human review

### 2. Parent Admissions Access Layer

Goal:
- allow families to begin admission without first visiting the school

Scope:
- application submission
- upload of supporting documents
- status updates
- remote test option where internet quality is sufficient
- in-person fallback when remote testing is not appropriate

Implementation status:
- implemented for first-pass public workflow
- branded public workflow, status emails, and correction resubmission are now implemented
- admission decision PDF packs remain a next-phase workflow enhancement

### 3. AI Bursar

Goal:
- automate reconciliation-heavy finance work and help schools act earlier on payment stress

Scope:
- payment matching and exception detection
- underpayment and overpayment identification
- likely-payment-stress signals
- flexible-plan recommendations for staff review
- daily finance exception summaries
- collections support drafts for approved staff workflows

### 4. Parent Payment Layer

Goal:
- give parents and guardians a cleaner payment experience without excluding low-connectivity households

Scope:
- school-branded fee instructions
- student or family payment identity
- bank-app compatible payment flow
- shortcode / USSD-compatible payment flow
- manual school-office fallback
- payment and balance status visibility for families

Implementation status:
- stable learner payment identity plus structured references implemented in payment instruction payloads
- current fee-route DVA compatibility retained where already configured
- parent balance visibility beyond instructions remains a next-phase item

## Payment Architecture Direction

### Current State

Current implementation supports:
- one optional Paystack dedicated virtual route per fee type
- structured reference parsing for payment categorization
- manual fallback where virtual routes are unavailable

This is valid operationally, but it should be treated as a current implementation pattern, not the universal long-term destination.

### Recommended Medium-Term Target

Preferred direction:
- one stable student or family payment identity
- structured references for tuition, feeding, transport, uniform, and other fees
- one reconciliation engine across all payment rails

Supported rails should include:
- bank app transfer
- USSD or shortcode-compatible flows
- manual school-office fallback

### Why This Direction Is Better

Benefits:
- simpler parent instructions
- better support for mixed digital literacy
- lower route sprawl per school
- easier convergence of online and offline payment behavior
- still compatible with EduPulse's existing reference parsing model

## AI Employee Packaging Direction

### Pricing Principles

Recommended commercial model:
- keep the platform subscription as the main contract layer
- keep already-shipped AI value inside Premium where it already strengthens Premium differentiation
- sell new AI Employees as optional add-ons that a school can enable when the workflow is relevant
- avoid per-task or pure outcome-based billing until trust, baseline usage, and cost predictability are stronger

Reasoning:
- schools need predictable bills
- add-on pricing is easier to explain than per-action charging
- workflow-level packaging better matches how schools buy operational tools
- Premium still needs visible bundled value, so existing AI should not be broken apart too early

### Current Packaging Recommendation

Premium-bundled AI features:
- Student Rescue Agent
- AI Exam Assistant
- current AI lesson-analysis and narrative features already tied to Premium capability tiers

Optional AI Employee add-ons for new workflow workers:
- AI Registrar Add-on
- AI Bursar Add-on
- future Communications Automation Add-on where SMS or WhatsApp usage becomes material

### Draft Add-on Package Model

#### 1. AI Registrar Add-on

Positioning:
- admission workflow automation for schools that want a stronger parent-intake and review-assistance layer

Recommended scope:
- public admissions intake
- AI completeness checks
- extraction summary cards
- online-test versus school-visit recommendation
- correction loop support
- parent status update workflow
- optional approval-document generation when the school enables it

Recommended pricing shape:
- fixed add-on fee per school per term
- include a reasonable admissions volume band in the base add-on
- if usage becomes large later, use volume bands per term, not per application decision

Recommended starting commercial draft:
- Basic plan school: GH₵180 to GH₵300 per term
- Premium plan school: GH₵120 to GH₵240 per term as a lighter uplift because Premium already carries related workflow value

Why Basic and Premium prices differ:
- Premium already bundles adjacent AI and governance capability, so the add-on is an incremental expansion rather than a cold-start workflow purchase
- Premium schools are more likely to already have the operational maturity, staff roles, and data hygiene needed to use the add-on efficiently
- Basic schools get more net-new workflow value from the add-on, so the commercial uplift can be higher
- the difference is about incremental value and packaging strategy, not about giving Premium a weaker version of the add-on

#### 2. AI Bursar Add-on

Positioning:
- finance exception detection and collections decision support for schools with more payment complexity

Recommended scope:
- reconciliation exception queue
- underpayment and overpayment flags
- payment-stress signals
- payment-plan recommendation drafts
- daily finance exception summaries
- collections support drafts for approved staff action

Recommended pricing shape:
- fixed add-on fee per school per term
- no per-transaction billing in the first commercial version

Recommended starting commercial draft:
- Basic plan school: GH₵240 to GH₵420 per term
- Premium plan school: GH₵180 to GH₵360 per term

Why Basic and Premium prices differ:
- Premium schools already pay for stronger analytics, reconciliation context, and governance tooling around finance workflows
- the add-on price for Premium is therefore a narrower workflow uplift
- Basic schools would be buying a larger operational step-up, so the add-on price band is higher
- both tiers should receive the same core AI Bursar worker for that add-on tier; the price difference reflects surrounding plan value, not an intentionally crippled worker

#### 3. Communications Automation Add-on

Positioning:
- channel-cost recovery layer, not the primary AI price lever

Recommended scope:
- parent notification bundles
- SMS credits or pass-through usage
- WhatsApp delivery where enabled later
- branded notification templates and sending logs

Recommended pricing shape:
- small platform add-on fee plus message credits or pass-through channel cost
- separate communications cost from the AI Employee fee so schools can understand what they are paying for

### What Not To Do Yet

Do not start with:
- per admission reviewed pricing
- per rescue case pricing
- per AI recommendation pricing
- pure success-fee or outcome-based charging for AI labor

Those models can be revisited later, but only after strong trust, stable usage data, and clear ROI evidence exist.

## Why Shortcodes Must Remain

Shortcodes or USSD-compatible rails should remain part of the design because:
- not every parent uses a smartphone app
- not every parent has reliable internet access
- many parents already understand familiar wallet-to-bank or mobile-money menu flows
- schools need a payment path that serves both digitally confident and low-connectivity households

The product should not force a false choice between portal payments and shortcodes.

The target model is:
- portal plus shortcode plus manual fallback
- one reconciliation backend

## Success Metrics

### AI Registrar
- application completion rate
- average time from application to review-ready status
- percentage of applications that need manual back-and-forth for missing documents
- online test completion rate
- admission conversion rate

### AI Bursar
- percentage of payments auto-matched
- time spent per reconciliation exception
- overdue-fee recovery rate
- days-to-collection improvement
- unmatched payment rate

### Parent Layer
- percentage of parents completing admission without a first physical visit
- percentage of parents using self-service payments
- split between bank app, shortcode, and manual fallback usage
- support requests per 100 parent journeys

## Future-Only Items

These should be documented, but not treated as immediate build requirements:
- fully autonomous admission approval
- multilingual voice bots that call or guide parents directly
- one DVA per student plus one DVA per fee type layered together by default
- autonomous collections contact without school approval
- pure outcome-based monetization before sufficient baseline data exists
- predictive dropout automation with autonomous interventions

Commercially future-only:
- per-task billing for AI Employees
- pure outcome-based charging for collections or admissions conversion
- automatic unreviewed parent messaging at scale without school-controlled rules

## Recommended Rollout Sequence

### Phase 1
- AI Registrar MVP
- parent admission form and document upload
- school review queue

### Phase 2
- parent payment layer
- stable payment identity strategy
- shortcode and bank-app instruction unification

### Phase 3
- AI Bursar workflows
- payment stress flags
- collections and payment-plan decision support

### Phase 4
- broader parent portal features
- richer family status visibility
- carefully selected automation upgrades

## Decision Rule

When deciding whether to build a new AI Employee feature now, ask:

1. Does it remove real labor from school staff?
2. Can the school still review or override important decisions?
3. Will it work for both online and low-connectivity households in Ghana?
4. Can it be audited and explained later?

If the answer is no to any of these, it should probably stay in the future-only bucket.