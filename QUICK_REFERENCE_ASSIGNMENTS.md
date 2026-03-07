# Teacher Assignment System - Quick Reference

## What's New

✅ **Staff Management now has assignment fields:**
- Classes to Teach (comma-separated input)
- Subjects to Teach (comma-separated input)

✅ **Staff List Table shows:**
- Teaching Classes column
- Teaching Subjects column

✅ **Teachers get filtered timetables:**
- Only see classes and subjects they're assigned to teach

## One-Minute Setup

### 1. Database Ready?
✅ TeacherAssignment table exists (created in previous session)

### 2. Backend Ready?
✅ All endpoints configured in routes.py:
- `/api/staff/add` - accepts assignments
- `/api/staff/list` - returns assignments
- `/api/staff/<id>` PUT - updates assignments
- `/api/teacher/assignments` - gets current teacher's assignments
- `/api/timetable/my` - filters by assignments

### 3. Frontend Ready?
✅ StaffManagement.jsx updated with UI for assignments

## How to Test (3 Minutes)

### Test 1: Add Teacher
```
1. Go to Staff Management
2. Fill: Username="teacher1", Email="t@t.com", Password="test"
3. Check "Teacher" role
4. Set Classes: "JHS 1, JHS 2"
5. Set Subjects: "Math, English"
6. Click Add Staff
7. ✅ Should appear in list with classes/subjects shown
```

### Test 2: Verify Filtering
```
1. Log in as teacher1
2. Go to Timetable
3. ✅ Only should see entries for (JHS 1, Math), (JHS 1, English), (JHS 2, Math), (JHS 2, English)
```

### Test 3: Edit Assignment
```
1. Go to Staff Management
2. Click Edit on teacher1
3. Change Classes to: "JHS 1"
4. Change Subjects to: "Math"
5. Click Save
6. Re-login as teacher1, check timetable
7. ✅ Should only see 1 slot: (JHS 1, Math)
```

## Code Changes Summary

### File: frontend/react/src/features/StaffManagement.jsx

**What Changed:**
- State expanded with `assigned_classes: []` and `assigned_subjects: []`
- Form inputs accept comma-separated class/subject names
- Table columns added for Teaching Classes and Teaching Subjects
- Edit mode allows updating assignments inline

**Key Changes:**
```jsx
// Before
const [formData, setFormData] = useState({
  username: '', email: '', password: '', roles: ['teacher'], assigned_class: ''
});

// After
const [formData, setFormData] = useState({
  username: '', email: '', password: '', roles: ['teacher'], assigned_class: '',
  assigned_classes: [],
  assigned_subjects: []
});
```

**New Form Inputs:**
```jsx
<input 
  placeholder="Classes to Teach (comma-separated)"
  value={formData.assigned_classes.join(', ')}
  onChange={(e) => setFormData({ 
    ...formData, 
    assigned_classes: e.target.value.split(',').map(c => c.trim()).filter(c => c)
  })}
/>

<input 
  placeholder="Subjects to Teach (comma-separated)"
  value={formData.assigned_subjects.join(', ')}
  onChange={(e) => setFormData({ 
    ...formData, 
    assigned_subjects: e.target.value.split(',').map(s => s.trim()).filter(s => s)
  })}
/>
```

**New Table Columns:**
```jsx
<th className="p-4">Teaching Classes</th>
<th className="p-4">Teaching Subjects</th>
```

## API Format Reference

### Request to Add Teacher with Assignments
```json
POST /api/staff/add
{
  "username": "math_teacher",
  "email": "math@school.com",
  "password": "SecurePass",
  "roles": ["teacher"],
  "assigned_class": null,
  "assigned_classes": ["JHS 1", "JHS 2"],
  "assigned_subjects": ["Mathematics"]
}
```

### Response from GET /api/staff/list
```json
[
  {
    "id": 42,
    "username": "math_teacher",
    "email": "math@school.com",
    "role": "teacher",
    "roles": ["teacher"],
    "assigned_class": null,
    "assigned_classes": ["JHS 1", "JHS 2"],
    "assigned_subjects": ["Mathematics"]
  }
]
```

### Timetable Entries Created
Since teacher is assigned to:
- Classes: ["JHS 1", "JHS 2"]
- Subjects: ["Mathematics"]

Database creates TeacherAssignment records:
```sql
INSERT INTO teacher_assignment VALUES
(NULL, 1, 42, "JHS 1", "Mathematics", NOW()),
(NULL, 1, 42, "JHS 2", "Mathematics", NOW());
```

When teacher views timetable, only slots matching these pairs are shown.

## Common Questions

### Q: What if I enter "JHS 1, , JHS 2" (with empty)?
**A:** Empty entries are filtered out. Result: ["JHS 1", "JHS 2"]

### Q: What if I enter "JHS 1, JHS 1" (duplicate)?
**A:** Database unique constraint prevents duplicate assignments. Backend only creates one record.

### Q: Can teacher be assigned to a class without any subjects?
**A:** No. Assignment requires both class AND subject (many-to-many model).

### Q: What if timetable has "Mathematics" but assignment says "Math"?
**A:** No match. Names must be exact. Timetable backend filters by exact string match.

### Q: Do teachers see assignments affecting their grade entry subjects?
**A:** No. Assignment filters affect only the Timetable ("My Schedule"). Grade entry subject selection is still independent.

### Q: Can I assign same class to multiple subjects for one teacher?
**A:** Yes. Each (class, subject) pair is separate. One teacher can teach both Math and English in JHS 1.

## Troubleshooting

### Assignments not saving?
1. Check browser console for errors (F12)
2. Check Network tab - does PUT request show 200 OK?
3. Try refreshing page
4. Check database directly: `SELECT * FROM teacher_assignment WHERE teacher_id = ?`

### Timetable not filtered?
1. Verify assignments exist in database
2. Verify timetable has entries matching class_name AND subject_name exactly
3. Check if teacher is viewing as "My Schedule" (should filter) vs "All Timetable" (shouldn't filter)
4. Verify school_id in filters matches current teacher's school

### Assignments field not showing?
1. Ensure staff member has "Teacher" or "Homeroom" role checked
2. Fields only display for teacher roles
3. Try refreshing page

## Files Involved

**Frontend:**
- `/frontend/react/src/features/StaffManagement.jsx` - MODIFIED (UI for assignments)
- `/frontend/react/src/components/TimetableManager.jsx` - Already integrated with filtering
- `/frontend/react/src/features/TeacherDashboard.jsx` - Already uses filtered timetable

**Backend:**
- `/backend/api/models.py` - TeacherAssignment model (already exists)
- `/backend/routes.py` - All endpoints (already configured)

**Database:**
- `teacher_assignment` table (already created)

## Next Steps After Testing

If everything works:
1. ✅ Teachers can be assigned to specific classes/subjects
2. ✅ Proprietor can manage assignments in Staff Management
3. ✅ Teachers see only their assigned slots in timetable
4. ✅ Timetable can be filtered and printed by class

Optional improvements:
- Add multi-select pickers (visual checkboxes) instead of text input
- Add validation (ensure class/subject names exist)
- Add bulk assignment templates
- Add assignment history/audit log

---

**Status: Ready for testing**
**Implementation Date: [Current Session]**
**Backend Status: ✅ Complete**
**Frontend Status: ✅ Complete**
**Database Status: ✅ Complete**
