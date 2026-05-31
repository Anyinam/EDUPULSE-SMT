# Payment Reference System (MoMo + Bank + Cash Tracking)

## Overview
EduPulse should now treat structured references as the primary school-fee instruction model. Parents and guardians pay with one stable learner identity plus a readable payment-purpose reference that tells EduPulse what the payment is for.

**Example:**
- Stable learner identity: `CFK01`
- Tuition reference: `CFK01-TUITION-T1`
- Feeding reference: `CFK01-FEEDING-MON`
- Uniform reference: `CFK01-UNIFORM`
- Transport reference: `CFK01-TRANSPORT-MON`

Legacy note:
- older short payment-code patterns can still be recognized where already deployed
- new school communication should favor the clearer structured-reference format

---

## How It Works

### 1. **Reference Generation**
The system generates references from:
- **Stable learner identity**: e.g. `CFK01`
- **Fee family**: `TUITION`, `FEEDING`, `UNIFORM`, `TRANSPORT`, `ADMISSION`
- **Optional detail**: term, frequency, item, or route detail

Examples:
- `CFK01-TUITION-T1`
- `CFK01-FEEDING-MON`
- `CFK01-UNIFORM`
- `CFK01-TRANSPORT-MON`
- `CFK01-ADMISSION`

### 2. **Payment Flow**

#### For Parents via MoMo
1. Parent goes to MoMo agent
2. Agent asks: "What are you paying for?"
3. Parent says: "School fees for student CFK01"
4. Parent provides the structured reference (e.g. `CFK01-FEEDING-MON`)
5. MoMo sends payment with that reference to school
7. **System automatically records payment type** ✅

#### For Cash Payments at School
1. Parent/student visits school office
2. Staff asks: "What fee are you paying?"
3. Parent provides the structured reference or fee purpose
4. Staff enters the reference (e.g. `CFK01-FEEDING-MON`) or student ID + amount
5. **System automatically detects payment type** ✅

---

## Features

### Student Payment Tracker with Payment Codes (`/payment-tracker`)
**Finance Staff Dashboard:** Staff tool for viewing payment codes to communicate to parents

- ✅ View each student's payment status for Tuition, Feeding, Uniform, Transport
- ✅ Payment references section showing what references to tell parents
- ✅ Copy individual references to clipboard for quick communication
- ✅ Copy full payment instructions for sharing with parents
- ✅ Outstanding balance calculated per fee type
- ✅ Progress bars show payment completion

### Automatic Payment Tracking
**Backend:** Structured references are automatically parsed and logged

- ✅ Reference tells system which fee was paid
- ✅ No more manual fee type selection
- ✅ Reduces data entry errors
- ✅ Works with existing MoMo webhook system
- ✅ Works with cash payments at school

---

## Payment Code API Endpoints

### 1. **Get Student Payment Codes**
```
GET /api/students/{student_id}/payment-codes
```

**Response:**
```json
{
  "student_id": 1,
  "student_name": "John Lamptey",
  "student_code": "CFK01",
  "class": "JHS 2",
  "parent_phone": "+233501234567",
  "payment_codes": [
    {
      "fee_type": "Tuition",
      "code": "CFK01-TUITION-T1",
      "amount": 5000.00,
      "instructions": "Pay GH₵ 5000.00 for Tuition. Use reference: CFK01-TUITION-T1"
    },
    {
      "fee_type": "Feeding",
      "code": "CFK01-FEEDING-MON",
      "amount": 500.00,
      "instructions": "Pay GH₵ 500.00 for Feeding. Use reference: CFK01-FEEDING-MON"
    },
    ...
  ],
  "note": "Parents should use the structured reference when making payments via MoMo, bank transfer, USSD, or at the school office."
}
```

### 2. **Record Payment with Reference Code**
```
POST /api/finance/receive-payment
```

**Option A - With Reference Code:**
```json
{
  "reference_code": "CFK01-FEEDING-MON",
  "amount": 500.00,
  "method": "MoMo"
}
```
✅ **System automatically determines:**
- Student ID: `CFK01`
- Payment Type: `Feeding` (from the reference token)
- Amount: `500.00`

**Option B - Traditional (still works):**
```json
{
  "student_id": 1,
  "type": "Tuition",
  "amount": 5000.00,
  "method": "Cash"
}
```

---

## Implementation Details

### Reference Parsing Logic
```python
# Example: Parse "CFK01-FEEDING-MON"
student_code = "CFK01"
payment_type = "Feeding"
payment_category = {"frequency": "Monthly"}

# Works for:
# CFK01-TUITION-T1 → Student CFK01, Tuition, Term 1
# CFK01-FEEDING-MON → Student CFK01, Feeding, Monthly
# CFK01-UNIFORM → Student CFK01, Uniform
# ABC123-ADMISSION → Student ABC123, Admission
```

### Custom Fees Mapping
When school adds custom fees like "Sports" or "Library", use readable fee tokens:
```
CFK01-SPORTS
CFK01-LIBRARY
CFK01-ART-MATERIALS
```

The format should stay readable enough for staff and parents to understand without memorizing numeric suffixes.

---

## Database Changes
No schema changes needed - uses existing `reference_id` column in Payment table.

---

## User Flow Diagrams

### Parent View
```
Parent logs in → "💳 Payment Codes" link
    ↓
Selects child (e.g., John)
    ↓
Sees all payment codes:
  • Tuition: CFK011 (GH₵ 5000)
  • Feeding: CFK012 (GH₵ 500)
  • Uniform: CFK013 (GH₵ 300)
  • Transport: CFK014 (GH₵ 200)
    ↓
Copies code → Gives to MoMo agent
    ↓
MoMo sends payment with code
    ↓
School system auto-records:
  ✓ Student: CFK01
  ✓ Fee Type: Feeding
  ✓ Amount: GH₵ 500
```

### Finance Staff View
```
Finance opens "💳 Payment Tracker"
    ↓
Searches for student (e.g., John Lamptey)
    ↓
Sees payment breakdown:
  • Tuition: GH₵ 3000 paid / GH₵ 5000 required
  • Feeding: GH₵ 500 paid / GH₵ 500 required ✅
  • Uniform: GH₵ 0 paid / GH₵ 300 required
  • Transport: GH₵ 0 paid / GH₵ 200 required
    ↓
Outstanding: GH₵ 1700
```

---

## Files Modified/Created

| File | Changes |
|------|---------|
| [backend/utils.py](backend/utils.py) | Added 5 payment code functions |
| [backend/routes.py](backend/routes.py) | Updated receive-payment endpoint + new payment-codes endpoint |
| [frontend/react/src/components/StudentPaymentTracker.jsx](frontend/react/src/components/StudentPaymentTracker.jsx) | ENHANCED: Added payment codes display section for staff to see codes to share with parents |

---

## Testing the System

### Test 1: Generate Payment Codes
```python
from backend.utils import generate_payment_code
code = generate_payment_code("CFK01", "Feeding")
# Result: "CFK012"
```

### Test 2: Parse Payment Code
```python
from backend.utils import parse_payment_code
student_id, fee_type = parse_payment_code("CFK012")
# Result: ("CFK01", "Feeding")
```

### Test 3: Generate All Codes for Student
```python
from backend.utils import generate_all_payment_codes
fees = {
    "tuition_fee": 5000,
    "feeding_fee": 500,
    "uniform_fee": 300,
    "transport_fee": 200,
    "other_fees": {"Sports": 100}
}
codes = generate_all_payment_codes("CFK01", fees)
# Result: {
#   "Tuition": "CFK011",
#   "Feeding": "CFK012",
#   "Uniform": "CFK013",
#   "Transport": "CFK014",
#   "Sports": "CFK015"
# }
```

---

## Next Steps

1. **Apply any database migrations** (if needed)
2. **Test in development:**
   - Set school fees in Settings
   - View `/parent-payments` as a parent role
   - Try recording payments with reference codes
3. **Configure MoMo webhook** to accept reference codes
4. **Train staff** on new payment code system
5. **Communicate to parents** about payment codes

---

## FAQ

**Q: What if parent gets the code wrong?**
A: System will reject the code or record for wrong student. Staff should verify before accepting payment.

**Q: Can we still use student IDs?**
A: Yes! Both codes and IDs work:
- Reference code for automated MoMo
- Student ID for manual cash entries

**Q: What about MoMo providers?**
A: Requires updating MoMo webhook settings to include reference code in payment info.

**Q: Can codes change?**
A: No, they're deterministic. `CFK01` + `Feeding` always = `CFK012`

