# 🏦 Automated Bank Transfer Tracking

## Overview
EduPulse now supports automated bank transfer payment tracking using a stable learner payment identity plus a structured payment reference. When parents make bank transfers, the system reads the reference, identifies the learner, infers the payment purpose, and records the payment.

## Features
✅ Automatic payment recording by stable learner identity and structured reference  
✅ Duplicate prevention using transaction IDs  
✅ Real-time tuition balance updates  
✅ Audit logging for bank transfers  
✅ Support for all major Ghana banks (GCB, Ecobank, etc.)
✅ Reference-first and not dependent on retired fee-route setup

---

## Webhook Endpoint

**URL:** `/api/finance/webhook/bank`  
**Method:** `POST`  
**Authentication:** HMAC SHA256 signature in `X-Bank-Signature` using the server-side `BANK_WEBHOOK_SECRET`

## Payload Structure

Bank providers should send this JSON structure:

```json
{
  "status": "success",
  "reference": "S001-TUITION-T1",         # Stable learner identity + payment purpose
  "amount": 500.00,                       # Amount in GH₵
  "transaction_id": "BANK-GCB-2026-001",  # Unique transaction ID (idempotency key)
  "payer_name": "Parent Name",            # Optional: payer details
  "account_number": "1234567890",         # Optional: payer account
  "description": "Tuition payment"        # Optional: payment description
}
```

## How It Works

### 1. **Bank Webhook Triggered**
When a parent makes a bank transfer with the structured reference in the narration:
```
Transfer Amount: GH₵500
Reference: S001-TUITION-T1 or "Kofi-S001-TUITION-T1"
Bank: Ghana Commercial Bank
```

### 2. **Automatic Matching**
- System extracts learner identity and payment purpose from `reference` field
- Looks up student by `student_code` field
- Finds `student.id` from database

### 3. **Payment Recording**
- Creates `Payment` record with:
  - `student_id` ← Linked to student
  - `method: 'Bank_Auto'` ← Marked as automated
  - `status: 'Confirmed'` ← Auto-confirmed
  - `reference_id: transaction_id` ← For duplicate prevention
  - `payment_type/payment_category` ← Parsed from the structured reference or provider metadata

### 4. **Balance Update**
- Automatically deducts from `student.total_tuition_owed`
- Updates financial records in real-time

---

## Test Scenario

You can test the bank webhook manually:

```bash
export BANK_WEBHOOK_SECRET="replace-with-your-shared-secret"
payload='{"status":"success","reference":"S001-TUITION-T1","amount":500.00,"transaction_id":"BANK-GCB-2026-001","payer_name":"Ama Mensah","description":"Tuition"}'
signature=$(printf '%s' "$payload" | openssl dgst -sha256 -hmac "$BANK_WEBHOOK_SECRET" -hex | sed 's/^.* //')

curl -X POST http://localhost:5000/api/finance/webhook/bank \
  -H "Content-Type: application/json" \
  -H "X-Bank-Signature: $signature" \
  -d "$payload"
```

**Expected Response:**
```json
{
  "status": "recorded",
  "student_id": 1,
  "amount": 500.0
}
```

---

## Comparison: MoMo vs Bank Transfer

| Feature | MoMo | Bank Transfer |
|---------|------|-------|
| Endpoint | `/finance/webhook/momo` | `/finance/webhook/bank` |
| Payment Method | `MoMo_Auto` | `Bank_Auto` |
| Reference Field | Structured reference | Structured reference |
| Auto-Confirm | ✓ Yes | ✓ Yes |
| Idempotent | ✓ Via reference | ✓ Via transaction_id |
| Real-time | ✓ Immediate | ✓ Immediate |

---

## Integration with Banks

### Ghana Commercial Bank (GCB)
- API: GCB Developer Portal
- Reference Format: Use the stable learner identity plus structured payment purpose
- Webhook supports custom HTTP callbacks

### Ecobank
- API: Ecobank Payment Gateway
- Reference Field available for student tracking
- Webhook endpoint configurable per merchant

### Other Banks
- Standard format: Send the structured reference in reference/description
- Contact bank technical support for webhook setup
- Ensure transaction_id is unique per transfer

---

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| `200` | Success | Payment recorded |
| `200` (ignored) | Transfer failed | Webhook ignored, no action |
| `400` | No reference found | Manual verification needed |
| `404` | Student not found | Check student code |
| `200` (duplicate) | Already recorded | Duplicate prevention active |
| `500` | Server error | Check logs and retry |

---

## Security Considerations

1. **Webhook Signature Verification**: Each callback must include a valid `X-Bank-Signature` HMAC generated from the raw request body and `BANK_WEBHOOK_SECRET`
2. **Transaction ID Uniqueness**: Each bank transfer must have unique `transaction_id` to prevent duplicates
3. **Status Verification**: Only `"status": "success"` triggers recording
4. **Audit Trail**: All bank transfers logged in `AuditLog` with timestamps
5. **Student Code Validation**: Student must exist in database before recording

---

## FAQ

**Q: What if a bank transfer comes in with wrong student code?**  
A: Returns `404 student_not_found`. Manual review recommended. Consider adding to pending transfers audit log.

**Q: Can the same transfer be recorded twice?**  
A: No. The `reference_id` (transaction_id) is unique in database. Duplicate payments are silently ignored.

**Q: What's the difference between `Bank` and `Bank_Auto`?**  
- `Bank` = Manual entry (slower, requires staff action)
- `Bank_Auto` = Webhook auto-recorded (instant, zero manual overhead)

**Q: Do bank transfers update student tuition immediately?**  
A: Yes. The `student.total_tuition_owed` is updated immediately upon webhook receipt.

**Q: Can I track which specific bank a transfer came from?**  
A: Currently stored generically as `Bank_Auto`. Extend `Payment.method` field to include bank name if needed (e.g., `Bank_Auto_GCB`).

---

## Next Steps

1. **Contact your bank** to enable webhook callbacks
2. **Agree on a shared webhook secret** and store it as `BANK_WEBHOOK_SECRET` on the EduPulse server
3. **Configure webhook URL**: `https://yourdomain.com/api/finance/webhook/bank`
4. **Configure the bank/provider to sign each callback** with the same secret in `X-Bank-Signature`
5. **Test with curl** (command above)
6. **Monitor audit logs** for successful recordings
7. **Train parents** to include student code in transfer reference
