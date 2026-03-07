# Payment Reference Code System (MoMo + Cash Tracking)

## Overview
Parents/guardians can now pay school fees using **unique reference codes** that automatically track which fee type (Tuition, Feeding, Uniform, Transport) is being paid.

**Example:**
- Student ID: `CFK01`
- Tuition payment code: `CFK011`
- Feeding payment code: `CFK012`
- Uniform payment code: `CFK013`
- Transport payment code: `CFK014`

---

## How It Works

### 1. **Code Generation**
The system automatically generates codes based on:
- **Student code** (first part): e.g., `CFK01`
- **Payment type index** (last digit):
  - `1` = Tuition
  - `2` = Feeding
  - `3` = Uniform
  - `4` = Transport
  - `5+` = Custom fees (Sports, Library, etc.)

### 2. **Payment Flow**

#### For Parents via MoMo
1. Parent goes to MoMo agent
2. Agent asks: "What are you paying for?"
3. Parent says: "School fees for student CFK01"
4. Agent asks: "Which code?" 
5. Parent provides code (e.g., `CFK012` for feeding)
6. MoMo sends payment with reference code to school
7. **System automatically records payment type** ✅

#### For Cash Payments at School
1. Parent/student visits school office
2. Staff asks: "What fee are you paying?"
3. Parent provides code or fee type
4. Staff enters code (e.g., `CFK012`) or student ID + amount
5. **System automatically detects payment type** ✅

---

## Features

### Student Payment Tracker with Payment Codes (`/payment-tracker`)
**Finance Staff Dashboard:** Staff tool for viewing payment codes to communicate to parents

- ✅ View each student's payment status for Tuition, Feeding, Uniform, Transport
- ✅ **NEW:** Payment codes section showing what codes to tell parents
- ✅ Copy individual codes to clipboard for quick communication
- ✅ Copy full payment instructions for sharing with parents
- ✅ Outstanding balance calculated per fee type
- ✅ Progress bars show payment completion

### Automatic Payment Tracking
**Backend:** Codes are automatically parsed and logged

- ✅ Reference code tells system which fee was paid
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
      "code": "CFK011",
      "amount": 5000.00,
      "instructions": "Pay GH₵ 5000.00 for Tuition. Use reference code: CFK011"
    },
    {
      "fee_type": "Feeding",
      "code": "CFK012",
      "amount": 500.00,
      "instructions": "Pay GH₵ 500.00 for Feeding. Use reference code: CFK012"
    },
    ...
  ],
  "note": "Parents should reference the code when making payments via MoMo or at the school office."
}
```

### 2. **Record Payment with Reference Code**
```
POST /api/finance/receive-payment
```

**Option A - With Reference Code:**
```json
{
  "reference_code": "CFK012",
  "amount": 500.00,
  "method": "MoMo"
}
```
✅ **System automatically determines:**
- Student ID: `CFK01`
- Payment Type: `Feeding` (from the `2`)
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

### Code Parsing Logic
```python
# Example: Parse "CFK012"
student_code = "CFK01"      # First part (everything except last digit)
index = 2                    # Last digit
payment_type = "Feeding"     # Map: 2 → Feeding

# Works for:
# CFK011 → Student CFK01, Tuition
# CFK012 → Student CFK01, Feeding
# CFK013 → Student CFK01, Uniform
# ABC1231 → Student ABC123, Custom Fee #1
```

### Custom Fees Mapping
When school adds custom fees like "Sports" or "Library":
```
Sport = Index 5 → Code: CFK015
Library = Index 6 → Code: CFK016
Art = Index 7 → Code: CFK017
```

The order matches the order fees appear in the fee configuration.

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

