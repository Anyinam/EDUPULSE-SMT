# Payment Reference System (MoMo + Bank + Cash Tracking)

## Overview
EduPulse should now treat structured references as the primary school-fee instruction model. Parents and guardians pay with one stable learner identity plus a readable payment-purpose reference that tells EduPulse what the payment is for.

**Example:**
- Stable learner identifier: `S001`
- Tuition reference: `S001-T1`
- Feeding reference: `S001-FEED-MON`
- Uniform reference: `S001-UNIF`
- Transport reference: `S001-TRANS-MON`

Legacy note:
- older short payment-code patterns can still be recognized where already deployed
- new school communication should favor the clearer structured-reference format

---

## How It Works

### 1. **Reference Generation**
The system generates references from:
- **Stable learner identifier**: e.g. `S001` (usually the student's school code)
- **Fee family**: `T1/T2/T3`, `FEED`, `UNIF`, `TRANS`, `ADMISSION`
- **Optional detail**: term, frequency, item, or route detail

Examples:
- `S001-T1`
- `S001-FEED-DAY`
- `S001-FEED-WEK`
- `S001-FEED-MON`
- `S001-UNIF`
- `S001-TRANS-MON`
- `S001-ADMISSION`

### 2. **Payment Flow**

#### For Parents via MoMo
1. Parent goes to MoMo agent
2. Agent asks: "What are you paying for?"
3. Parent says: "School fees for student S001"
4. Parent provides the structured reference (e.g. `S001-FEED-MON`)
5. MoMo sends payment with that reference to school
7. **System automatically records payment type** ✅

#### For Cash Payments at School
1. Parent/student visits school office
2. Staff asks: "What fee are you paying?"
3. Parent provides the structured reference or fee purpose
4. Staff enters the reference (e.g. `S001-FEED-MON`) or the student's identifier plus amount
5. **System automatically detects payment type** ✅

### Feeding Plan References
When a school configures feeding plans separately, EduPulse issues one feeding reference per plan:

- `S001-FEED-DAY` for the daily feeding plan
- `S001-FEED-WEK` for the weekly feeding plan
- `S001-FEED-MON` for the monthly feeding plan

The first segment is the student's stable identifier in the school system. The last segment tells EduPulse whether the payment is daily, weekly, or monthly.

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
  "student_code": "S001",
  "class": "JHS 2",
  "parent_phone": "+233501234567",
  "payment_codes": [
    {
      "fee_type": "Tuition + Terminal Report",
      "code": "S001-T1",
      "amount": 5000.00,
      "instructions": "Pay GH₵ 5000.00 for Tuition. Use reference: S001-T1"
    },
    {
      "fee_type": "Feeding (Monthly)",
      "code": "S001-FEED-MON",
      "amount": 500.00,
      "instructions": "Pay GH₵ 500.00 for monthly feeding. Use reference: S001-FEED-MON"
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
  "reference_code": "S001-FEED-MON",
  "amount": 500.00,
  "method": "MoMo"
}
```
✅ **System automatically determines:**
- Student identifier: `S001`
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
# Example: Parse "S001-FEED-MON"
student_code = "S001"
payment_type = "Feeding"
payment_category = {"frequency": "Monthly"}

# Works for:
# S001-T1 → Student S001, Tuition, Term 1
# S001-FEED-MON → Student S001, Feeding, Monthly
# S001-UNIF → Student S001, Uniform
# ABC123-ADMISSION → Student ABC123, Admission
```

### Custom Fees Mapping
When school adds custom fees like "Sports" or "Library", use readable fee tokens:
```
S001-SPORTS
S001-LIBRARY
S001-ART-MATERIALS
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
  • Tuition: S001-T1 (GH₵ 5000)
  • Feeding Daily: S001-FEED-DAY (GH₵ 5)
  • Feeding Weekly: S001-FEED-WEK (GH₵ 25)
  • Feeding Monthly: S001-FEED-MON (GH₵ 500)
  • Uniform: S001-UNIF (GH₵ 300)
  • Transport: S001-TRANS-MON (GH₵ 200)
    ↓
Copies code → Gives to MoMo agent
    ↓
MoMo sends payment with code
    ↓
School system auto-records:
  ✓ Student: S001
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
| [backend/utils.py](backend/utils.py) | Structured reference parsing for tuition, feeding, transport, and custom fee identifiers |
| [backend/routes.py](backend/routes.py) | Payment-code payloads, feeding-plan references, and manual receive-payment reference resolution |
| [frontend/react/src/components/PaymentInstructions.jsx](frontend/react/src/components/PaymentInstructions.jsx) | Parent-facing payment cards now show plan-aware feeding references |
| [frontend/react/src/components/SettingsPanel.jsx](frontend/react/src/components/SettingsPanel.jsx) | School fee settings now support daily, weekly, and monthly feeding plans |

---

## Testing the System

### Test 1: Generate Payment Codes
```python
from backend.utils import generate_all_payment_codes
fees = {"feeding_fee": 500}
codes = generate_all_payment_codes("S001", fees)
# Result includes {"Feeding": "S0012"} for legacy compact codes where used
```

### Test 2: Parse Structured Reference
```python
from backend.utils import parse_payment_reference
parsed = parse_payment_reference("S001-FEED-WEK")
# Result: {"student_code": "S001", "payment_type": "Feeding", "category": {"frequency": "Weekly"}}
```

### Test 3: Parent Instruction Payload
```python
payment_codes = [
  "S001-T1",
  "S001-FEED-DAY",
  "S001-FEED-WEK",
  "S001-FEED-MON",
  "S001-UNIF",
]
```

---

## Next Steps

1. **Apply any database migrations** (if needed)
2. **Test in development:**
   - Set school fees in Settings
  - Configure daily, weekly, and monthly feeding plans if the school charges feeding by plan
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
A: Yes, but distinguish them clearly:
- The payment reference begins with the student's stable school identifier, usually the student code.
- Manual cash entry can still use the student's identifier directly when staff are not using the full structured reference.

**Q: What about MoMo providers?**
A: Requires updating MoMo webhook settings to include reference code in payment info.

**Q: Can codes change?**
A: The structured reference stays deterministic for the same learner and fee purpose. For feeding, the suffix changes by plan: `FEED-DAY`, `FEED-WEK`, or `FEED-MON`.

