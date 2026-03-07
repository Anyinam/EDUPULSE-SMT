# Staff Assignment Implementation - Complete

## Overview
The Staff Management interface has been fully updated to support teacher subject/class assignments required for the timetable filtering feature.

## UI Updates - StaffManagement.jsx

### Add New Staff Form
Teachers and Homeroom teachers can now specify:
1. **Homeroom Class** (optional): Single class they manage (existing field, repurposed)
2. **Classes to Teach** (new): Comma-separated list of classes they teach
   - Example: "JHS 1, JHS 2, SHS 1"
3. **Subjects to Teach** (new): Comma-separated list of subjects they teach
   - Example: "Mathematics, English, Science"

### Staff List Table
The table now displays 7 columns:
1. **Staff ID**: Username
2. **Email**: Contact email
3. **Role**: Job roles (Teacher, Homeroom, etc.)
4. **Homeroom**: Homeroom class assignment (if applicable)
5. **Teaching Classes**: Classes the teacher instructs (NEW)
6. **Teaching Subjects**: Subjects the teacher instructs (NEW)
7. **Actions**: Edit/Remove buttons

### Edit Mode
When editing a staff member:
- All assignment fields become editable inline
- Classes and Subjects fields show as comma-separated inputs
- Fields only display for teachers/homeroom staff (hidden for other roles)
- Save/Cancel buttons allow confirm or discard changes

## Data Flow

### Adding a Staff Member
```
User fills form:
├─ Username, Email, Password
├─ Roles (checkboxes)
├─ Assigned Class (homeroom)
├─ Classes to Teach (comma-separated)
└─ Subjects to Teach (comma-separated)

↓ POST /api/staff/add

Backend:
├─ Creates User record
├─ Calls replace_teacher_assignments()
├─ Which creates TeacherAssignment records:
│  ├─ For each (class, subject) pair
│  └─ Stores: school_id, teacher_id, class_name, subject_name
└─ Returns success

Frontend:
└─ Refreshes staff list → Fetches updated records
```

### Updating a Staff Member
```
User edits and saves:
├─ Changes roles
├─ Updates Classes to Teach
└─ Updates Subjects to Teach

↓ PUT /api/staff/<user_id>

Backend:
├─ Updates User roles
├─ Calls replace_teacher_assignments()
├─ Which:
│  ├─ Deletes all old TeacherAssignment records for teacher
│  ├─ Creates new ones from updated arrays
│  └─ Maintains unique constraint: (school_id, teacher_id, class_name, subject_name)
└─ Returns updated user

Frontend:
└─ Refreshes staff list
```

## Integration with Timetable System

### TeacherAssignment Records
When a teacher has assignments configured:
```sql
-- Example: Math teacher at JHS 1 and JHS 2, English teacher at SHS 1
INSERT INTO teacher_assignment (school_id, teacher_id, class_name, subject_name, created_at)
VALUES 
  (1, 42, 'JHS 1', 'Mathematics', '2024-01-15'),
  (1, 42, 'JHS 2', 'Mathematics', '2024-01-15'),
  (1, 43, 'SHS 1', 'English', '2024-01-15');
```

### Timetable Filtering
When teacher views their timetable (`GET /api/timetable/my`):
1. System fetches all TeacherAssignment records for that teacher
2. Filters timetable entries to only include matching (class_name, subject_name) pairs
3. Teacher sees only slots they actually teach

## API Endpoints Updated

### POST /api/staff/add
**Request Body:**
```json
{
  "username": "john_doe",
  "email": "john@school.com",
  "password": "secure_pass",
  "roles": ["teacher"],
  "assigned_class": "JHS 1",
  "assigned_classes": ["JHS 1", "JHS 2"],
  "assigned_subjects": ["Mathematics", "Science"]
}
```

### GET /api/staff/list
**Response includes:**
```json
{
  "id": 42,
  "username": "john_doe",
  "email": "john@school.com",
  "roles": ["teacher"],
  "assigned_class": "JHS 1",
  "assigned_classes": ["JHS 1", "JHS 2"],
  "assigned_subjects": ["Mathematics", "Science"]
}
```

### PUT /api/staff/<user_id>
**Request Body:**
```json
{
  "roles": ["teacher", "homeroom"],
  "assigned_class": "JHS 2",
  "assigned_classes": ["JHS 2", "SHS 1"],
  "assigned_subjects": ["Mathematics"]
}
```

### GET /api/teacher/assignments
**Response (current teacher's assignments):**
```json
[
  { "class_name": "JHS 1", "subject_name": "Mathematics" },
  { "class_name": "JHS 2", "subject_name": "Mathematics" }
]
```

## Testing Workflow

### 1. Add a Teacher with Assignments
- Navigate to Staff Management (Proprietor with role: 'proprietor')
- Fill form:
  - Username: `math_teacher`
  - Email: `math@school.com`
  - Password: `test123`
  - Role: Check "Teacher"
  - Homeroom Class: (leave empty)
  - Classes to Teach: `JHS 1, JHS 2`
  - Subjects to Teach: `Mathematics, Science`
- Click "Add Staff"
- Expected: Staff member appears in list with classes/subjects displayed

### 2. Verify Backend Storage
- Check database:
  ```sql
  SELECT * FROM teacher_assignment WHERE teacher_id = <math_teacher_id>;
  ```
- Expected: 4 rows (2 classes × 2 subjects = 4 combinations)

### 3. Login as Teacher
- Login with `math_teacher` credentials
- Navigate to Timetable
- Expected: Only see slots for (JHS 1, Mathematics), (JHS 1, Science), (JHS 2, Mathematics), (JHS 2, Science)

### 4. Edit Teacher Assignments
- Return to Staff Management
- Click "Edit" on math_teacher row
- Change:
  - Classes to Teach: `JHS 2, JHS 3`
  - Subjects to Teach: `Mathematics`
- Click "Save"
- Expected: Table updates; backend deletes old 4 records, creates 2 new ones (JHS 2 + JHS 3 × Math)

### 5. Verify Timetable Update
- Login again as math_teacher
- Check timetable
- Expected: Only (JHS 2, Mathematics) and (JHS 3, Mathematics) entries visible

## Implementation Notes

### Data Model
- **TeacherAssignment**: Many-to-many relationship between User and (class_name, subject_name) pairs
- **Unique Constraint**: `(school_id, teacher_id, class_name, subject_name)` - prevents duplicate assignments
- **Foreign Keys**: teacher_id references User.id

### UI State Management
- Form data split into two parts:
  - `formData` for new staff entries
  - `editForm` for editing existing staff
- Both include:
  - `assigned_classes: []` - array of class names
  - `assigned_subjects: []` - array of subject names
- Arrays converted to/from comma-separated display strings using `.join(', ')` and `.split(',').map(s => s.trim())`

### Conditional Display
- Assignment fields only show when role includes "teacher" or "homeroom"
- Display "-" for non-teacher staff
- Empty values handled gracefully (default to empty array in display)

### Multi-Tenant Safety
- All backend operations filtered by `g.school_id`
- Staff can only manage teachers within their own school
- TeacherAssignment records scoped by school_id

## Future Enhancements
1. **Visual Class/Subject Pickers**: Replace comma-separated text with multi-select dropdowns (requires fetching available classes/subjects)
2. **Bulk Assignment**: Assign same subjects to multiple classes at once
3. **Assignment History**:T rack when assignments were changed
4. **Conflict Detection**: Warn if teacher has overlapping class/subject assignments

---

**Status**: ✅ Complete - StaffManagement UI fully integrated with backend assignment endpoints
**Last Updated**: Current session
**Related Files**:
- `/frontend/react/src/features/StaffManagement.jsx` - UI component
- `/backend/api/models.py` - TeacherAssignment model
- `/backend/routes.py` - Assignment endpoints and timetable filtering logic
