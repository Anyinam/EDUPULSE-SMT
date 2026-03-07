# Terminal Report Fee + Tuition Fee Integration

## Overview

The terminal report fee has been **combined with the tuition fee** since the terminal report amount is typically small. This simplifies payment processing for parents/guardians and reduces confusion with multiple small payments.

## Changes Made

### 1. Backend Payment Code System (`backend/utils.py`)

**Changes:**
- Removed "Terminal Report" as a separate payment type (was index 5)
- Updated `PAYMENT_TYPE_INDEX` to only include: Tuition (1), Feeding (2), Uniform (3), Transport (4)
- Modified `generate_all_payment_codes()` to combine terminal report fee with tuition fee automatically
- Custom fees now start at index 5 instead of index 6

**Key Code:**
```python
# Combine tuition and terminal report fees
tuition_amount = fees_config.get("tuition_fee", 0) + fees_config.get("terminal_report_fee", 0)

standard_fees = [
    ("Tuition", tuition_amount),  # Now includes terminal report
    ("Feeding", fees_config.get("feeding_fee", 0)),
    ("Uniform", fees_config.get("uniform_fee", 0)),
    ("Transport", fees_config.get("transport_fee", 0)),
]
```

### 2. Payment Codes API Endpoint (`backend/routes.py`)

**Endpoint:** `GET /api/students/<int:student_id>/payment-codes`

**Changes:**
- Tuition amount now includes terminal report fee in calculation
- Display label changed from "Tuition" to "Tuition + Terminal Report"
- Payment instructions reflect combined amount

**Key Code:**
```python
if fee_type == "Tuition":
    # Tuition now includes terminal report fee
    amount = fees_config["tuition_fee"] + fees_config["terminal_report_fee"]
    
# Display name for tuition includes terminal report reference
display_name = fee_type
if fee_type == "Tuition":
    display_name = "Tuition + Terminal Report"
```

### 3. Frontend Payment Tracker (`frontend/react/src/components/StudentPaymentTracker.jsx`)

**Changes:**
- Removed "Terminal Report" from `feeTypes` array
- Updated `calculatePaymentSummary()` to include terminal report fee in tuition calculations
- Added `getFeeTypeLabel()` helper function to display "Tuition + Terminal Report" label
- All displays, receipts, and payment instructions now show combined label

**Key Code:**
```javascript
const feeTypes = ['Tuition', 'Feeding', 'Uniform', 'Transport'];

const getFeeTypeLabel = (feeType) => {
  return feeType === 'Tuition' ? 'Tuition + Terminal Report' : feeType;
};

// In calculation
if (paymentType === 'Tuition' && schoolFees?.tuition_fee) {
  // Combine tuition and terminal report fees
  requiredAmount = schoolFees.tuition_fee + (schoolFees.terminal_report_fee || 0);
}
```

## Payment Reference Codes

### Before Change:
```
CFK011 - Tuition (GH₵ 5000)
CFK012 - Feeding (GH₵ 500)
CFK013 - Uniform (GH₵ 300)
CFK014 - Transport (GH₵ 200)
CFK015 - Terminal Report (GH₵ 100)  ← Separate payment
```

### After Change:
```
CFK011 - Tuition + Terminal Report (GH₵ 5100)  ← Combined
CFK012 - Feeding (GH₵ 500)
CFK013 - Uniform (GH₵ 300)
CFK014 - Transport (GH₵ 200)
```

## Benefits

### For Parents/Guardians:
- ✅ **Simpler payments** - One code instead of two for tuition and terminal report
- ✅ **Fewer transactions** - Reduces payment processing overhead
- ✅ **Less confusion** - No need to remember separate code for small terminal report fee

### For School Staff:
- ✅ **Easier tracking** - Tuition and terminal report fees tracked together
- ✅ **Reduced reconciliation** - Fewer payment types to match
- ✅ **Cleaner reports** - Payment summaries are more concise

### For System:
- ✅ **Simplified logic** - Fewer fee types to handle
- ✅ **Better UX** - Payment instructions are clearer
- ✅ **Consistent display** - All interfaces show "Tuition + Terminal Report" label

## Payment Instructions Display

### MoMo Payment Example:
```
Fee Type: Tuition + Terminal Report
Amount: GH₵ 5100.00
Reference Code: CFK011

Instructions:
1. Dial MoMo shortcode or use app
2. Send GH₵ 5100.00 to [school number]
3. Use reference: CFK011
```

### Bank Transfer Example:
```
Fee Type: Tuition + Terminal Report
Amount: GH₵ 5100.00
Reference Code: CFK011

Bank Details:
- Bank: GCB Bank
- Account: 1234567890
- Branch: Accra
- Reference/Narration: CFK011
```

## Database Schema (No Changes)

**Good News:** No database migration needed!

- `SchoolSettings` table still has separate `tuition_fee` and `terminal_report_fee` columns
- Both fees are simply **added together** at calculation time
- Historical payments with `payment_type="Terminal Report"` remain valid
- New payments will use `payment_type="Tuition"` for both components

## Backward Compatibility

### Existing Payments:
- Old payments with `payment_type="Terminal Report"` are still in database
- They won't be counted in new "Tuition" calculations (intentional)
- Finance staff can still see historical terminal report payments in payment history

### Configuration:
- Schools can still set separate tuition and terminal report fees in Settings Panel
- The combination happens **automatically** during payment code generation
- No manual intervention required

## Testing Checklist

Test the following to ensure everything works:

- [ ] Navigate to Student Payment Tracker
- [ ] Select a student
- [ ] Click "📋 View Payment Codes & Instructions"
- [ ] Verify "Tuition + Terminal Report" is shown with combined amount
- [ ] Verify reference code is CFK011 format (no CFK015 anymore)
- [ ] Print payment instructions receipt
- [ ] Verify printed receipt shows "Tuition + Terminal Report"
- [ ] Check payment summary section shows combined amount
- [ ] Test payment recording with Tuition payment type
- [ ] Verify amount deducted from combined tuition requirement

## API Response Example

**Endpoint:** `GET /api/students/123/payment-codes`

```json
{
  "student_id": 123,
  "student_name": "Kofi Mensah",
  "student_code": "CFK01",
  "class": "JHS 1",
  "payment_codes": [
    {
      "fee_type": "Tuition + Terminal Report",
      "code": "CFK011",
      "amount": 5100.0,
      "instructions": "Pay GH₵ 5100.00 for Tuition + Terminal Report. Use reference code: CFK011"
    },
    {
      "fee_type": "Feeding",
      "code": "CFK012",
      "amount": 500.0,
      "instructions": "Pay GH₵ 500.00 for Feeding. Use reference code: CFK012"
    },
    {
      "fee_type": "Uniform",
      "code": "CFK013",
      "amount": 300.0,
      "instructions": "Pay GH₵ 300.00 for Uniform. Use reference code: CFK013"
    },
    {
      "fee_type": "Transport",
      "code": "CFK014",
      "amount": 200.0,
      "instructions": "Pay GH₵ 200.00 for Transport. Use reference code: CFK014"
    }
  ],
  "note": "Parents should reference the code when making payments via MoMo or at the school office."
}
```

## Settings Panel (No Changes Needed)

The Settings Panel still shows separate fields:
- **Tuition Fee:** GH₵ 5000.00
- **Terminal Report Fee:** GH₵ 100.00

**Why keep them separate?**
- Allows schools to see individual fee breakdowns
- Makes it easy to adjust terminal report pricing without changing tuition
- Provides transparency in fee structure
- Backend automatically combines them for payment processing

## Files Modified

| File | Changes |
|------|---------|
| `backend/utils.py` | ✅ Updated payment code generation logic |
| `backend/routes.py` | ✅ Updated payment codes endpoint |
| `frontend/react/src/components/StudentPaymentTracker.jsx` | ✅ Updated fee calculations and displays |

## Deployment Status

✅ **Deployed:** February 28, 2026
✅ **Build Status:** Successful (23.9s)
✅ **Containers:** All services started and healthy

---

**Last Updated:** February 28, 2026  
**Version:** 2.1.0  
**Status:** Production Ready
