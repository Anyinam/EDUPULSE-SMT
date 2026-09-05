# Payment Categorization Guide

## Current Product Logic

EduPulse SMT now uses a hybrid payment model:

1. Structured references remain the default identity for student fees.
2. Paystack dedicated virtual accounts are used when the school wants automatic transfer tracking.
3. Manual office entry still exists for cash or externally confirmed payments.
4. Public parent admission payments use a separate Paystack checkout flow.

Categorization is still handled inside EduPulse. The difference is that automatic transfer tracking now has a first-class provider route instead of relying only on ordinary bank narration.

## The 4 Active Payment Paths

### 1. Manual recorded payment

Route: `POST /api/finance/receive-payment`

Use this when staff are recording a confirmed school-office payment or an offline transfer that was verified outside the automated rails.

What EduPulse stores:
- `student_id`
- `amount`
- `payment_type`
- `payment_category`
- `reference_code` when available
- external transaction reference if supplied

### 2. Imported parent payment notice

Route: `POST /api/finance/import-parent-payment`

Use this when a school pastes a provider notice or SMS-like payment alert and EduPulse extracts the learner reference and external transaction id.

### 3. Ordinary bank webhook tracking

Route: `POST /api/finance/webhook/bank`

This still works when a bank or aggregator can send a signed webhook containing the structured learner reference. It is not the main guaranteed auto-tracking rail for general parent transfers unless the provider reliably sends that reference back.

### 4. Tracked transfer account via Paystack DVA

Route: `POST /api/students/<student_id>/payment-codes/<reference_code>/virtual-account`

This is now the main automatic transfer-tracking path for student fees.

EduPulse creates or reuses a `PaymentCollectionIntent` for that exact learner fee reference, provisions a Paystack dedicated virtual account, and waits for a `charge.success` webhook with `authorization.channel=dedicated_nuban`.

When the webhook lands:
- EduPulse matches the transfer back to the stored intent
- only the school fee portion is posted against the student balance
- convenience-fee metadata is preserved on the payment record

## Fee Categorization Still Uses References

Even with tracked transfer accounts, the fee purpose is still identified by EduPulse’s reference scheme.

Examples:
- `S001-T1` for tuition term 1
- `S001-FEED-MON` for monthly feeding
- `S001-UNIF` for uniform
- `S001-TRANS-MON` for monthly transport

The dedicated virtual account is created per payment reference. That means the route knows both:
- who the learner is
- what the payment is for

## Convenience Fee Logic

For tracked transfer accounts, EduPulse calculates:
- `base_amount`: the real school fee
- `estimated_provider_fee_amount`: estimated Paystack transfer-processing cost
- `platform_fee_amount`: EduPulse platform fee
- `convenience_fee_amount`: the total extra amount charged to the parent
- `total_amount`: what the parent must transfer

Example:
- tuition: `GH₵100`
- estimated provider fee: `GH₵3`
- EduPulse platform fee: `GH₵3`
- parent transfer total: `GH₵106`

When payment records are written, only `GH₵100` reduces the learner’s debt. The extra `GH₵6` remains in payment metadata for settlement and audit.

## Settlement Logic

Tracked transfer accounts now use Paystack split settlement on the dedicated virtual account:

- the school’s Paystack subaccount receives the fixed school fee amount
- the remainder settles into EduPulse’s main Paystack settlement account
- Paystack charges are borne by the main account in the current setup

That means the school receives the base fee amount while EduPulse retains the convenience-fee remainder, from which Paystack also deducts its own charge.

## School Setup Requirement

Tracked transfer accounts are only available after the school saves verified bank details and EduPulse successfully creates the school’s Paystack subaccount.

Without that subaccount:
- the tracked transfer button should not be offered as a ready rail
- EduPulse returns a readiness error if the route is forced from the API

## Main Data Structures

`Payment.payment_category` can include:
- learner fee descriptors like `term`, `frequency`, `route`, or `item`
- `reference_code`
- `collection_channel`
- `payment_collection_intent_id`
- `transfer_total_amount`
- `convenience_fee_amount`
- `platform_fee_amount`
- `estimated_provider_fee_amount`
- `settlement_mode`
- `split_code`

`PaymentCollectionIntent` stores the provider route itself:
- dedicated account number
- customer code
- school subaccount code
- split code
- base amount
- convenience fee
- total amount
- expiry and payment status

## Operational Rule

If you need reliable automatic tracking for transfer-style parent payments, use the tracked transfer account. If parents send money to the ordinary school bank account without a provider-backed tracked route, automatic identification depends on whatever webhook or notice the bank actually returns.

## Related References

- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `docs/finance/PAYMENT_INTEGRATION.md`
- `backend/routes.py`
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
