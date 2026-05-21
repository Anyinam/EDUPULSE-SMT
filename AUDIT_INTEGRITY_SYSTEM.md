# Audit Integrity & Payment Security System

## Overview

EduPulse implements a **cryptographic audit trail** for all financial transactions to ensure transparency, prevent fraud, and maintain regulatory compliance. This document explains the immutable ledger system and payment approval workflow.

## Core Principles

### 1. Immutable Ledger (Hash Chain)

All **confirmed** payments are recorded in an immutable blockchain-style ledger where:
- Each entry contains a cryptographic hash of the previous entry
- Any tampering breaks the hash chain and is immediately detectable
- Entries cannot be edited or deleted once added
- Full audit trail from first to last transaction

**Database Table:** `ledger_entries`

**Hash Algorithm:** HMAC-SHA256 using secret key (LEDGER_SECRET_KEY)

### 2. Separation of Duties

**Why can't Finance staff confirm their own payments?**

To prevent fraud and ensure accountability, we implement **dual control**:

- **Finance/Teachers** can RECORD payments → Creates "Pending" status
- **Proprietor ONLY** can APPROVE payments → Creates immutable ledger entry

This separation ensures:
- No single person can both record AND confirm money
- Proprietor has final oversight of all cash handling
- Clear audit trail of who recorded vs. who approved

### 3. Cannot Edit Confirmed Payments

**Why can't we edit or delete confirmed payments?**

Once a payment is **confirmed by proprietor**, it is:
1. Added to the immutable ledger with cryptographic hash
2. Locked permanently in the audit trail
3. Cannot be edited/deleted without breaking the hash chain
4. Required for regulatory compliance and fraud prevention

**If a mistake is made:**
- Contact system administrator
- A correcting entry (reversal + correction) must be created
- Original entry remains in ledger for audit purposes

## Payment Approval Workflow

### Verification Gate (School KYB)

Before selected finance actions proceed, the system checks school verification status.

- If verified: payment flow continues normally.
- If not verified: finance action can be blocked with a verification-required response.
- Schools can be auto-verified through configured KYB provider outcomes, with review-required exceptions routed to compliance review.

### Step 1: Manual Payment Recording

**Who can record:** Teacher, Homeroom, Finance, Inventory Manager, Proprietor

**Process:**
```
Staff → Records payment → Status: "Pending"
```

**Not yet in ledger:** Pending payments are NOT hashed until approved

### Step 2: Proprietor Review

**Who can approve:** Proprietor ONLY

**Actions available:**
- ✅ **Approve & Hash** → Adds to immutable ledger
- ❌ **Reject** → Removes pending payment (not yet in ledger)

**Process:**
```
Proprietor reviews → Approves → Status: "Confirmed" + Ledger Entry Created
```

### Step 3: Immutable Record

Once approved:
- Payment status changes to "Confirmed"
- Ledger entry created with cryptographic hash
- Student balance updated
- Entry becomes permanent and uneditable

## Ledger Entry Structure

Each ledger entry contains:

```json
{
  "id": 12345,
  "school_id": "CCA-OFK",
  "tx_type": "tuition",
  "tx_ref": "PAY-12345",
  "amount": 500.00,
  "currency": "GH₵",
  "actor_id": 5,
  "student_id": 123,
  "source": "cash",
  "metadata": {
    "payment_id": 12345,
    "student_name": "John Doe",
    "student_code": "S001",
    "confirmed_by": "proprietor_username"
  },
  "prev_hash": "abc123...",
  "entry_hash": "def456...",
  "created_at": "2026-02-28T12:00:00Z"
}
```

**Hash Calculation:**
```python
entry_hash = HMAC-SHA256(
    school_id + tx_type + tx_ref + amount + currency + 
    actor_id + student_id + source + prev_hash + created_at,
    secret_key=LEDGER_SECRET_KEY
)
```

## Audit Verification

### Verify Ledger Integrity

**Endpoint:** `GET /api/finance/audit/verify`

**Access:** Proprietor only

**Process:**
1. Retrieves all ledger entries in sequence
2. Recalculates hash for each entry
3. Verifies each entry's hash matches stored hash
4. Verifies each entry's prev_hash matches actual previous entry
5. Reports any broken links in the chain

**Response:**
```json
{
  "is_valid": true,
  "status": "VERIFIED IMMUTABLE",
  "total_checked": 1234,
  "broken_count": 0,
  "broken_entries": []
}
```

### View Audit Ledger

**Endpoint:** `GET /api/finance/audit/ledger`

**Access:** Proprietor only

**Features:**
- Paginated ledger entries
- Filter by date range
- Shows all confirmed transactions with hashes
- Cannot be filtered to hide entries (full transparency)

## Automated Payments (Via Webhooks)

**MoMo/Bank Transfer auto-payments:**
- Automatically marked as "Confirmed" (verified by payment provider)
- Immediately added to immutable ledger
- No manual approval needed (already verified by bank/MoMo)
- If school verification is not approved, payment can remain pending and open an AML/compliance flag until resolved.

**Webhook endpoints:**
- `/api/finance/webhook/momo` - MoMo automated callbacks
- `/api/finance/webhook/bank` - Bank transfer callbacks
- `/api/paystack/webhook` - Paystack payment confirmations

## Role Permissions Summary

| Role | Record Payment | Approve Payment | View Ledger | Verify Ledger |
|------|---------------|-----------------|-------------|---------------|
| **Proprietor** | ✅ Auto-confirm | ✅ Yes | ✅ Yes | ✅ Yes |
| **Finance** | ✅ Needs approval | ❌ No | ❌ No | ❌ No |
| **Teacher** | ✅ Needs approval | ❌ No | ❌ No | ❌ No |
| **Homeroom** | ✅ Needs approval | ❌ No | ❌ No | ❌ No |
| **Inventory Mgr** | ✅ Inventory only | ❌ No | ❌ No | ❌ No |

## Security Considerations

### 1. Ledger Secret Key Protection

**Environment Variable:** `LEDGER_SECRET_KEY`

**Best Practices:**
- Use cryptographically random 64+ character key
- Never commit to version control
- Rotate periodically (requires ledger regeneration)
- Store in secure secrets management (AWS Secrets Manager, Vault, etc.)

### 2. Preventing Backdoor Access

**Database Protection:**
- Even with direct database access, tampering is detectable
- Hash verification will fail if data is modified
- Audit logs track all database queries
- Regular verification runs detect tampering

### 3. Regulatory Compliance

This system supports:
- **GAAP** (Generally Accepted Accounting Principles)
- **SOX** (Sarbanes-Oxley) - audit trail requirements
- **Tax Authority Requirements** - immutable transaction records
- **Internal Controls** - separation of duties

## User Interface

### Finance Dashboard

**What finance staff see:**
- "💰 Record Payment" form at top
- Can record all payment types
- "⏳ Pending Payments" section showing awaiting approval
- Cannot confirm their own recorded payments

### Proprietor Panel

**What proprietor sees:**
- "💰 Record Payment" form (auto-confirms)
- "⏳ Pending Manual Payments (Requires Your Approval)" section
- For each pending payment:
  - ✅ **Approve & Hash** button (green)
  - ❌ **Reject** button (red)
- Audit ledger access in finance section

## Error Messages

### "Cannot reject confirmed payments - they are in the immutable audit ledger. Contact system administrator if correction needed."

**Cause:** Attempting to delete/edit a confirmed payment

**Solution:** 
- Confirmed payments cannot be deleted (they're hashed)
- If error occurred, create a reversal entry
- Contact administrator for manual intervention if needed

### "Access denied: Platform owner credentials required"

**Cause:** Non-proprietor trying to access audit verification

**Solution:** Only proprietor can verify audit integrity

## Troubleshooting

### Pending payments not showing

**Check:**
1. Payment was recorded with status "Pending"
2. User recording was not proprietor (proprieto auto-confirms)
3. Dashboard is fetching from correct API endpoint

### Hash chain broken

**Red alert - Possible tampering detected!**

**Action:**
1. Run ledger verification: `GET /api/finance/audit/verify`
2. Check broken_entries in response
3. Contact system administrator immediately
4. Review database access logs
5. Consider security incident response

### Cannot approve payment

**Check:**
1. User is logged in as proprietor
2. Payment is in "Pending" status
3. Backend has correct role permissions

## Future Enhancements

Planned features:

- [ ] Block-explorer style ledger viewer for proprietor
- [ ] Daily automated hash verification scheduled job
- [ ] Email alerts for failed hash verification
- [ ] Multi-signature approval (2+ proprietors)
- [ ] Reversal entry workflow for corrections
- [ ] Export ledger for external auditor review
- [ ] Real-time ledger sync to external audit system

## API Reference

### Confirm Payment

```http
POST /api/finance/confirm-payment/:payment_id
Authorization: Bearer <proprietor_jwt>
X-School-ID: <school_id>
```

**Access:** Proprietor only

### Reject Payment

```http
POST /api/finance/reject-payment/:payment_id
Authorization: Bearer <proprietor_jwt>
X-School-ID: <school_id>
```

**Access:** Proprietor only

**Protection:** Cannot reject confirmed payments

### Verify Ledger

```http
POST /api/finance/audit/verify
Authorization: Bearer <proprietor_jwt>
X-School-ID: <school_id>
```

**Access:** Proprietor only

### View Ledger

```http
GET /api/finance/audit/ledger?limit=100&offset=0&start_date=2026-01-01&end_date=2026-12-31
Authorization: Bearer <proprietor_jwt>
X-School-ID: <school_id>
```

**Access:** Proprietor only

---

**Last Updated:** February 28, 2026  
**Version:** 2.0.0  
**Compliance:** GAAP, SOX-compliant
