# Student Enrollment Status Guide

## Overview

EduPulse tracks student enrollment status for:
- **Subscription billing** (counts active students per term)
- **Enrollment management** (know who left, graduated, or transferred)
- **Audit trail** (tracks who changed status and when)
- **Analytics** (class distribution, graduation rates, retention metrics)

---

## Student Status Types

### 1. **Active** ✅
**Meaning**: Student is currently enrolled and attending school

**When to use**:
- All current students in school
- Students taking classes regularly
- Students paying tuition

**Who sets this**: Automatically set when student is admitted
- Set by proprietor or headmaster during admission
- Default status for new students

**Example**: "Students in JHS 1, JHS 2, JHS 3 right now"

---

### 2. **Graduated** 🎓
**Meaning**: Student completed all classes and has left the school

**When to use**:
- JHS 3 students who finished exams and left
- Primary 6 students who moved to JHS
- Any student who completed the school curriculum

**Who sets this**: Headmaster or Proprietor
- Usually batch updated at end of academic year
- Triggered after final exams and results
- Should be done before new term billing

**Financial impact**:
- **NOT counted** in subscription billing
- Pro-rata credit if changed during term

**Example time**: July when JHS 3 finishes

**Query to update**:
```sql
UPDATE students 
SET status = 'Graduated', status_reason = 'Completed JHS 3'
WHERE current_class = 'JHS 3' AND school_id = 1;
```

---

### 3. **Withdrawn** 🚪
**Meaning**: Student left school voluntarily (before graduation)

**When to use**:
- Parent withdrew child from school
- Student decided to stop midterm
- Family relocated
- Changed to another school (see "Transferred" for official transfer)

**Who sets this**: Headmaster or Proprietor
- Usually when parent notifies school
- Can happen at any time during term

**Financial impact**:
- **NOT counted** in subscription billing
- Pro-rata **CREDIT** applied for remaining days
- Example: Student leaves day 30 of 90-day term
  - Days remaining = 60
  - Per-student cost = 12 GHS
  - Credit = (60/90) × 12 = GH₵ 8

**Reason examples**:
- "Parent withdrew child for financial reasons"
- "Student moved to Accra"
- "Health reasons"

---

### 4. **Transferred** 📍
**Meaning**: Student officially transferred to another school (with record)

**When to use**:
- Student moving to a different school
- Parent requesting official transcript
- Inter-school transfers with documentation

**Who sets this**: Headmaster or Proprietor
- Usually by request from receiving school
- Accompanied by transfer letter/transcript

**Financial impact**:
- **NOT counted** in subscription billing
- Pro-rata **CREDIT** applied
- Receiving school's EduPulse system will add as new student

**Reason examples**:
- "Transferred to Adisadel College"
- "Moved to another school with better boarding facilities"

---

### 5. **Suspended** 🚷
**Meaning**: Student is temporarily removed from school (still enrolled)

**When to use**:
- Disciplinary suspension (2 weeks, 1 month, etc.)
- Medical leave pending return
- Administrative hold

**Who sets this**: Headmaster or Proprietor
- Due to disciplinary issues
- Medical/health reasons

**Financial impact**:
- **STILL COUNTED** in subscription billing
- Parent still pays tuition
- Assumption: suspension is temporary and student will return

**Reason examples**:
- "Suspended for 2 weeks - disciplinary action"
- "Medical leave - expected return in 2 weeks"

**How to revert**: Update status back to "Active" when suspension ends

---

### 6. **Inactive** 💤
**Meaning**: Student record exists but not currently active (data retention)

**When to use**:
- Student took long leave but didn't formally withdraw
- Placeholder while investigating enrollment status
- Test/duplicate student entries

**Who sets this**: Headmaster or Proprietor
- Administrative use only

**Financial impact**:
- **NOT counted** in subscription billing
- Can revert to "Active" if student returns

**Example**: "Student on extended medical leave - status unclear"

---

## How Student Status Updates Work

### Who Can Change Status?
- ✅ **Proprietor** - Can change ANY student's status
- ✅ **Headmaster** - Can change ANY student's status
- ❌ Teachers - Read-only (see student status but cannot change)
- ❌ Parents - No access (don't see status)

### Accessing Enrollment Management

### Bulk Status Update (Recommended Approach) ⚡
Both Proprietor and Headmaster have quick-access buttons for bulk operations:

**Proprietor:**
```
Dashboard → Admissions Tab → [⚡ Bulk Status Update Button]
```

**Headmaster:**
```
Dashboard → [⚡ Bulk Status Update Button at top]
```

### How to Use Bulk Status Update

**Perfect for**: Marking all students in a class as Graduated after BECE exams

**Steps**:
1. Click ⚡ **Bulk Status Update** button (blue banner)
2. Select class (e.g., "JHS 3") - pre-filled with most common choice
3. Select new status (Graduated, Withdrawn, etc.)
4. Add reason (optional): e.g., "Completed BECE exams"
5. Click **Update [Class Name]**
6. ✅ All active students in that class updated instantly!

**Example**: Updating 45 JHS 3 students from Active → Graduated
- **With bulk update**: 5 clicks, ~2 seconds ⚡
- **Manual alternative**: Individual Edit for each student = 45 clicks, ~10 minutes 😴

### Real-World Examples

**Scenario 1: End of Year Graduation**
- **Current Status**: Active (in JHS 3)
- **New Status**: Graduated
- **Reason**: "Completed JHS 3, passed final exams"
- **When**: July 31, 2026
- **Impact**: No longer counted in billing for Term 1 (Sept 2026)

**Scenario 2: Student Left Mid-Term**
- **Current Status**: Active (in JHS 1)
- **New Status**: Withdrawn
- **Reason**: "Parent withdrew - moving to Ghana"
- **When**: March 15, 2026 (20 days into 90-day term)
- **Impact**: Credit of (70/90) × 12 GHS ≈ GH₵ 9.33 applied to next bill

**Scenario 3: Disciplinary Suspension**
- **Current Status**: Active  
- **New Status**: Suspended
- **Reason**: "Suspended for 2 weeks - disciplinary action"
- **When**: February 28, 2026
- **Impact**: Still billed; automatically change back to Active on March 14
- **Note**: Setting reminder to revert status is recommended

---

## Data Fields for Student Status

### Database Fields
```sql
-- Student status tracking columns
status VARCHAR(20) DEFAULT 'Active'
  -- Valid values: Active, Graduated, Withdrawn, Transferred, Suspended, Inactive

status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  -- When status was last changed

status_updated_by_user_id INTEGER (FK to users)
  -- WHO made the change (proprietor/headmaster username)

status_reason VARCHAR(255)
  -- WHY status was changed (human-readable explanation)
```

### API Response
When viewing a student in Enrollment Management:
```json
{
  "id": 5,
  "name": "Ama Asante",
  "student_code": "S001",
  "current_class": "JHS 3",
  "status": "Graduated",
  "status_reason": "Completed JHS 3, passed final exams",
  "status_updated_at": "2026-07-31T15:30:00Z",
  "status_updated_by": "headmaster_kobe",
  "parent_name": "James Asante",
  "parent_phone": "+233508123456",
  "parent_email": "james@example.com"
}
```

---

## Billing Impact by Status

| Status | Counted? | Billing Impact | When to Use |
|--------|----------|---|---|
| **Active** | ✅ YES | Full term charge | Current students |
| **Graduated** | ❌ NO | Pro-rata credit (if mid-term) | End of year |
| **Withdrawn** | ❌ NO | Pro-rata credit (remaining days) | Student left |
| **Transferred** | ❌ NO | Pro-rata credit | Applied to other school |
| **Suspended** | ✅ YES | Full charge (assumed temporary) | Disciplinary/medical hold |
| **Inactive** | ❌ NO | No charge (unverified status) | Unknown/test records |

### Pro-Rata Credit Calculation
When a student's status changes from **Active** to **Graduated/Withdrawn/Transferred**:

```
Credit = (Days Remaining / Total Term Days) × (Per-Student Cost)
```

**Example**:
- Term length: 90 days
- Student changes status on day 40
- Days Remaining: 50
- Per-student cost: GH₵ 12
- **Credit**: (50/90) × 12 = **GH₵ 6.67**

---

## Viewing Enrollment Statistics

### Dashboard Cards Show:
- **Active Students**: Currently enrolled students (used for billing)
- **Graduated**: Completed their years
- **Withdrawn**: Left mid-year
- **Transferred**: Moved to another school
- **Suspended**: Temporarily out (still charged)
- **Inactive**: Unverified/test records
- **Total Enrollment**: Sum of all statuses

### Class Distribution
View how many active students in each class:
- JHS 1: 45 students
- JHS 2: 38 students
- JHS 3: 42 students

### Gender Distribution
View active students by gender:
- Male: 75 students
- Female: 65 students
- Other: 2 students

---

## Audit Trail & Compliance

Every status change is logged with:
1. **Who changed it**: Username of proprietor/headmaster
2. **When changed**: Exact timestamp
3. **New status**: What it changed to
4. **Reason**: Explanation provided
5. **Previous status**: What it was before

### View Change History
```bash
Dashboard → Audit Logs
Filter: Type = "STUDENT_STATUS_UPDATED"
Sort: By Date (newest first)
```

---

## Common Scenarios & How to Handle

### Scenario 1: End of Academic Year - Mark All JHS 3 as Graduated ⚡
**Task**: After BECE exams, mark all JHS 3 students as "Graduated" (45 students)

**Using Bulk Status Update (RECOMMENDED)**:
1. Click ⚡ **Bulk Status Update** button
2. Class: **JHS 3** (already selected)
3. New Status: **Graduated**
4. Reason: **"Completed JHS 3, passed BECE exams"**
5. Click **Update JHS 3**
6. ✅ **Result**: All 45 students updated in 2 seconds!

**Time saved**: ~8 minutes vs. clicking Edit on each student individually

**Finance Impact**: 
- These students no longer counted in billing
- Pro-rata credit applied if changed mid-term

---

### Scenario 2: Mid-Term Withdrawal (Single Student)
**Task**: One student leaves school mid-term

**Steps**:
1. Use API endpoint: `PUT /api/admissions/students/<id>/status`
2. Status: **Withdrawn**
3. Reason: **"Parent withdrew - family moved"**
4. Submit

**Finance Impact**: 
- Automatic pro-rata credit: (Days Remaining / Term Days) × per-student cost
- Example: Left day 40 of 90-day term = ~GH₵ 6.67 credit

---

### Scenario 3: Discipline - Suspend Multiple Students
**Task**: Suspend 3 students for disciplinary reasons

**Option A - Bulk (if all same class)**:
1. Use ⚡ Bulk Status Update
2. Class: **[Their Class]**
3. Status: **Suspended**
4. Reason: **"Suspended for 2 weeks - disciplinary action"**
5. Note: Will also suspend any other Active students in that class

**Option B - Individual (if different classes)**:
1. Update each student individually via API
2. Status: **Suspended**
3. Reason: **"Suspended for 2 weeks - disciplinary action"**

**Finance Impact**: Still charged (assumed temporary)  
**Reminder**: Set calendar reminder to change back to "Active" when suspension ends

**Finance Impact**: Still charged for this term

---

### Scenario: Mid-Term Withdrawal
**Task**: Student leaves, parent requests pro-rata refund

**Steps**:
1. Go to Enrollment Management
2. Find student
3. Click Edit
4. Change to "Withdrawn"
5. Reason: Why student left (parent request, moved, etc.)
6. Submit

**Finance Impact**: 
- Automatic pro-rata credit calculated
- Shown on next billing statement
- Example: Left day 40 of 90-day term
  - Credit = (50/90) × 12 = ~GH₵ 6.67

---

### Scenario: Transfer to Another School
**Task**: Student transferred; provide transcript

**Steps**:
1. Go to Enrollment Management
2. Find student
3. Click Edit
4. Change to "Transferred"
5. Reason: "Transferred to Adisadel College"
6. Submit

**Finance Impact**: Pro-rata credit applied

---

## API Endpoints for Developers

### Get All Students (with status filter)
```http
GET /api/admissions/students?status=Active&class=JHS1
Authorization: Bearer <token>
```

**Response**:
```json
{
  "total_students": 120,
  "status_breakdown": {
    "Active": 95,
    "Graduated": 15,
    "Withdrawn": 10
  },
  "students": [...]
}
```

### Update Student Status
```http
PUT /api/admissions/students/<id>/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "Graduated",
  "reason": "Completed JHS 3"
}
```

### Get Enrollment Statistics
```http
GET /api/admissions/statistics
Authorization: Bearer <token>
```

**Response**:
```json
{
  "status_summary": {
    "active": 95,
    "graduated": 15,
    "withdrawn": 10,
    "transferred": 2,
    "suspended": 3,
    "inactive": 0,
    "total": 125
  },
  "class_distribution": {
    "JHS 1": 45,
    "JHS 2": 38,
    "JHS 3": 12
  },
  "gender_distribution": {
    "Male": 75,
    "Female": 50
  }
}
```

---

## Frequently Asked Questions

**Q: Can I change a student's status without a reason?**  
A: Yes, reason is optional. But it's recommended for audit trail and parent communication.

**Q: Will my subscription bill change if I mark a student as Withdrawn?**  
A: Yes! That student is no longer counted as "Active", and you get a pro-rata credit for remaining days.

**Q: Can teachers see which students are withdrawn/graduated?**  
A: No, teachers only see active students. They cannot access the Enrollment Management page.

**Q: What happens if I suspend a student but forget to change back to Active?**  
A: They stay suspended - you're still charged BUT they won't appear in normal class reports. Set a calendar reminder!

**Q: Can I force download a list of all students (Active/Graduated/etc.)?**  
A: Yes! Click "Export CSV" button in Enrollment Management. Downloads filtered list in Excel-friendly format.

**Q: Do parents get notified when their child's status changes?**  
A: Not yet - this is a coming feature. Currently only admin action log tracks it.

**Q: What if I accidentally mark a student as Graduated when they should be Active?**  
A: Just edit them again and change back to "Active". The change will be logged in audit trail.

---

## Implementation Summary

✅ Student status field in database (6 valid statuses)
✅ Bulk status update (for all students in a class at once)
✅ Status update via API endpoints
✅ Subscription billing integration (only "Active" counted)
✅ Audit logging for all status changes
✅ Status statistics dashboard
✅ Pro-rata credit calculation for mid-term changes

🔄 **Coming Soon**:
- Individual student UI (currently API-only, coming in v2)
- Email notifications to parents on status change
- Graphical enrollment trends
- Student status search/filter
- Automatic end-of-year graduation prompts

---

## Support

**For schools**: Contact support@edupulse.com with enrollment questions

**For developers**: Check `/api/admissions/*` endpoints in API docs

**Audit trail**: Dashboard → Logs → Filter by type="STUDENT_STATUS_UPDATED"
