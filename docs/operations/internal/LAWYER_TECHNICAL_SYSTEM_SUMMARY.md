# EduPulse SMT Technical System Summary For Counsel

## Purpose

This document is a lawyer-facing technical summary of how EduPulse SMT operates as a business and software system. It is written to support business incorporation, intellectual-property positioning, contract drafting, and Ghana data-protection analysis.

It focuses especially on:

1. The overall operating model of EduPulse SMT
2. How Paystack routing and split-style payment handling work
3. How external KYB provider screening is used for school verification and compliance gating
4. How cryptography is used inside the application and in the documented AWS production architecture
4. Which parts appear to be proprietary workflow and control logic

## Companion Counsel Docs

Use these together with this summary:

1. `LAWYER_EXECUTIVE_BRIEF.md` for the shortest counsel-ready overview
2. `IP_ASSET_INVENTORY.md` for the main protectable-asset inventory
3. `GHANA_DATA_PROTECTION_TECHNICAL_BRIEF.md` for the privacy and compliance control mapping

## Business Name

The business name used in this system documentation is:

**EduPulse SMT**

Where relevant, `SMT` refers to **Smart School Management Technology**.

## Ready-To-Send Email Draft

Subject: EduPulse SMT Technical Summary for Incorporation, IP, and Data Protection Review

Hello Counsel,

I am sharing a technical summary of EduPulse SMT so you can understand how the platform operates and how its payment, security, and data-protection architecture work in practice.

The main reasons for sharing this are:

1. To help you frame the business correctly during incorporation
2. To identify which technical workflows may be protectable as intellectual property, trade secrets, know-how, or contractual confidential information
3. To support data-protection structuring for Ghana, especially around payment handling, student/guardian data, audit trails, and encryption controls

Please pay particular attention to:

1. The Paystack payment-routing and split-style design
2. The cryptographic controls used for sensitive data and ledger integrity
3. The multi-tenant school architecture and role-based controls
4. The parts of the workflow that may be stronger candidates for confidentiality protection, software licensing language, or internal control language in policy documents

I have included a detailed technical summary below.

Best regards,
Daniel Asare Anyinam
EduPulse SMT

## Executive Summary

EduPulse SMT is a multi-tenant SaaS platform for basic schools in Ghana. Each school operates as a logically separated tenant inside one platform. The system combines:

1. Academic operations
2. Payment and fee oversight
3. Subscription billing and school-plan management
4. Proprietor visibility and governance controls
5. Audit logging and tamper-evident ledgering

From a legal and IP perspective, the platform is not only a school-management application. It is a coordinated operating system for school workflows with a strong emphasis on:

1. Role-gated control flows
2. Payment verification and routing
3. External KYB-driven school verification with automatic outcomes and exception handling
4. Tenant isolation
5. Tamper-evident financial records
6. Encrypted storage of sensitive personal and banking data

## System Operation Overview

### 1. Multi-Tenant Model

The platform is designed so that each school is treated as a separate tenant identified by a school ID. The system uses tenant guards and role-based controls so one school should not access another school's data.

In practical terms, EduPulse SMT supports:

1. Separate school organizations
2. School-specific branding and settings
3. School-specific financial records
4. School-specific payment routing
5. School-specific users and permissions

### 2. Main User Roles

The platform recognizes multiple user roles, including:

1. Proprietor
2. Headmaster
3. Teacher
4. Finance
5. Admin

These roles matter legally because the software encodes separation-of-duty rules. For example, certain financial actions are intentionally separated between recording and approval to reduce fraud risk and strengthen audit defensibility.

### 3. Core Functional Areas

EduPulse SMT combines several functions in one operating environment:

1. Student records and attendance
2. Grades, report generation, and approvals
3. School billing and plan management
4. Parent/guardian-linked payment flows
5. Proprietor monitoring and governance
6. Internal audit and ledger verification

## End-To-End Operational Flow

At a high level, the system operates as follows:

1. A school registers and selects a plan
2. If the plan is paid, the system initializes Paystack payment
3. Once payment is verified, the school subscription is activated
4. The proprietor can submit school verification details for external KYB screening
5. Clean KYB outcomes auto-verify while flagged outcomes route to review-required status
6. School users log in under role-based access controls
7. Staff carry out academic and finance workflows
8. Certain finance events create ledger entries that are cryptographically chained
9. Sensitive data is encrypted at the application layer before being stored
10. In production, the documented AWS deployment posture injects secrets through managed secret storage and recommends encrypted storage and backups

This combination of payments, tenant separation, approval flow, and tamper-evident finance records is one of the strongest parts of the system from an IP and compliance standpoint.

## Paystack Architecture

## 1. Two Distinct Payment Contexts

EduPulse SMT uses Paystack in at least two important contexts:

1. Subscription and plan payments for schools themselves
2. Fee-collection routing for school-specific payments such as tuition, feeding, uniform, transport, and similar categories

These are related but not identical.

### A. School Subscription Payments

When a school chooses a paid plan, the system initializes a Paystack transaction and redirects the school to Paystack checkout. After Paystack confirms success, the platform activates the school's subscription.

The system also keeps payment references and reconciliation logic so successful payments that fail to write locally can later be recovered.

### B. School Fee Routing By Payment Type

For school operations, the system supports Paystack fee-route accounts by payment type. The relevant model describes one route per payment type per school. The operational idea is:

1. One school has one underlying real settlement account registered with Paystack
2. The platform creates separate virtual payment routes for payment categories such as Tuition or Feeding
3. Parents or payers use the route associated with that fee type
4. When Paystack sends the webhook, the route code tells the system which fee category was actually paid
5. The webhook route is treated as authoritative if it conflicts with the original reference hint

This is commercially important because it lets the platform automate payment classification while keeping settlement attached to the school-level account structure.

## 2. What “Paystack Split” Means In This System

In EduPulse SMT, the Paystack “split” idea is used in a practical routing-and-settlement sense rather than only as generic marketing language.

The relevant implementation concepts are:

1. A school can have a Paystack route account record for each payment type
2. The route record stores a `subaccount_code` or dedicated virtual route identifier
3. Payment initialization can include this route code during transaction initialization
4. The webhook reads the `subaccount` information in the Paystack payload
5. Settlement metadata such as settlement amount and subaccount share are written into ledger metadata

This means the software is not merely collecting one undifferentiated payment stream. It is using Paystack route metadata to classify school payments automatically and to preserve settlement context inside the platform's finance trail.

## 3. Paystack Fee Route Account Logic

The platform stores route-account records with fields such as:

1. School ID
2. Payment type
3. Route or subaccount code
4. Business name for the route
5. Virtual bank account details
6. Mobile-money provider information
7. Percentage charge metadata

This creates a configurable school-by-school payment-routing layer. That layer is one of the clearest examples of proprietary business workflow encoded as software.

## 4. Paystack Checkout Initialization

When EduPulse SMT initializes a payment, it generates:

1. A unique reference
2. The payer email
3. The amount in pesewas
4. School and student metadata
5. Payment-type metadata
6. A callback URL

If a school has a route code for the payment type, that route code is added to the Paystack payload. The code comments describe this as an automatic split to the school's designated subaccount based on payment type.

## 5. Webhook Security

Paystack webhooks are protected using HMAC SHA-512 signature verification against the raw request body and the Paystack secret key.

That matters legally because it shows the system is not blindly trusting external payment callbacks. It cryptographically verifies that the callback originated from an entity holding the shared Paystack secret context.

## 6. Payment Idempotency And Duplicate Prevention

Before writing a Paystack finance payment, the system checks whether a payment with the same reference already exists. If so, it returns a duplicate outcome instead of recording the payment again.

This is important from a compliance and accounting perspective because it reduces the risk of duplicate posting caused by repeated webhook delivery or reconciliation replay.

## 7. Reconciliation And Recovery

EduPulse SMT also includes reconciliation logic that can fetch successful Paystack transactions over a lookback window and recover transactions that succeeded at Paystack but were not fully recorded locally.

This is operationally important because it shows the platform is engineered not only for happy-path payment success, but also for failure recovery and ledger completeness.

## Cryptography And Data Protection Architecture

## 1. Application-Layer Encryption Of Sensitive Fields

The platform defines an `EncryptedString` type backed by the Python `cryptography` library's `Fernet` implementation.

In production:

1. The application requires a `DATA_ENCRYPTION_KEY`
2. Startup is blocked if that key is missing
3. Values are encrypted before being written to the database
4. Values are decrypted when read back through the ORM

This means certain sensitive fields are protected at the application layer even before considering disk encryption.

## 2. Which Data Is Encrypted In The Application

The current models show encryption being applied to data such as:

1. Saved bank details
2. Certain school email fields
3. Guardian and parent names
4. Parent phone numbers
5. Parent email addresses

This matters for Ghana data protection because the platform handles personal data relating to students, guardians, school staff, and school finance.

## 3. Tamper-Evident Financial Ledger

Separate from field encryption, the platform uses a cryptographic ledger chain for financial records.

The ledger design works as follows:

1. Each confirmed finance event becomes a ledger entry
2. Each entry includes the previous hash
3. A new HMAC-SHA256 hash is computed over the entry payload plus the previous hash
4. The chain starts from a genesis value if no prior entry exists
5. If any stored finance record is altered later, the verification chain can reveal the tampering

The ledger uses a dedicated `LEDGER_SECRET_KEY`, and production startup is blocked if that key is missing.

From an IP and legal perspective, this is not just general logging. It is a structured tamper-evident finance-control mechanism that strengthens trust, internal controls, and forensic defensibility.

## 4. Separation Between Encryption And Integrity

It is important to distinguish two different cryptographic uses:

1. **Encryption** protects confidentiality of sensitive stored values
2. **HMAC ledger chaining** protects integrity and tamper detection for finance events

These are distinct protections serving different legal and operational functions.

## AWS Production Cryptography And Secret Handling

## 1. What Is Implemented At Application Level Today

The code already enforces the presence of production keys for:

1. `JWT_SECRET_KEY`
2. `DATA_ENCRYPTION_KEY`
3. `LEDGER_SECRET_KEY`

The application is therefore designed to depend on environment-provided secrets in production rather than hardcoded values.

## 2. Documented AWS Deployment Posture

The production deployment documentation describes an AWS-oriented deployment model that uses:

1. ECS task definitions
2. Secret injection from AWS Secrets Manager
3. Encrypted storage recommendations for EBS-backed volumes
4. Encrypted backups to S3 using SSE-KMS

The deployment documentation specifically references Secrets Manager ARNs for critical values such as:

1. Database URL
2. JWT secret
3. Flask secret
4. Mail password

The broader security documentation also recommends:

1. Encrypted EBS volumes
2. Private database exposure only
3. S3 backup encryption using SSE-KMS
4. Restricted IAM access to encrypted storage and secrets

## 3. Legal Meaning Of “AWS Cryptography” In This System

When describing AWS cryptography for counsel, the most accurate formulation is:

1. EduPulse SMT performs **application-layer cryptography** itself for confidential data and tamper-evident ledgering
2. EduPulse SMT is designed to be deployed in an AWS environment where **secret storage and infrastructure encryption** are handled using AWS-managed services and encrypted storage controls
3. The software and the infrastructure therefore work together: the application encrypts data fields and signs ledger chains, while AWS is the recommended secret-hosting and storage-encryption environment in production

That distinction is important so counsel does not overstate which protections come from application code and which come from the cloud environment.

## Proprietary And Potentially Protectable Elements

The strongest candidates for trade-secret, confidential-know-how, contractual confidentiality, or software-licensing protection appear to be:

1. The multi-tenant school-control workflow as a whole
2. The role-gated approval structure across school operations and finance
3. The Paystack fee-route account architecture by payment type per school
4. The routing rule that treats the actual Paystack route used as authoritative in mismatch scenarios
5. The reconciliation-and-recovery logic for missing payment writes
6. The tamper-evident financial ledger design tied to school-specific finance events
7. The combination of encrypted PII storage, audit chaining, and school-specific payment-routing logic in a single Ghana-school operating platform

Any incorporation, employment, contractor, partner, or reseller documents should likely preserve these elements as confidential system design and proprietary implementation know-how.

## Ghana Data Protection Relevance

From a Ghana data-protection perspective, the technically relevant points are:

1. The system processes student, parent, guardian, staff, school-owner, and billing data
2. Sensitive personal and banking fields are encrypted at the application layer
3. Financial actions are logged in a tamper-evident chain
4. Production architecture is designed to avoid hardcoded secrets and instead rely on managed secret injection
5. The system uses role controls and tenant isolation to reduce unauthorized cross-school access
6. Payment verification relies on authenticated gateway callbacks rather than unauthenticated trust

These features do not replace legal compliance, but they provide strong factual support for technical and organizational measures in a Ghana data-protection analysis.

## Counsel Review Questions

The following are useful legal review questions for counsel:

1. Which parts of this payment-routing and control architecture should be treated as trade secret or confidential know-how?
2. How should contractor, employee, and vendor agreements describe ownership of EduPulse SMT workflows, code, payment logic, and data models?
3. Should the incorporation documents or internal governance records explicitly mention that EduPulse SMT operates a multi-tenant school-management and payment-governance platform?
4. What filings, policies, or contractual terms are needed in Ghana to support the handling of student, guardian, and financial data?
5. How should the legal documents distinguish between EduPulse SMT as software vendor and each school as controller or user of school-originated personal data?
6. What contractual language should protect the Paystack routing logic, reconciliation logic, and tamper-evident ledger design from misuse by employees, contractors, or implementation partners?

## Short Technical Positioning Statement

EduPulse SMT is not only a school record system. It is a multi-tenant governance and payment-control platform for schools, combining role-gated academic operations, Paystack-linked fee routing, school subscription billing, encrypted sensitive-data handling, and tamper-evident financial ledgering.

That combined workflow architecture is a central part of the business value and should be treated as a core proprietary asset.