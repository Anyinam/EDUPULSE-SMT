# EduPulse SMT Docs Map

## Purpose

This folder is the canonical home for EduPulse SMT documentation grouped by topic and audience.

Most root-level markdown files now remain only as redirect stubs for older references. New edits should be made in the canonical files under `docs/` or `compliance/`.

## Top-Level Structure

- `academics/`
  Academic workflows, report builders, admissions flows, timetable docs, and classroom implementation notes.
- `ai/`
  AI strategy and AI-powered product workflow documents.
- `branding/`
  Logo and brand integration materials.
- `finance/`
  Billing, payments, pricing mechanics, and subscription documentation.
- `operations/`
  Internal and customer-facing operating materials.
- `platform/`
  Platform setup, implementation, deployment, reliability, and console docs.
- `security/`
  Security, firewall, production hardening, and audit integrity docs.
- `strategy/`
  Product strategy, pitch, business model, roadmap, and milestone documents.
- `testing/`
  Testing setup, summaries, execution reports, and quick-start validation docs.

## Legal And Compliance

Legal and privacy documents remain under `compliance/` and lawyer-facing operational materials remain under `docs/operations/internal/`.

## Core References

- `operations/README.md`
- `operations/internal/README.md`
- `operations/customer/README.md`
- `platform/SETUP.md`
- `security/SECURITY.md`
- `finance/PAYMENT_INTEGRATION.md`
- `academics/REPORT_BUILDER_GUIDE.md`
- `testing/TESTING_INDEX.md`

## Recent September 2026 Updates

- Finance docs now reflect the current tracked-transfer model, including Paystack dedicated virtual accounts, automatic webhook matching, reconciliation fallback, and split-settlement behavior.
- Tuition installment documentation now covers `2`, `3`, and custom schedules, per-installment references such as `STUDENT-TUIT-I1`, live installment statuses, and exact-total validation rules.
- Payment reference docs now explain the mixed model of readable structured references for newer flows and legacy compact fee codes that remain active for backward compatibility.
- Billing and subscription behavior continues to be summarized in `finance/SUBSCRIPTION_BILLING_GUIDE.md`, while the broader payment-layer overview now lives in `finance/PAYMENT_INTEGRATION.md`.
