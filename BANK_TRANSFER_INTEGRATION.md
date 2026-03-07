# 🏦 Automated Bank Transfer Tracking

## Overview
EduPulse now supports **automated bank transfer payment tracking by student ID**, similar to MoMo automation. When parents make bank transfers, the system automatically matches the student code and records the payment.

## Features
✅ Automatic payment recording by **student ID**  
✅ Duplicate prevention using transaction IDs  
✅ Real-time tuition balance updates  
✅ Audit logging for bank transfers  
✅ Support for all major Ghana banks (GCB, Ecobank, etc.)

---

## Webhook Endpoint

**URL:** `/api/finance/webhook/bank`  
**Method:** `POST`  
**Authentication:** None (bank provider callback)

## Payload Structure

Bank providers should send this JSON structure:

```json
{
  "status": "success",
  "reference": "S001",                    # Student code
  "amount": 500.00,                       # Amount in GH₵
  "transaction_id": "BANK-GCB-2026-001",  # Unique transaction ID (idempotency key)
  "payer_name": "Parent Name",            # Optional: payer details
  "account_number": "1234567890",         # Optional: payer account
  "description": "Tuition payment"        # Optional: payment description
}
```

## How It Works

### 1. **Bank Webhook Triggered**
When a parent makes a bank transfer with student code in the reference:
```
Transfer Amount: GH₵500
Reference: S001 or "Kofi-S001-Tuition"
Bank: Ghana Commercial Bank
```

### 2. **Automatic Matching**
- System extracts student code from `reference` field
- Looks up student by `student_code` field
- Finds `student.id` from database

### 3. **Payment Recording**
- Creates `Payment` record with:
  - `student_id` ← Linked to student
  - `method: 'Bank_Auto'` ← Marked as automated
  - `status: 'Confirmed'` ← Auto-confirmed
  - `reference_id: transaction_id` ← For duplicate prevention

### 4. **Balance Update**
- Automatically deducts from `student.total_tuition_owed`
- Updates financial records in real-time

---

## Test Scenario

You can test the bank webhook manually:

```bash
curl -X POST http://localhost:5000/api/finance/webhook/bank \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "reference": "S001",
    "amount": 500.00,
    "transaction_id": "BANK-GCB-2026-001",
    "payer_name": "Ama Mensah",
    "description": "Tuition"
  }'
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
| Reference Field | Phone/Reference | Student Code |
| Auto-Confirm | ✓ Yes | ✓ Yes |
| Idempotent | ✓ Via reference | ✓ Via transaction_id |
| Real-time | ✓ Immediate | ✓ Immediate |

---

## Integration with Banks

### Ghana Commercial Bank (GCB)
- API: GCB Developer Portal
- Reference Format: Use student code as reference
- Webhook supports custom HTTP callbacks

### Ecobank
- API: Ecobank Payment Gateway
- Reference Field available for student tracking
- Webhook endpoint configurable per merchant

### Other Banks
- Standard format: Send student code in reference/description
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

1. **Transaction ID Uniqueness**: Each bank transfer must have unique `transaction_id` to prevent duplicates
2. **Status Verification**: Only `"status": "success"` triggers recording
3. **Audit Trail**: All bank transfers logged in `AuditLog` with timestamps
4. **Student Code Validation**: Student must exist in database before recording

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
2. **Configure webhook URL**: `https://yourdomain.com/api/finance/webhook/bank`
3. **Test with curl** (command above)
4. **Monitor audit logs** for successful recordings
5. **Train parents** to include student code in transfer reference
