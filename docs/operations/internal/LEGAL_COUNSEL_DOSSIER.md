# EduPulse SMT Legal Counsel Dossier

## Purpose

This is the single-file consolidated legal dossier for **EduPulse SMT**. It is intended to give counsel one forwardable document covering:

1. Business framing
2. Whole-system technical operation
3. Paystack routing and split-style payment handling
4. Cryptography and AWS security posture
5. Intellectual-property and confidential-know-how positioning
6. Ghana data-protection technical controls
7. Founder-side legal action priorities
8. Draft internal legal templates for assignment and confidentiality

This document is a practical legal-support dossier, not legal advice.

## Business Name

**EduPulse SMT**

`SMT` means **Smart School Management Technology**.

## Counsel Cover Note

Subject: EduPulse SMT Legal Review Dossier for Incorporation, IP, and Data Protection

Hello Counsel,

I write to share a consolidated legal review dossier for **EduPulse SMT** to support work on:

1. Business incorporation
2. Intellectual-property ownership and protection
3. Confidentiality and contributor controls
4. Ghana data-protection positioning
5. Platform terms and school-facing legal documents

EduPulse SMT is a multi-tenant school SaaS platform with several technical and operational features that I want reflected accurately in the legal work:

1. Paystack-linked payment-routing and split-style fee handling
2. Application-layer encryption of selected sensitive data
3. Tamper-evident finance ledgering using cryptographic chaining
4. Role-gated academic, finance, and approval workflows
5. School-by-school tenant separation and access controls

The principal legal outcomes I need from this review are:

1. Proper legal framing of EduPulse SMT as a business and software asset
2. Strong ownership and confidentiality protection for the code, workflows, and operating materials
3. Clear data-protection positioning under Ghana law
4. Contract language that protects the platform while making school data responsibilities clear
5. Execution-ready contributor assignment and confidentiality forms

I would be grateful if you would pay particular attention to:

1. Which parts of the platform should be treated as confidential know-how or trade-secret-like assets
2. Whether the school contracts and terms should distinguish clearly between EduPulse SMT as platform operator and each school as controller of school-originated personal data
3. Whether stronger employee, contractor, founder, or partner paperwork is needed to secure IP ownership and confidentiality
4. Whether the draft assignment and confidentiality templates in this dossier should be revised into final execution-ready forms

Best regards,
Daniel Asare Anyinam
EduPulse SMT
danielasareanyinam2020@gmail.com

## Executive Brief

### What EduPulse SMT Is

EduPulse SMT is a multi-tenant SaaS platform for schools in Ghana. It combines:

1. School operations
2. Student and academic workflows
3. Payment and billing workflows
4. Proprietor oversight and governance
5. Audit and security controls

It should be understood legally as more than a generic school app. It is an operating system for school workflow control, payment governance, and audit visibility.

### Why This Matters Legally

Counsel should treat the platform as containing at least four legally important layers:

1. Proprietary workflow design
2. Proprietary payment-routing and reconciliation logic
3. Confidential security and control architecture
4. Regulated personal-data handling for schools, parents, guardians, staff, and billing contacts

### The Core Proprietary Value

The strongest proprietary elements appear to be:

1. Multi-tenant school-control architecture
2. Role-gated workflow and approval logic
3. Paystack fee-route handling by payment type per school
4. Reconciliation and recovery logic for missing payment writes
5. Tamper-evident ledgering for finance records
6. Combined use of encryption, audit logging, and routing controls inside one school operations platform

### Paystack Positioning

EduPulse SMT uses Paystack in two main ways:

1. For school subscription and plan payments
2. For school fee-collection routing by payment type

The fee-routing design is especially important. The platform can assign route accounts or virtual payment routes to categories like tuition or feeding, then use Paystack webhook data to identify which route was actually used. This supports automatic payment classification and settlement context preservation.

### Cryptography Positioning

EduPulse SMT uses cryptography in two distinct ways:

1. Application-layer encryption for sensitive stored values such as parent contacts and saved bank details
2. HMAC-based tamper-evident chaining for finance ledger entries

In the documented AWS production posture, the software is also designed to use managed secrets and encrypted infrastructure controls, including AWS Secrets Manager and encrypted backup/storage recommendations.

### Ghana Data-Protection Positioning

The system processes personal data relating to students, guardians, staff, school operators, and billing records. Its documented controls include:

1. Role-based access control
2. Tenant isolation
3. Encryption in transit
4. Application-layer encryption of selected sensitive fields
5. Audit logging and incident response planning
6. Retention and deletion policy structure

## Whole-System Technical Summary

### Platform Model

EduPulse SMT is a multi-tenant SaaS platform for schools in Ghana. Each school operates as a logically separated tenant inside one platform. The system combines:

1. Academic operations
2. Payment and fee oversight
3. Subscription billing and school-plan management
4. Proprietor visibility and governance controls
5. Audit logging and tamper-evident ledgering

### Main Roles

The platform recognizes roles including:

1. Proprietor
2. Headmaster
3. Teacher
4. Finance
5. Admin

These roles matter legally because the software encodes separation-of-duty rules. Certain financial actions are intentionally separated between recording and approval to reduce fraud risk and strengthen audit defensibility.

### End-To-End Operational Flow

At a high level, the system operates as follows:

1. A school registers and selects a plan
2. If the plan is paid, the system initializes Paystack payment
3. Once payment is verified, the school subscription is activated
4. The proprietor can submit school verification details that are screened by an external KYB provider
5. Clean KYB outcomes can auto-verify; flagged outcomes are routed to review-required status for platform compliance decisions
6. School users log in under role-based access controls
7. Staff carry out academic and finance workflows
8. Certain finance events create ledger entries that are cryptographically chained
9. Sensitive data is encrypted at the application layer before being stored
10. In production, the documented AWS deployment posture injects secrets through managed secret storage and recommends encrypted storage and backups

## Paystack Architecture And Split-Style Handling

### Two Distinct Payment Contexts

EduPulse SMT uses Paystack in at least two important contexts:

1. Subscription and plan payments for schools themselves
2. Fee-collection routing for school-specific payments such as tuition, feeding, uniform, transport, and similar categories

### School Subscription Payments

When a school chooses a paid plan, the system initializes a Paystack transaction and redirects the school to Paystack checkout. After Paystack confirms success, the platform activates the school's subscription.

The system also keeps payment references and reconciliation logic so successful payments that fail to write locally can later be recovered.

### School Fee Routing By Payment Type

For school operations, the system supports Paystack fee-route accounts by payment type. The relevant implementation model uses one route per payment type per school. The operating idea is:

1. One school has one underlying real settlement account registered with Paystack
2. The platform creates separate virtual payment routes for categories such as Tuition or Feeding
3. Parents or payers use the route associated with that fee type
4. When Paystack sends the webhook, the route code tells the system which fee category was actually paid
5. The webhook route is treated as authoritative if it conflicts with the original reference hint

### What “Split” Means In This System

In EduPulse SMT, the Paystack “split” idea is used in a practical routing-and-settlement sense. The implementation concepts are:

1. A school can have a route account record for each payment type
2. The route record stores a `subaccount_code` or dedicated virtual route identifier
3. Payment initialization can include this route code during transaction initialization
4. The webhook reads `subaccount` information in the Paystack payload
5. Settlement metadata such as settlement amount and subaccount share are written into ledger metadata

This means the software is not merely collecting one undifferentiated payment stream. It uses route metadata to classify school payments automatically and preserve settlement context inside the finance trail.

### Webhook Security And Idempotency

Paystack webhooks are protected using HMAC SHA-512 signature verification against the raw request body and the Paystack secret key.

Before writing a Paystack finance payment, the system checks whether a payment with the same reference already exists. If so, it returns a duplicate outcome instead of recording the payment again.

### Reconciliation And Recovery

EduPulse SMT includes reconciliation logic that can fetch successful Paystack transactions over a lookback window and recover transactions that succeeded at Paystack but were not fully recorded locally.

## Cryptography And Security Architecture

### Application-Layer Encryption

The platform defines an `EncryptedString` type backed by the Python `cryptography` library's `Fernet` implementation.

In production:

1. The application requires a `DATA_ENCRYPTION_KEY`
2. Startup is blocked if that key is missing
3. Values are encrypted before being written to the database
4. Values are decrypted when read back through the ORM

Sensitive fields shown in current models include:

1. Saved bank details
2. Certain school email fields
3. Guardian and parent names
4. Parent phone numbers
5. Parent email addresses

### Tamper-Evident Financial Ledger

Separate from field encryption, the platform uses a cryptographic ledger chain for financial records:

1. Each confirmed finance event becomes a ledger entry
2. Each entry includes the previous hash
3. A new HMAC-SHA256 hash is computed over the entry payload plus the previous hash
4. The chain starts from a genesis value if no prior entry exists
5. If any stored finance record is altered later, the verification chain can reveal the tampering

The ledger uses a dedicated `LEDGER_SECRET_KEY`, and production startup is blocked if that key is missing.

### AWS Production Posture

The documented production deployment describes an AWS-oriented model that uses:

1. ECS task definitions
2. Secret injection from AWS Secrets Manager
3. Encrypted storage recommendations for EBS-backed volumes
4. Encrypted backups to S3 using SSE-KMS

The legal meaning is that EduPulse SMT performs application-layer cryptography itself while AWS is the recommended environment for secret storage and encrypted infrastructure controls.

## IP Asset Inventory

### Asset Categories

The most relevant IP categories here are:

1. Copyright in source code, documentation, designs, and templates
2. Trade secrets and confidential know-how in system workflows and controls
3. Brand assets and naming
4. Contractual protection of methods, implementation detail, and operating playbooks

### Core Asset Inventory

| Asset | Description | Likely Protection Type | Why It Matters |
| --- | --- | --- | --- |
| Multi-tenant school architecture | Tenant-specific school scoping, role controls, and operational separation | Trade secret, copyright, confidential know-how | Core system structure for serving many schools in one platform |
| Role-gated workflow engine | Proprietor, headmaster, teacher, finance, admin workflow separation | Trade secret, confidential know-how | Encodes governance logic and internal-control design |
| Paystack fee-route architecture | School-specific payment routing by fee type using Paystack route/subaccount metadata | Trade secret, confidential know-how, copyright in code | Differentiates fee collection and payment classification |
| Reconciliation recovery logic | Recovery of successful gateway payments not fully recorded locally | Trade secret, confidential know-how | Protects revenue integrity and operational reliability |
| Tamper-evident finance ledger | HMAC-chained ledger entries and verification logic | Trade secret, confidential know-how, copyright in implementation | Strong compliance and audit differentiator |
| Application-layer encrypted fields | ORM-backed encrypted storage of sensitive values | Copyright in implementation, confidential security know-how | Protects personal and banking data |
| Subscription and metering logic | Plan selection, plan state, overage, trial, downgrade handling | Trade secret, copyright, confidential know-how | Commercial model embedded in code |
| Academic approval workflows | Report staging, approval, and governance loops | Trade secret, copyright, confidential know-how | Part of the control-layer value proposition |
| Operations documentation system | SOPs, launch packets, handoff docs, incident templates, onboarding playbooks | Copyright, confidential business know-how | Turns software into a repeatable operating business |
| Brand and product naming | EduPulse SMT name and presentation materials | Trademark/brand, copyright in materials | Customer and legal identity |

### High-Value Trade Secret Candidates

The strongest trade-secret candidates appear to be:

1. The school-by-school Paystack route architecture by fee type
2. The routing-mismatch rule where the actual route used can override a reference hint
3. The reconciliation sweep and missing-payment recovery design
4. The dual use of encrypted fields plus tamper-evident finance ledgering
5. The role-gated separation between recording, approval, audit review, and proprietor oversight
6. The full operations layer that connects onboarding, billing, launch, support, incidents, and renewal management

## Ghana Data Protection Technical Brief

### Scope Of Data Processed

The platform processes data relating to:

1. Students
2. Parents and guardians
3. School staff and operators
4. Proprietors and school administrators
5. Billing and payment records
6. Security, authentication, and audit events

### Role Positioning: School vs Platform

The existing privacy documentation points to this distinction:

1. Each school is the primary controller of school-originated student and guardian data in its operational context
2. EduPulse SMT acts as the platform operator and processor/service provider for those schools in many processing activities

### Technical Controls Currently Evident

1. Role-based access control
2. School/tenant isolation
3. Restricted access to sensitive finance and audit functions
4. TLS encryption in transit
5. Application-layer encryption at rest for selected sensitive fields
6. HMAC-SHA256 tamper-evident logging for finance records
7. HMAC SHA-512 verification of Paystack webhook events
8. External KYB provider integration with explicit verified/review-required outcomes and audit logging
9. Secrets management and production hardening
10. Incident and breach handling documentation
11. Retention, deletion, and DSAR workflow documentation

### Practical Risk Areas To Review

1. Placeholder legal fields still awaiting formal company registration details or address information
2. Whether all high-risk data flows have matching contractual language
3. Whether school-side user behavior could still cause improper data entry or disclosure despite platform controls
4. Whether internal roles and named owners are formalized in corporate documents, not only operating docs

## Founder IP And Confidentiality Checklist

### Immediate Priorities

1. Confirm the legal entity name to be used for ownership of the platform
2. Confirm whether EduPulse SMT will be registered personally first or through a formal company entity immediately
3. Ensure all code created personally is clearly attributable to you or the business entity
4. Confirm there is no contributor code in the repo without written ownership or assignment terms
5. Put invention-assignment language in every developer or contractor agreement
6. Put confidentiality clauses in every contractor or collaborator agreement
7. Ensure contracts say schools own their school data and EduPulse SMT owns the platform, code, workflows, and materials
8. Preserve repository history, screenshots, architecture notes, and dated packet docs as evidence

### Strongest Assets To Protect First

If time is limited, prioritize legal protection around:

1. Multi-tenant school-control architecture
2. Paystack fee-route and reconciliation logic
3. Tamper-evident financial ledger design
4. Security and encrypted-data handling design
5. Operations playbooks and school rollout materials

## Draft Template 1: Contributor IP Assignment

### Purpose

This is a draft internal template for assigning intellectual-property rights in work created for EduPulse SMT.

### Draft Form

**Contributor Intellectual Property Assignment Agreement**

This Contributor Intellectual Property Assignment Agreement is made on [Date] between:

1. **EduPulse SMT / [Registered Entity Name]**, of [Address] (the "Company")
2. **[Contributor Full Name]**, of [Address] (the "Contributor")

The Contributor irrevocably assigns to the Company, with full title guarantee, all present and future right, title, and interest in and to the Work Product and all associated Intellectual Property Rights, to the fullest extent permitted by law.

For this purpose, **Work Product** means all software code, source files, scripts, database models, APIs, technical designs, prompts, documents, templates, playbooks, specifications, business methods, visual materials, communications materials, and derivative works created, authored, modified, or contributed by the Contributor in connection with EduPulse SMT.

The Contributor also agrees:

1. To sign further documents reasonably needed to confirm ownership
2. To disclose any pre-existing materials before using them
3. To keep EduPulse SMT confidential information confidential
4. Not to assert moral rights against the Company to the extent permitted by law

## Draft Template 2: Confidentiality And NDA

### Purpose

This is a draft confidentiality and non-disclosure template for contributors, advisors, contractors, prospective partners, or other parties given access to EduPulse SMT confidential information.

### Draft Form

**Confidentiality and Non-Disclosure Agreement**

This Confidentiality and Non-Disclosure Agreement is made on [Date] between:

1. **EduPulse SMT / [Registered Entity Name]**, of [Address] (the "Disclosing Party")
2. **[Recipient Full Name or Entity]**, of [Address] (the "Receiving Party")

Confidential Information includes all non-public information relating to EduPulse SMT, including source code, software architecture, product roadmap, payment-routing and reconciliation logic, Paystack route-account structures, cryptographic controls, operations playbooks, onboarding materials, incident templates, pricing and commercial strategy, technical know-how, and draft legal materials.

The Receiving Party agrees:

1. To use Confidential Information only for the permitted purpose
2. To keep it strictly confidential
3. Not to copy, disclose, publish, reverse engineer, or exploit it except as authorized in writing
4. To limit access to those who genuinely need to know and who are bound by equivalent confidentiality obligations
5. To return or destroy the information on request or at the end of the relationship, subject to legal retention obligations

## Repository Evidence Points

The strongest evidence files supporting this dossier include:

1. `backend/routes.py`
2. `backend/api/models.py`
3. `backend/security/crypto.py`
4. `backend/paystack_integration.py`
5. `AUDIT_INTEGRITY_SYSTEM.md`
6. `SECURITY.md`
7. `compliance/PRIVACY_POLICY.md`
8. `compliance/DATA_RETENTION_POLICY.md`
9. `compliance/INCIDENT_RESPONSE_PLAN.md`
10. `docs/operations/internal/STANDARD_OPERATING_PROCEDURES.md`

## Recommended Counsel Questions

1. What is the best legal framing for EduPulse SMT as a business entity and software product?
2. Which system elements should be explicitly reserved as IP, confidential information, or trade-secret-like know-how?
3. What contributor, employee, contractor, and partner agreements are needed to ensure ownership remains with EduPulse SMT?
4. How should Ghana data-protection roles be described between EduPulse SMT and each school?
5. What terms should govern customer data ownership, software ownership, audit evidence, and misuse restrictions?
6. Should the included draft assignment and NDA templates be refined into final execution versions for immediate use?

## Recommended Use

Use this dossier when you want one single document to forward to counsel without sending a multi-file packet first. For working edits and modular review, the separate files in `docs/operations/internal/` remain the canonical breakdown.