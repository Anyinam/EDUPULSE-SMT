# 💰 Payment Reference Format Guide

## Reference Parsing: How Parents Pay ✅

This is now the recommended default parent payment instruction across EduPulse SMT.

Recommended product stance:
- structured references should remain the default parent instruction across bank app, shortcode / USSD, and manual fallback flows
- EduPulse should favor a stable student or family payment identity plus reference parsing rather than multiplying payment destinations unnecessarily
- legacy Paystack route metadata may still appear in historical audit data, but new fee-route setup is retired

Instead of any configuration, **parents simply enter a formatted reference** when making MoMo or Bank transfers.

Your system **automatically parses** this reference to extract:
- Student Identifier (usually the student's code in EduPulse)
- Payment Type (Tuition, Feeding, Uniform, Transport)
- Payment Category (Term, Frequency, Item, etc.)

---

## Reference Format

**Pattern: `STUDENT_CODE-CATEGORY-[OPTIONAL_DETAIL]`**

### Tuition References
```
S001-T1    → Student S001, Term 1 Tuition
S001-T2    → Student S001, Term 2 Tuition
S001-T3    → Student S001, Term 3 Tuition
```

### Feeding References
```
S001-FEED-DAY   → Student S001, Daily Feeding
S001-FEED-WEK   → Student S001, Weekly Feeding
S001-FEED-MON   → Student S001, Monthly Feeding
```

The first segment is the learner's stable school identifier. The last segment tells EduPulse whether the feeding payment is for the daily, weekly, or monthly plan.

### Uniform References
```
S001-UNIF      → Student S001, Uniform Purchase
```

### Transport References
```
S001-TRANS-DAY → Student S001, Daily Transport
S001-TRANS-MON → Student S001, Monthly Transport
```

---

## Real-World Example

### Parent Makes a Transfer

**Scenario:** Kofi's parent pays GH₵500 for Term 1 tuition

**Parent's Steps (Using Any Bank App):**
```
FROM:        My Account (John's Account)
TO:          0501234567 (School's MoMo Account)
AMOUNT:      500 GH₵
REFERENCE:   S001-T1    ← This is KEY!
MESSAGE:     Kofi's Term 1 Tuition
[Send]
```

### Bank/MoMo Sends Webhook

Bank provider sends to your system:
```json
{
  "status": "success",
  "reference": "S001-T1",
  "amount": 500,
  "transaction_id": "BANK-GCB-2026-abc123"
}
```

### Your System Auto-Processes

```python
# Step 1: Parse reference
reference = "S001-T1"
parsed = parse_payment_reference(reference)
# Result: {
#   "student_code": "S001",
#   "payment_type": "Tuition",
#   "category": {"term": "Term 1"}
# }

# Step 2: Find student
student = Student.query.filter_by(student_code="S001").first()

# Step 3: Create payment
payment = Payment(
    student_id=student.id,
    payment_type="Tuition",
    method="Bank_Auto",
    amount=500,
    payment_category={"term": "Term 1"},
    status="Confirmed"
)

# Step 4: Update balance
student.total_tuition_owed -= 500

# Step 5: Log it
log_action(..., action="BANK_TRANSFER_AUTO", ...)
```

### Result in System

Database shows:
```
Payment {
  student_id: 1 (Kofi),
  payment_type: "Tuition",
  amount: 500.00,
  payment_category: {"term": "Term 1"},
  method: "Bank_Auto",
  status: "Confirmed"
}
```

---

## Category Code Reference

### Tuition (Handled by Terms)
| Code | Maps To |
|------|---------|
| T1 | `{"term": "Term 1"}` |
| T2 | `{"term": "Term 2"}` |
| T3 | `{"term": "Term 3"}` |

### Feeding (Handled by Frequency)
| Code | Maps To |
|------|---------|
| FEED-DAY | `{"frequency": "Daily"}` |
| FEED-WEK | `{"frequency": "Weekly"}` |
| FEED-MON | `{"frequency": "Monthly"}` |

### Other
| Code | Maps To |
|------|---------|
| UNIF | `{"item": "School Uniform"}` |
| TRANS-MON | `{"frequency": "Monthly"}` (for transport) |
| TRANS-DAY | `{"frequency": "Daily"}` (for transport) |

---

## Testing the Webhooks

### Test Term 1 Tuition (Bank Transfer)

```bash
curl -X POST http://localhost:5000/api/finance/webhook/bank \
  -H "Content-Type: application/json" \
  -H "X-Bank-Signature: <hmac_sha256_of_raw_body>" \
  -d '{
    "status": "success",
    "reference": "S001-T1",
    "amount": 500,
    "transaction_id": "BANK-2026-001"
  }'
```

Response:
```json
{
  "status": "recorded",
  "student_id": 1,
  "payment_type": "Tuition",
  "category": {"term": "Term 1"}
}
```

### Test Monthly Feeding (MoMo)

```bash
curl -X POST http://localhost:5000/api/finance/webhook/momo \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "reference": "S002-FEED-MON",
    "amount": 100,
    "transaction_id": "MOMO-2026-002"
  }'
```

Response:
```json
{
  "status": "recorded",
  "student_id": 2,
  "payment_type": "Feeding",
  "category": {"frequency": "Monthly"}
}
```

### Test Daily Feeding (MoMo)

```bash
curl -X POST http://localhost:5000/api/finance/webhook/momo \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "reference": "S001-FEED-DAY",
    "amount": 5,
    "transaction_id": "MOMO-2026-003"
  }'
```

Response:
```json
{
  "status": "recorded",
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
