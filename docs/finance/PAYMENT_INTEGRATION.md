# EduPulse SMT Payment Integration Guide

## Scope

EduPulse has two distinct Paystack-backed payment layers:

1. EduPulse's own school-subscription billing
2. school-operated parent and guardian fee collection

This document covers both at a high level and points to the more specific finance docs for the school-fee layer.

## 1. School Subscription Billing

Schools remain the paying SaaS customer for platform access.

Current billing behavior:

- `Free` onboarding completes without Paystack checkout
- `Basic` and `Premium` onboarding initialize Paystack checkout immediately
- successful verification activates the paid entitlement
- direct plan changes are reserved for non-paid transitions such as scheduled downgrades or internal cleanup

Relevant routes:

- `POST /api/finance/paystack/initialize-payment`
- `GET /api/paystack/verify/<reference>`
- `POST /api/paystack/webhook`
- `GET /api/school/subscription/effective-plan`
- `GET /api/school/subscription/billing-visibility`

## 2. School Fee Collection Layer

Parent-fee collection is separate from subscription billing.

Current product logic:

- EduPulse builds learner payment instructions from `GET /api/students/<student_id>/payment-codes`
- schools can enable Paystack tracked transfer accounts per learner fee reference
- printed instructions can auto-attach those tracked transfer accounts
- automatic Paystack tracking is now the primary path for tuition transfers where supported
- visible references remain important for support, manual entry, and non-Paystack fallback paths

### Tuition Collection Modes

EduPulse currently supports two tuition models:

1. one live outstanding tuition route per learner
2. installment-based tuition collection configured in school settings

When installments are enabled:

- the school chooses `2`, `3`, or a custom installment count
- EduPulse can auto-split the schedule equally
- the saved schedule must add up exactly to the tuition fee
- each installment gets its own reference and virtual account route
- statuses move through `upcoming`, `open`, `partial`, `paid`, and `overdue`
- small overpayments can carry forward into the next installment

### Tracked Transfer Logic

For tracked transfer accounts:

- EduPulse creates or reuses a `PaymentCollectionIntent`
- Paystack provides a dedicated virtual account per learner fee route
- the school's fixed fee amount is settled to the school's Paystack subaccount
- the convenience-fee remainder settles to EduPulse's main Paystack account
- only the base school-fee amount reduces the learner's debt inside EduPulse

### Recovery Path

If a Paystack transfer succeeds but the automatic EduPulse record is missing, staff can use:

- `POST /api/finance/paystack/recover-reference`

This is a recovery tool, not the normal workflow.

## Current School Setup Requirements

For tracked transfer accounts to work, a school must:

1. save verified bank details in Settings
2. let EduPulse create the school's Paystack subaccount
3. keep Paystack webhook secrets configured in the platform environment

Without that setup, EduPulse can still show fee references, but it cannot attach a ready tracked transfer account.

## Environment Variables

Typical platform variables:

```bash
PAYSTACK_SECRET_KEY=sk_live_or_test_key
PAYSTACK_PUBLIC_KEY=pk_live_or_test_key
FRONTEND_URL=https://your-frontend-host
BANK_WEBHOOK_SECRET=shared_secret_for_non_paystack_bank_callbacks
```

## Related References

- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/PAYMENT_REFERENCE_CODE_SYSTEM.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `docs/finance/SUBSCRIPTION_BILLING_GUIDE.md`
