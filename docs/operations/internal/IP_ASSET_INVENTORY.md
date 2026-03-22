# EduPulse SMT IP Asset Inventory

## Purpose

This document identifies the main intellectual-property and confidential-know-how assets visible from the EduPulse SMT repository and operating model. It is intended to support legal review, incorporation, internal ownership clarity, and confidentiality drafting.

This is not a patentability opinion or legal conclusion. It is a technical asset inventory for counsel.

## Business Name

**EduPulse SMT**

## Asset Categories

The most relevant IP categories here are:

1. Copyright in source code, documentation, designs, and templates
2. Trade secrets and confidential know-how in system workflows and controls
3. Brand assets and naming
4. Contractual protection of methods, implementation detail, and operating playbooks

## Core Asset Inventory

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

## High-Value Trade Secret Candidates

The strongest trade-secret candidates appear to be:

1. The school-by-school Paystack route architecture by fee type
2. The routing-mismatch rule where the actual route used can override a reference hint
3. The reconciliation sweep and missing-payment recovery design
4. The dual use of encrypted fields plus tamper-evident finance ledgering
5. The role-gated separation between recording, approval, audit review, and proprietor oversight
6. The full operations layer that connects onboarding, billing, launch, support, incidents, and renewal management

These are more defensible as confidential know-how than individual generic features like attendance or grading screens.

## Repository Evidence Points

The following files are strong evidence points for counsel:

- `backend/routes.py`
  Payment initialization, Paystack webhook handling, route creation, reconciliation, and control logic.
- `backend/api/models.py`
  Paystack route-account model, ledger-entry model, and encrypted data fields.
- `backend/security/crypto.py`
  Application-layer encryption implementation.
- `backend/paystack_integration.py`
  Subscription payment initialization, verification, and charge flows.
- `AUDIT_INTEGRITY_SYSTEM.md`
  Finance-ledger integrity model.
- `SECURITY.md`
  Security posture and deployment controls.
- `docs/operations/internal/STANDARD_OPERATING_PROCEDURES.md`
  Formal business operations layer.
- `docs/operations/internal/LAWYER_TECHNICAL_SYSTEM_SUMMARY.md`
  Lawyer-facing system description.

## Ownership And Contract Recommendations

Counsel should consider ensuring the following are clearly covered in contracts:

1. All source code, system architecture, documentation, templates, and operating materials belong to EduPulse SMT or its founder entity
2. Employees and contractors assign inventions, improvements, and derivative work to the business
3. Payment-routing logic, reconciliation logic, ledger logic, pricing logic, and implementation playbooks are expressly confidential
4. Partners and schools receive limited use rights only, not ownership of the platform or underlying methods
5. Reverse engineering, workflow copying, and derivative commercial use are expressly prohibited where legally appropriate

## Brand And Documentation Assets

The following should also be treated as protectable business assets:

1. The EduPulse SMT name and presentation identity
2. Launch packet materials and rollout documentation
3. School implementation guides and onboarding templates
4. Incident and support communication frameworks

These may be less technical than code, but they still reflect business methods and authored material that should remain controlled.

## Practical Legal Questions

Counsel should review:

1. Whether trademark registration or name protection should be pursued for EduPulse SMT
2. Whether all contributors have signed enforceable IP assignment and confidentiality terms
3. Whether the terms of service and school contracts adequately reserve all platform IP rights
4. Whether the most valuable workflow logic should be protected primarily as trade secret rather than publicly described in excessive detail

## Short Position

The most valuable legal assets in EduPulse SMT are not only the code files themselves, but the combined business method embodied in:

1. Multi-tenant school governance logic
2. Paystack routing and reconciliation control
3. Tamper-evident finance ledgering
4. Security and data-protection implementation choices
5. Operations playbooks that make the platform repeatable as a business