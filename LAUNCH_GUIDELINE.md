# EduPulse Launch Guideline (Ghana)

Effective Date: February 22, 2026

This document outlines the steps to launch EduPulse into production. Use it as a checklist and execution plan.

---

## Phase 1: Legal and Compliance (Ghana)

- [ ] Register company with Registrar-General's Department (RGD).
- [ ] Register with the Data Protection Commission (DPC) as data controller/processor.
- [ ] Finalize legal documents:
  - [ ] Privacy Policy
  - [ ] Terms of Service
  - [ ] Data Processing Agreement (DPA)
  - [ ] Data Retention Policy
  - [ ] Incident Response Plan
- [ ] Sign sub-processor agreements (hosting, email, payment providers).
- [ ] School contract template reviewed by counsel.
- [ ] Configure in-app acceptance for Terms of Service and Privacy Policy at sign-up.

---

## Phase 2: Security and Infrastructure

- [ ] Select hosting provider and region.
- [ ] Configure production domain and DNS.
- [ ] Enforce HTTPS only (TLS certificates, HSTS).
- [ ] Private database networking and firewall rules.
- [ ] Secrets management (no secrets in repo).
- [ ] Database backups (daily + weekly) and restore test.
- [ ] Encryption at rest (database storage encryption or field-level for PII).
- [ ] Monitoring and alerting (uptime, error rates, auth failures).
- [ ] Audit logging enabled for critical actions.
- [ ] Rate limiting enabled for auth and API endpoints.
- [ ] Storage-level encryption enabled (AWS example):
  - [ ] RDS: Enable storage encryption with KMS.
  - [ ] EBS: Enable default encryption for volumes.
  - [ ] S3: Default bucket encryption enabled (SSE-S3 or SSE-KMS).
- [ ] Run migrations with ALEMBIC_RUNNING=1 to prevent auto create_all.

---

## Phase 3: Payments (Paystack)

- [ ] Paystack business verification completed.
- [ ] Live keys stored in secrets manager.
- [ ] Webhook signature verification implemented.
- [ ] Idempotency keys enforced for payment events.
- [ ] Reconciliation flow and reporting checked.
- [ ] Sandbox-to-live separation validated.

---

## Phase 4: QA and Pilot

- [ ] Full regression test suite executed.
- [ ] Security verification (tenant isolation, access control, rate limits).
- [ ] Pilot run with 1-2 schools for 2-4 weeks.
- [ ] Collect feedback and fix high-priority issues.
- [ ] Staff onboarding training materials finalized.

---

## Onboarding Checklist (Operations)

- [ ] Confirm in-app terms acceptance is enforced at sign-up.
- [ ] Send contract addendum only if custom terms are required.
- [ ] Confirm authorized signatory and billing contact.
- [ ] Gather school branding assets (logo, colors).
- [ ] Collect initial data import needs and format.
- [ ] Schedule admin training session and support channel setup.

---

## Phase 5: Go-Live Execution

- [ ] Production deploy (tagged release).
- [ ] SSL/TLS confirmed in production.
- [ ] Monitoring dashboards live.
- [ ] Backups verified.
- [ ] Public launch communication sent.
- [ ] Support channel active (email/phone/whatsapp).

---

## Phase 6: Post-Launch Operations

- [ ] Weekly stability review for first month.
- [ ] Monthly security review.
- [ ] Quarterly compliance review.
- [ ] Patch management and dependency updates.
- [ ] Roadmap planning and user feedback cycle.

---

## Recommended Owners

- Legal + Compliance: Founder / Legal Counsel
- Infrastructure + Security: DevOps / Backend Lead
- Payments: Backend Lead
- QA + Pilot: Product / QA Lead
- Launch Comms + Support: Operations

---

## Launch Readiness Gate

Proceed to production only when:
- Legal registration complete and DPC registration approved.
- HTTPS, backups, and monitoring are active.
- Payment flow verified in live mode.
- Pilot feedback resolved.

---

## In-App Terms Acceptance (UX + Audit)

- [ ] Show Terms of Service and Privacy Policy links on sign-up.
- [ ] Require an unchecked-by-default checkbox to accept.
- [ ] Log acceptance timestamp, user ID, and IP address.
- [ ] Store the terms version accepted (e.g., version or effective date).
- [ ] Block account creation if acceptance is not given.

## Notes

- Start small to control cost and risk.
- Keep a rollback plan for every release.
- Document all incidents and fixes.
- For migrations: use `FLASK_ENV=testing ALEMBIC_RUNNING=1 alembic upgrade head`.
