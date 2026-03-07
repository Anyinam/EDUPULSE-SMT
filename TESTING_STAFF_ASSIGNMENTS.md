# Testing Checklist - Teacher Assignment System

## Quick Start Testing

### Setup Phase
- [ ] Ensure database is properly migrated (TeacherAssignment table exists)
- [ ] Restart backend server to load updated routes
- [ ] Clear browser cache/localStorage if needed

### Test 1: Add Teacher with Assignments
**Steps:**
1. Log in as proprietor
2. Navigate to Staff Management
3. Fill form:
   - Username: `test_math`
   - Email: `math@test.com`
   - Password: `Test123!`
   - Roles: Check "Teacher"
   - Homeroom Class: (leave blank)
   - Classes to Teach: `JHS 1, JHS 2`
   - Subjects to Teach: `Mathematics, English`
4. Click "Add Staff"

**Expected Results:**
- ✅ Alert shows "Staff member added successfully!"
- ✅ New teacher appears in staff list
- ✅ Teaching Classes column shows: "JHS 1, JHS 2"
- ✅ Teaching Subjects column shows: "English, Mathematics" (alphabetic order)
- ✅ Database: 4 TeacherAssignment records created (2 classes × 2 subjects)

### Test 2: Edit Teacher Assignments
**Steps:**
1. In staff list, click "Edit" on test_math row
2. Change:
   - Classes to Teach: `JHS 1, JHS 3`
   - Subjects to Teach: `Mathematics`
3. Click "Save"

**Expected Results:**
- ✅ Alert shows "Staff member updated successfully!"
- ✅ Table updates to show:
   - Teaching Classes: "JHS 1, JHS 3"
   - Teaching Subjects: "Mathematics"
- ✅ Database: Old 4 records deleted, new 2 records created

### Test 3: Verify Timetable Filtering
**Setup:** Ensure timetable entries exist for:
- JHS 1, Mathematics
- JHS 1, English
- JHS 2, Mathematics
- JHS 2, English (not assigned to test_math)
- SHS 1, Mathematics (not assigned)

**Steps:**
1. Log out from proprietor
2. Log in as test_math
3. Navigate to Timetable (or My Schedule)
4. Observe timetable entries

**Expected Results:**
- ✅ Only entries matching (JHS 1, Mathematics) or (JHS 3, Mathematics) are visible
- ✅ No JHS 2 entries appear (not in updated list)
- ✅ No SHS 1 entries appear

### Test 4: Teacher with Multiple Subjects, Single Class
**Steps:**
1. Add new teacher:
   - Username: `test_english`
   - Classes to Teach: `JHS 1`
   - Subjects to Teach: `English, French, Swahili`
2. Verify staff list display

**Expected Results:**
- ✅ Teaching Classes: "JHS 1"
- ✅ Teaching Subjects: "English, French, Swahili" (alphabetic)
- ✅ Database: 3 TeacherAssignment records (1 class × 3 subjects)

### Test 5: Homeroom Teacher Assignment
**Steps:**
1. Add new staff:
   - Username: `test_homeroom`
   - Role: Check "Homeroom Teacher"
   - Homeroom Class: `JHS 2`
   - Classes to Teach: `JHS 2, JHS 3`
   - Subjects to Teach: `Social Studies`
2. Verify staff list display

**Expected Results:**
- ✅ Homeroom column shows: "JHS 2"
- ✅ Teaching Classes: "JHS 2, JHS 3"
- ✅ Teaching Subjects: "Social Studies"
- ✅ Both fields display (Homeroom Teacher role includes teacher privileges)

### Test 6: Non-Teacher Staff (No Assignments)
**Steps:**
1. Add new staff:
   - Username: `test_finance`
   - Role: Check "Finance Officer"
   - Leave assignment fields blank
2. Try to edit this staff member

**Expected Results:**
- ✅ "Classes to Teach" field shows "-" in table
- ✅ "Subjects to Teach" field shows "-" in table
- ✅ Edit mode: assignment fields are hidden for Finance Officer role
- ✅ No TeacherAssignment records created

### Test 7: Empty/Whitespace Handling
**Steps:**
1. Add teacher with:
   - Classes to Teach: `  JHS 1  ,  , JHS 2  ` (with extra spaces and empty entries)
   - Subjects to Teach: `, Mathematics ,` (with commas but empty entries)
2. Save and observe display

**Expected Results:**
- ✅ Trimmed properly: "JHS 1, JHS 2"
- ✅ Empty entries filtered: "Mathematics"
- ✅ Database reflects cleaned values (no extra spaces)

### Test 8: Assignment Clear on Role Remove
**Steps:**
1. Edit test_math to remove "Teacher" role
   - Uncheck "Teacher"
   - Keep only other roles (if any)
2. Save

**Expected Results:**
- ✅ Teaching Classes and Subjects columns show "-" in table
- ✅ Database: All TeacherAssignment records deleted
- ✅ Cannot edit assignment fields in edit mode

### Test 9: Cancel Edit Without Changes
**Steps:**
1. Click "Edit" on any staff member
2. Make a change to Classes field
3. Click "Cancel" without saving
4. Edit again

**Expected Results:**
- ✅ Original values retained (edit was not saved)
- ✅ Assignment fields show original values on second edit

### Test 10: Conflict Prevention (Unique Constraint)
**Note:** Manual database test - this should be handled by ORM

**Expected Behavior:**
- System prevents duplicate (school_id, teacher_id, class_name, subject_name) records
- If assignment already exists, system silently skips or updates

## API Response Verification

### GET /api/staff/list Response Format
```json
{
  "id": 42,
  "username": "test_math",
  "email": "math@test.com",
  "role": "teacher",
  "roles": ["teacher"],
  "assigned_class": null,
  "assigned_classes": ["JHS 1", "JHS 2"],
  "assigned_subjects": ["English", "Mathematics"]
}
```
- [ ] assigned_classes is array (not comma-separated string)
- [ ] assigned_subjects is array
- [ ] Both arrays are sorted alphabetically
- [ ] Both fields are present (never undefined)

### GET /api/teacher/assignments (as teacher) Response Format
```json
{
  "classes": ["JHS 1", "JHS 3"],
  "subjects": ["Mathematics"],
  "pairs": [
    { "class_name": "JHS 1", "subject_name": "Mathematics" },
    { "class_name": "JHS 3", "subject_name": "Mathematics" }
  ]
}
```
- [ ] Returns only current teacher's assignments
- [ ] Pairs list shows all (class, subject) combinations

### POST /api/staff/add Request Format
```json
{
  "username": "test_teacher",
  "email": "test@school.com",
  "password": "SecurePass123",
  "roles": ["teacher"],
  "assigned_class": null,
  "assigned_classes": ["JHS 1", "JHS 2"],
  "assigned_subjects": ["Math", "Science"]
}
```
- [ ] assigned_classes as array
- [ ] assigned_subjects as array
- [ ] Backend correctly creates 2×2=4 assignment records

### PUT /api/staff/<id> Request Format
```json
{
  "roles": ["teacher"],
  "assigned_class": "JHS 1",
  "assigned_classes": ["JHS 1", "JHS 3"],
  "assigned_subjects": ["Mathematics"]
}
```
- [ ] Old assignments are deleted
- [ ] New assignments are created
- [ ] Response includes updated user data

## Database Verification

### Ensure TeacherAssignment Table Exists
```sql
DESCRIBE teacher_assignment;
-- Should show columns: id, school_id, teacher_id, class_name, subject_name, created_at

SELECT COUNT(*) FROM teacher_assignment;
-- After Test 1: Should be 4

SELECT COUNT(*) FROM teacher_assignment;
-- After Test 2: Should be 2 (old deleted, new created)
```

### Check Unique Constraint
```sql
SHOW INDEXES FROM teacher_assignment;
-- Should show unique constraint on (school_id, teacher_id, class_name, subject_name)
```

### Sample Query for Teacher
```sql
SELECT class_name, subject_name FROM teacher_assignment 
WHERE school_id = 1 AND teacher_id = 42 
ORDER BY class_name, subject_name;
-- Test_math should return: (JHS 1, Eng), (JHS 1, Math), (JHS 2, Eng), (JHS 2, Math)
-- Then after update: (JHS 1, Math), (JHS 3, Math)
```

## Browser DevTools Checks

### Network Tab
- [ ] POST /api/staff/add returns 200 with "Staff member added successfully"
- [ ] GET /api/staff/list returns 200 with array of staff objects
- [ ] PUT /api/staff/<id> returns 200 with "Staff member updated"
- [ ] assigned_classes and assigned_subjects appear in responses as arrays

### Console Warnings
- [ ] No JavaScript errors when adding/editing staff
- [ ] No warnings about undefined assigned_classes or assigned_subjects

### Component State (React DevTools, if available)
- [ ] formData.assigned_classes is array type
- [ ] editForm.assigned_subjects is array type
- [ ] State updates correctly when user types in text fields

## Known Limitations & Edge Cases

⚠️ **Current Implementation Notes:**
1. Class/Subject names are free-text input (case-sensitive, no validation against available classes/subjects)
   - Example: "JHS 1" ≠ "jhs 1" ≠ "Jhs 1"
   - Recommendation: Future PR to fetch available classes/subjects from `/api/school/classes` endpoint

2. No duplicate prevention at UI level (backend handles via unique constraint)
   - User could type "JHS 1" and "JHS 1" in same field → backend silently deduplicates
   - Recommendation: Show warning if duplicates detected

3. Timetable filtering requires timetable entries to match class_name and subject_name exactly
   - If timetable uses "Math" but assignment uses "Mathematics" → no match
   - Recommendation: Standardize subject names across the system

4. URL encoding required for class names with spaces
   - Frontend handles this in TimetableManager.jsx with `encodeURIComponent()`
   - Backend receives decoded value via Flask URL parsing

## Rollback Instructions (If Issues Found)

**To revert changes:**
```bash
# Frontend - restore original StaffManagement.jsx from git
git checkout frontend/react/src/features/StaffManagement.jsx

# Backend - revert routes.py stubs
git checkout backend/routes.py

# Database - drop TeacherAssignment table (careful!)
ALTER TABLE teacher_assignment DROP CONSTRAINT uk_teacher_assignment;
DROP TABLE teacher_assignment;
```

## Post-Testing Validation

After all tests pass:
1. [ ] No console errors or warnings
2. [ ] Staff list displays correctly (all columns visible)
3. [ ] Teacher can view their filtered timetable
4. [ ] Assignment changes propagate to timetable immediately
5. [ ] Multi-school isolation verified (test with second school if possible)
6. [ ] Performance acceptable (staff list loads quickly with many teachers)

---

**Status**: Ready for manual testing
**Prerequisites**: Database migrated, backend running, frontend dev server running
**Test Duration Estimate**: 30-45 minutes
