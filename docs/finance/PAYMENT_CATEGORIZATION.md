# 💰 Granular Payment Categorization Guide

## No Configuration Needed With Providers ✅

**You DO NOT need to configure anything with MoMo or Bank providers.** All categorization happens on your end!

Payment providers (MoMo, Bank) don't care about your internal business logic. They just send:
- Amount
- Reference (stable learner identity plus payment purpose)
- Transaction ID
- Status

**You handle the categorization** to track:
- **Tuition**: Term 1, Term 2, Term 3
- **Feeding**: Daily, Weekly, Monthly
- **Uniforms**: Specific item + quantity
- **Transport**: Route + frequency

Recommended stance:
- use one stable learner or family payment identity as the default parent instruction
- encode payment purpose in the structured reference
- treat legacy Paystack route metadata as historical compatibility data, not an active setup requirement

---

## How It Works

### 1️⃣ **Tuition Tracking by Term**

When a parent pays for Term 1 tuition:

```bash
# Bank sends this
curl -X POST http://localhost:5000/api/finance/webhook/bank \
  -H "Content-Type: application/json" \
  -H "X-Bank-Signature: <hmac_sha256_of_raw_body>" \
  -d '{
    "status": "success",
    "reference": "S001-TUITION-T1",
    "amount": 500.00,
    "transaction_id": "BANK-GCB-2026-001",
    "description": "Tuition - Term 1",
    "category": {"term": "Term 1"}
  }'
```

**System Records:**
```json
{
  "student_id": 1,
  "payment_type": "Tuition",
  "method": "Bank_Auto",
  "amount": 500.00,
  "payment_category": {"term": "Term 1"},  // 👈 Tracked!
  "status": "Confirmed"
}
```

**Benefits:**
- Query all Term 1 payments: `Payment.query.filter_by(payment_type='Tuition').all()` then filter by category
- Report: "Term 1 Revenue: GH₵5,000"
- Balance: Track remaining tuition per term

---

### 2️⃣ **Feeding by Frequency**

Daily or Monthly feeding payments:

```bash
# Parent pays for monthly feeding on MoMo
curl -X POST http://localhost:5000/api/finance/receive-payment \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 2,
    "amount": 100.0,
    "type": "Feeding",
    "method": "MoMo",
    "payment_category": {"frequency": "Monthly"}  # 👈 Specify frequency
  }'
```

**System Records:**
```json
{
  "student_id": 2,
  "payment_type": "Feeding",
  "method": "MoMo",
  "amount": 100.00,
  "payment_category": {"frequency": "Monthly"},  // 👈 Tracked!
  "status": "Confirmed"
}
```

**Query Examples:**
```python
# Get all daily feeding payments
daily_payments = db.session.query(Payment).filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Daily'
).all()

# Get monthly revenue
monthly_feeding = db.session.query(db.func.sum(Payment.amount)).filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Monthly'
).scalar()
```

---

### 3️⃣ **Uniform Tracking by Item**

Which uniforms purchased and quantity:

```bash
# Uniform payment with item details
curl -X POST http://localhost:5000/api/finance/receive-payment \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "amount": 300.0,
    "type": "Uniform",
    "method": "Cash",
    "payment_category": {
      "item": "School Uniform - Size Large",
      "quantity": 2
    }
  }'
```

**System Records:**
```json
{
  "student_id": 1,
  "payment_type": "Uniform",
  "amount": 300.00,
  "payment_category": {
    "item": "School Uniform - Size Large",
    "quantity": 2
  },
  "status": "Confirmed"
}
```

**Business Use:**
- "How many students bought Large uniforms?" → Count via payment_category
- "Total uniform revenue this term?" → Sum all Uniform payment_type
- Inventory sync: Link purchases to inventory levels

---

### 4️⃣ **Transport by Route**

Track transport fees by route:

```bash
curl -X POST http://localhost:5000/api/finance/receive-payment \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 3,
    "amount": 150.0,
    "type": "Transport",
    "method": "Bank",
    "payment_category": {
      "route": "Ashongman - Accra",
      "frequency": "Monthly"
    }
  }'
```

---

## Auto-Detection (Zero Manual Work)

If the bank description says "Tuition - Term 1", the system auto-detects:

```python
# Bank sends: {"description": "Tuition - Term 1"}
# System auto-extracts: {"term": "Term 1"}
```

**Auto-Detection Examples:**
| Description | Auto-Category |
|-------------|----------|
| "Tuition - Term 1" | `{"term": "Term 1"}` |
| "Tuition - Term 2" | `{"term": "Term 2"}` |
| "Feeding - Monthly" | `{"frequency": "Monthly"}` |
| "School Uniform Payment" | `{"item": "School Uniform"}` |
| "Transport - Route 5" | `{"route": "Route 5"}` |

No extra configuration needed! Bank just mentions the details in description.

---

## Database Schema

The `payment_category` field:

```python
# JSON field in Payment model
payment_category = db.Column(db.JSON, default={})

# Examples of valid data:
{
  "term": "Term 1"                                    # Tuition
}
{
  "frequency": "Monthly"                              # Feeding
}
{
  "item": "School Uniform - Size Large",              # Uniform
  "quantity": 2
}
{
  "route": "Ashongman",                               # Transport
  "frequency": "Monthly"
}
```

## Frontend Integration

When entering payment manually, show dropdowns:

```jsx
// Tuition payment
<select name="term">
  <option value="Term 1">Term 1</option>
  <option value="Term 2">Term 2</option>
  <option value="Term 3">Term 3</option>
</select>

// Feeding payment
<select name="frequency">
  <option value="Daily">Daily</option>
  <option value="Weekly">Weekly</option>
  <option value="Monthly">Monthly</option>
</select>

// Uniform payment
<select name="item">
  <option value="School Uniform - Size Small">Small</option>
  <option value="School Uniform - Size Large">Large</option>
</select>
<input type="number" name="quantity" placeholder="Quantity" />
```

---

## Reporting & Analytics

### Example: Term 1 Revenue Report

```python
# Get all Term 1 payments
term1_payments = Payment.query.filter(
    Payment.payment_type == 'Tuition',
    Payment.payment_category['term'].astext == 'Term 1'
).all()

total = sum(p.amount for p in term1_payments)  # Total revenue

# By student
for student_id in set(p.student_id for p in term1_payments):
    student_payments = [p for p in term1_payments if p.student_id == student_id]
    amount = sum(p.amount for p in student_payments)
    print(f"Student {student_id}: GH₵{amount}")
```

### Example: Monthly Feeding Patterns

```python
# Who pays monthly vs daily?
monthly_feeders = Payment.query.filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Monthly'
).count()

daily_feeders = Payment.query.filter(
    Payment.payment_type == 'Feeding',
    Payment.payment_category['frequency'].astext == 'Daily'
).count()

print(f"Monthly: {monthly_feeders}, Daily: {daily_feeders}")
```

---

## Summary: Zero Provider Configuration

| Element | Configuration Location |
|---------|----------------------|
| **Tuition Terms** | Your system (database) ✓ |
| **Feeding Frequency** | Your system (database) ✓ |
| **Uniform Items** | Your system (database) ✓ |
| **Transport Routes** | Your system (database) ✓ |
| **Payment Provider** | Banks/MoMo send only amounts ✓ |

Everything is **self-configured**. You don't need to set up anything with payment providers to track this level of detail!

---

## Test Scenario

```bash
# 1. Student pays for Term 1 Tuition via Bank
curl -X POST http://localhost:5000/api/finance/webhook/bank \
  -H "Content-Type: application/json" \
  -H "X-Bank-Signature: <hmac_sha256_of_raw_body>" \
  -d '{
    "status": "success",
    "reference": "S001",
    "amount": 500,
    "transaction_id": "BANK-001",
    "description": "Tuition - Term 1"
  }'

# 2. System auto-detects and stores: {"term": "Term 1"}

# 3. Query: All Term 1 tuition? Get payments where category['term'] == 'Term 1'

# 4. Report: Term 1 revenue = GH₵500 ✓
```

---

## Migration Note

If you already have payments without categories, they'll have empty `{}`. You can backfill:

```python
# Set all existing Feeding as Monthly (example)
for payment in Payment.query.filter_by(payment_type='Feeding').all():
    if not payment.payment_category:
        payment.payment_category = {"frequency": "Monthly"}

db.session.commit()
```

No downtime needed - old payments still work!
