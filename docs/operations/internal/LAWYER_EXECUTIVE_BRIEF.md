# EduPulse SMT Executive Brief For Counsel

## Purpose

This is the short executive version of the technical system summary for legal counsel reviewing EduPulse SMT for incorporation, IP structuring, contracts, and Ghana data-protection positioning.

## Business Name

**EduPulse SMT**

SMT means **Smart School Management Technology**.

## What EduPulse SMT Is

EduPulse SMT is a multi-tenant SaaS platform for schools in Ghana. It combines:

1. School operations
2. Student and academic workflows
3. Payment and billing workflows
4. Parent admissions and communication workflows
5. Proprietor oversight and governance
6. Audit and security controls

It should be understood legally as more than a generic school app. It is an operating system for school workflow control, payment governance, and audit visibility.

## Why This Matters Legally

Counsel should treat the platform as containing at least four legally important layers:

1. Proprietary workflow design
2. Proprietary payment-routing and reconciliation logic
3. Confidential security and control architecture
4. Regulated personal-data handling for schools, parents, guardians, staff, and billing contacts

## The Core Proprietary Value

The strongest proprietary elements appear to be:

1. Multi-tenant school-control architecture
2. Role-gated workflow and approval logic
3. Structured-reference payment categorization and reconciliation logic
4. Reconciliation and recovery logic for missing payment writes
5. Tamper-evident ledgering for finance records
6. Report-card parsing and academic-intelligence workflows
7. Combined use of encryption, audit logging, and routing controls inside one school operations platform

These are stronger candidates for trade-secret and confidential-know-how protection than a simple claim to generic school software features.

## Paystack Positioning

EduPulse SMT uses Paystack in two main ways:

1. For school subscription and plan payments
2. For school fee collection using structured references and school payment rules

The payment-classification design is especially important. The active model uses structured references, stable learner payment identity, and reconciliation logic to classify incoming payments and preserve audit context. Legacy route metadata may still appear in older records, but it is no longer the active setup model.

For counsel, the main point is that the system contains a structured payment-control and categorization architecture, not merely a generic payment button.

## Cryptography Positioning

EduPulse SMT uses cryptography in two distinct ways:

1. Application-layer encryption for sensitive stored values such as parent contacts and saved bank details
2. HMAC-based tamper-evident chaining for finance ledger entries

In the documented AWS production posture, the software is also designed to use managed secrets and encrypted infrastructure controls, including AWS Secrets Manager and encrypted backup/storage recommendations.

## Ghana Data-Protection Positioning

The system processes personal data relating to students, guardians, staff, school operators, and billing records. Its documented controls include:

1. Role-based access control
2. Tenant isolation
3. Encryption in transit
4. Application-layer encryption of selected sensitive fields
5. Audit logging and incident response planning
6. Retention and deletion policy structure
7. Structured handling of admissions, report-card, and external examination records
8. Planned de-identification and aggregation controls for multi-school benchmarking and educational trend analysis

This gives counsel a concrete technical basis for privacy-policy drafting, processor/controller positioning, and regulator-facing explanations.

## Immediate Legal Uses

This brief should help counsel with:

1. Business incorporation framing for EduPulse SMT
2. IP ownership and confidentiality clauses
3. Contractor and employee invention/confidentiality language
4. Platform terms, privacy, and data-processing language
5. Ghana data-protection structuring for school, parent, and student data
6. Advice on anonymized benchmarking and educational research clauses
7. Advice on data-processing or registration application materials where required

## Recommended Counsel Focus

Counsel should pay closest attention to:

1. Ownership of the system design and workflow architecture
2. Protection of the payment categorization and payment-control logic
3. Confidentiality obligations for developers, contractors, and partners
4. Data-protection roles between EduPulse SMT and each school
5. Contract language governing school data, audit records, payment evidence, and de-identified analytics outputs
6. Whether the planned anonymization and aggregation workflow is sufficiently disclosed and supportable for Ghana DPC-facing materials