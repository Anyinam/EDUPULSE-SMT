# Payment Reference Format Guide

## Purpose

Structured references are still the core identifier for student-fee categorization in EduPulse SMT, even when the school uses a Paystack tracked transfer account.

The reference answers two questions:
- which learner is this payment for?
- what fee purpose is being paid?

## Active Reference Pattern

Pattern:

`STUDENT_CODE-CATEGORY-[OPTIONAL_DETAIL]`

Examples:
- `S001-T1` for tuition term 1
- `S001-T2` for tuition term 2
- `S001-T3` for tuition term 3
- `S001-FEED-DAY` for daily feeding
- `S001-FEED-WEK` for weekly feeding
- `S001-FEED-MON` for monthly feeding
- `S001-UNIF` for uniform
- `S001-TRANS-DAY` for daily transport
- `S001-TRANS-MON` for monthly transport

## Current Parent Payment Experience

The school can share any of these references in 3 ways:

1. Printed instruction sheet with tracked transfer account details attached automatically when available
2. Manual school-office or direct-bank instruction using the same reference
3. Optional tracked online checkout link for cases where the school wants web checkout instead of bank transfer

When the school generates a tracked transfer account, the dedicated virtual account is bound to one reference. Parents do not need to understand Paystack. They only see a bank account to transfer to and the exact amount to pay.

## What The Reference Still Controls

EduPulse uses the reference to derive:
- learner identity
- payment type
- fee category metadata such as `term` or `frequency`

Examples:

| Reference | Meaning |
|------|---------|
| `S001-T1` | `Tuition` with `{"term": "Term 1"}` |
| `S001-FEED-MON` | `Feeding` with `{"frequency": "Monthly"}` |
| `S001-UNIF` | `Uniform` |
| `S001-TRANS-MON` | `Transport` with `{"frequency": "Monthly"}` |

## Important Distinction

Reference alone does not guarantee automatic tracking if money is sent to the school’s ordinary bank account and the provider does not return the reference reliably.

For reliable automatic tracking, the school should use the tracked transfer account for that reference. EduPulse then stores a `PaymentCollectionIntent` that maps:
- student
- reference
- Paystack customer
- dedicated account number
- settlement split

## Convenience Fee With References

The reference does not change the fee math. It only identifies the route.

For a tracked transfer account, EduPulse can show:
- base fee amount
- convenience fee amount
- total transfer amount

Example:
- reference: `S001-T1`
- base fee: `GH₵100`
- convenience fee: `GH₵6`
- parent transfer amount: `GH₵106`

The payment record will still categorize the fee under `S001-T1`, but only `GH₵100` is applied to the learner balance.

## Parent Instructions

Recommended wording:

1. If a tracked transfer account appears on the printed instruction sheet, pay the exact total into that account.
2. If the school shares only a normal bank or MoMo destination, include the reference exactly as shown.
3. Keep the same reference when showing proof at the school office.

## Error Rules

| Reference | Outcome | Why |
|-----------|---------|-----|
| `S001-T1` | Valid | Learner and fee purpose are clear |
| `S001-FEED-MON` | Valid | Learner and feeding frequency are clear |
| `S001` | Limited fallback | Learner may be found, but fee purpose is less precise |
| `S001-XYZ` | Weak | Unknown fee suffix, likely requires manual interpretation |

## Related References

- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `backend/utils.py`
  "student_id": 1,
  "payment_type": "Feeding",
  "category": {"frequency": "Daily"}
}
```

---

## How to Train Parents

### Print & Display (Can post in school)
```
HOW TO PAY SCHOOL FEES

1. Open your MoMo/Bank app
2. Send money to: [SCHOOL PHONE/ACCOUNT]

REFERENCE CODES (VERY IMPORTANT - Enter in reference field):

For Tuition:
- S001-T1 (Term 1)
- S001-T2 (Term 2)
- S001-T3 (Term 3)

For Feeding:
- S001-FEED-DAY (Daily)
- S001-FEED-MON (Monthly)

Replace S001 with your child's STUDENT CODE

If your school uses a different stable learner identifier, use that exact identifier before the feeding plan suffix.

Example:
If Kofi (Code: S001) is paying Term 1:
- Reference: S001-T1
```

---

## Error Scenarios

| Reference | Outcome | Why |
|-----------|---------|-----|
| `S001-T1` | ✅ Recorded | Valid format, student exists |
| `xyz-T1` | ❌ Not found | Student code doesn't exist |
| `S001` | ❌ Error | Missing category code |
| `S001-XYZ` | ⚠️ General | Unknown code, defaults to Tuition |
| `S001-T4` | ⚠️ General | Invalid term (only T1-T3) |

---

## Database Query Examples

### Get all Term 1 revenue
```python
term1_payments = Payment.query.filter(
    Payment.payment_type == 'Tuition',
    Payment.payment_category['term'].astext == 'Term 1'
).all()

total = sum(p.amount for p in term1_payments)
print(f"Term 1 Revenue: GH₵{total}")
```

### Get all monthly feeding payments
```python
monthly_feeding = Payment.query.filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Monthly'
).all()

print(f"Monthly Feeders: {len(monthly_feeding)}")
```

### Get daily feeding this week
```python
from datetime import datetime, timedelta

week_ago = datetime.now() - timedelta(days=7)

daily_this_week = Payment.query.filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Daily',
    Payment.date_paid >= week_ago
).all()

print(f"Daily feeding payments this week: {len(daily_this_week)}")
```

---

## Summary

✅ **No provider configuration needed** - Parents just include reference  
✅ **Automatic parsing** - System extracts all categorization  
✅ **Works with any MoMo/Bank** - Any provider that supports custom reference field  
✅ **Zero manual data entry** - Reference parsing handles it all  
✅ **Full audit trail** - Every transaction logged and categorized  

**Parents only need one thing from the school: the student's identifier followed by the correct fee suffix, such as `S001-FEED-WEK`.**
