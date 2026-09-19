# Payment Reference Format Guide

## Purpose

EduPulse uses payment references to answer two questions:

- which learner is this payment for?
- what fee purpose or installment does the payment belong to?

The system now uses a hybrid reference model. Some fees still use legacy compact references generated from `backend/utils.py`, while newer fee flows emit readable structured references directly from the payment-instruction layer.

## Current Reference Families

### 1. Tuition installment references

When a school enables tuition installments in Settings, EduPulse emits one tuition reference per installment:

- `S001-TUIT-I1`
- `S001-TUIT-I2`
- `S001-TUIT-I3`

Each installment reference is tied to:

- an exact installment amount
- a start date
- a deadline
- a live installment status such as `upcoming`, `open`, `partial`, `paid`, or `overdue`

### 2. Structured feeding references

When a school configures feeding by plan, EduPulse emits readable feeding references:

- `S001-FEED-DAY`
- `S001-FEED-WEK`
- `S001-FEED-MON`

These references tell EduPulse which feeding plan the payment belongs to.

### 3. Legacy compact references

Classic non-installment tuition, uniform, transport, and most custom fees still rely on the legacy compact code generator in `backend/utils.py`.

Examples:

- `CFK011` for the learner's tuition route when the school is not using tuition installments
- `CFK013` for uniform
- `CFK014` for transport

Custom fees continue from the next numeric suffix.

This means the payment-code payload a school sees today can contain both:

- structured references for newer fee models
- compact references for older fee families that have not yet been migrated to readable suffixes

## What The Reference Controls

Regardless of format, the reference still drives EduPulse's categorization logic.

Examples:

| Reference | Meaning |
|-----------|---------|
| `S001-TUIT-I1` | Tuition installment 1 |
| `S001-FEED-MON` | Feeding with `{"frequency": "Monthly"}` |
| `CFK011` | Legacy tuition route for learner `CFK01` |
| `CFK013` | Legacy uniform route for learner `CFK01` |

The reference can be used in two different ways:

- as the main matching key for manual entry, office confirmation, and some webhook paths
- as a support hint when a Paystack tracked transfer account already identifies the learner and fee route automatically

## Current Parent Payment Experience

EduPulse now prioritizes Paystack tracked transfer accounts for dependable automatic tuition tracking.

Parent instructions can be delivered in these modes:

1. Printed or copied tracked-transfer instructions with bank name, account number, exact amount, and the preferred reference
2. Direct school-office or ordinary-bank instructions where the parent must include the reference manually
3. Optional online checkout in flows that still use Paystack checkout, such as subscription billing or public admission payment flows

When a tracked transfer account is available:

- the dedicated virtual account is already bound to one learner fee route
- EduPulse expects Paystack to identify the route automatically from the prepared account
- the visible reference becomes a preferred support hint rather than the normal tracking requirement

## Installment Logic

Tuition installments are configured from the school Settings panel.

Current rules:

- the school chooses `2`, `3`, or a custom installment count
- EduPulse can auto-split the tuition equally
- staff can edit the label, amount, start date, and deadline of each installment
- the saved schedule must add up exactly to the tuition fee
- every installment gets its own payment route and reference
- small overpayments can carry forward as credit into the next installment

## Automatic Tracking Rules

### Tracked transfer account path

For reliable automation, the school should use the EduPulse-generated tracked transfer account.

That path stores a `PaymentCollectionIntent` and lets EduPulse match incoming Paystack `charge.success` events by the prepared route rather than by narration alone.

### Ordinary bank or manual path

If parents pay into a normal school account, the reference is still important because matching depends on whatever narration or webhook data the upstream provider returns.

## Example Payment-Code Payload

```json
{
  "student_code": "S001",
  "payment_identity": {
    "model": "installment_reference_first",
    "tuition_installments_enabled": true
  },
  "payment_codes": [
    {
      "fee_type": "Tuition",
      "reference_code": "S001-TUIT-I1",
      "base_amount": 500.0,
      "payment_category": {
        "installment_number": 1,
        "installment_label": "Installment 1",
        "installment_status": "open",
        "installment_start_date": "2026-09-01",
        "installment_due_date": "2026-09-30"
      }
    },
    {
      "fee_type": "Feeding (Monthly)",
      "reference_code": "S001-FEED-MON",
      "base_amount": 300.0
    }
  ]
}
```

## Parent Instruction Rule

Recommended wording:

1. If EduPulse shows a tracked transfer account, pay the exact amount into that account.
2. Keep the displayed reference for school-office support even when payment should track automatically.
3. If the school shares only a normal account or MoMo destination, include the reference exactly as shown.

## Related References

- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/PAYMENT_REFERENCE_CODE_SYSTEM.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `backend/payment_instruction_service.py`
- `backend/utils.py`
