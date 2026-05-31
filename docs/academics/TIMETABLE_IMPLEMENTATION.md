# Timetable & Grade Exchange Implementation

## Overview
This implementation adds a comprehensive timetable management system and enhances the grade exchange workflow across the entire EduPulse platform. Teachers, homeroom staff, and administrators can now view schedules, manage time slots, and seamlessly exchange grades that auto-fill into report cards.

## Features Implemented

### 1. Timetable Management System
- **Database Model**: New `Timetable` table with the following fields:
  - `id`, `school_id`, `class_name`, `subject_name`, `teacher_id`
  - `day_of_week`, `start_time`, `end_time`, `location`
  - `created_at`, `updated_at`
  - Foreign keys to `schools` and `users` tables

- **Backend Endpoints** (in `backend/routes.py`):
  - `GET /api/timetable` - Retrieve all timetable entries for the school (Proprietor, Headmaster, Teachers)
  - `GET /api/timetable/my` - Retrieve logged-in teacher's assigned schedule (Teacher, Homeroom)
  - `POST /api/timetable` - Create new timetable entry (Proprietor, Headmaster)
  - `DELETE /api/timetable/<entry_id>` - Remove timetable entry (Proprietor, Headmaster)
  - `GET /api/timetable/export` - Export timetable as CSV (All roles)

- **UI Components**:
  - **TimetableManager.jsx**: Reusable component for viewing/managing timetable
    - Supports two modes:
      - `scope="school"` with `canManage=true` - Full management UI (Proprietor, Headmaster)
      - `scope="mine"` with `canManage=false` - Read-only teacher schedule view
    - Form to add new slots (class, subject, teacher, day, time, location)
    - Sorted display by day and time
    - Delete functionality for authorized roles
    - **Export to CSV** button - Downloads timetable as CSV file
    - **Print** button - Opens print-friendly view in new window

### 2. Integration Across Dashboards

#### Proprietor Settings Panel (`SettingsPanel.jsx`)
- Added timetable management section at the bottom of system settings
- Full CRUD operations for timetable entries
- Staff list dropdown for teacher assignment

#### Headmaster Dashboard (`HeadmasterDashboard.jsx`)
- Timetable management section (can add/remove entries)
- **Grade Inbox** section:
  - Class selector dropdown
  - Displays all submitted grades per student
  - Shows class work, exam score, and total per subject
  - Uses existing `/api/homeroom/get-subject-grades/<class>` endpoint

#### Teacher Dashboard (`TeacherDashboard.jsx`)
- "My Teaching Schedule" section at the top
- Read-only timetable view showing teacher's assigned classes, subjects, and times
- Helps teachers see which classes they teach before submitting grades

#### Homeroom Dashboard (`HomeroomDashboard.jsx`)
- "My Teaching Schedule" section visible for homeroom teachers
- Shows all classes/subjects the homeroom teacher teaches
- Integrated with existing grade submission and report generation workflow

### 3. Grade Exchange Workflow
The grade exchange system leverages the existing endpoints and enhances visibility:

#### Existing Backend Endpoints (Already Implemented)
- `POST /api/teacher/submit-grades-to-homeroom` - Subject teachers submit grades (finalized StudentGrade records)
- `GET /api/homeroom/get-subject-grades/<class>` - Homeroom retrieves all finalized grades for their class
- `POST /api/homeroom/generate-terminal-report` - Homeroom aggregates grades into terminal reports
- The reports **auto-fill** student grades from `StudentGrade` table

#### Enhanced UI Flow
1. **Subject Teacher** (TeacherDashboard.jsx):
   - Sees their timetable
   - Selects class and subject from the timetable
   - Enters class work (0-30) and exam (0-70) scores
   - Submits via "Submit Grades to Homeroom" button
   - Backend marks `is_finalized=True` in `StudentGrade` table

2. **Homeroom Teacher** (HomeroomDashboard.jsx):
   - Sees their teaching schedule
   - Can view submitted grades via existing grading tab
   - Generates terminal reports (aggregates all finalized grades)
   - Reports auto-fill from StudentGrade records

3. **Headmaster** (HeadmasterDashboard.jsx):
   - Grade Inbox shows all submitted grades by class
   - Can review grades before report approval
   - Approves/rejects terminal reports

### 4. Role-Based Visibility
- **Proprietor**: Full timetable management in system settings
- **Headmaster**: Full timetable management + grade inbox view
- **Homeroom**: Read-only timetable + grade submission/aggregation
- **Teacher**: Read-only timetable + grade submission

## Database Migration

The timetable table was created using a migration script:
```sql
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id VARCHAR(20) NOT NULL,
    class_name VARCHAR(20) NOT NULL,
    subject_name VARCHAR(50) NOT NULL,
    teacher_id INTEGER,
    day_of_week VARCHAR(10) NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    location VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY(school_id) REFERENCES schools(id),
    FOREIGN KEY(teacher_id) REFERENCES users(id)
)
```

## Files Modified

### Frontend
1. **New File**: `frontend/react/src/components/TimetableManager.jsx`
   - Reusable timetable component with create/view/delete functionality

2. **Modified**: `frontend/react/src/components/SettingsPanel.jsx`
   - Added timetable management section
   - Imported TimetableManager component

3. **Modified**: `frontend/react/src/features/TeacherDashboard.jsx`
   - Added "My Teaching Schedule" section
   - Imported TimetableManager with `scope="mine"` and `canManage={false}`

4. **Modified**: `frontend/react/src/features/HomeroomDashboard.jsx`
   - Added "My Teaching Schedule" section
   - Imported TimetableManager component

5. **Modified**: `frontend/react/src/features/HeadmasterDashboard.jsx`
   - Added timetable management section
   - Added grade inbox section with class selector
   - Integrated with existing `get-subject-grades` endpoint

### Backend
1. **Modified**: `backend/api/models.py`
   - Added `Timetable` model with all required fields and relationships

2. **Modified**: `backend/routes.py`
   - Added `Timetable` import
   - Added 4 new timetable endpoints (GET all, GET my, POST, DELETE)
   - Updated `/staff/list` to accept headmaster role
   - Updated `/staff/list` to return roles array

## Testing Recommendations

### Manual Testing Steps
1. **Timetable Creation**:
   - Log in as Proprietor
   - Go to Settings Panel
   - Scroll to "Timetable Management"
   - Add multiple timetable entries for different classes/teachers
   - Verify entries appear in sorted order

2. **Teacher View**:
   - Log in as Teacher
   - Verify "My Teaching Schedule" shows only assigned classes
   - Submit grades for a class
   - Verify grades persist

3. **Homeroom Grade Aggregation**:
   - Log in as Homeroom
   - Verify teaching schedule appears
   - Submit grades for multiple subjects
   - Generate terminal report
   - Verify report auto-fills all grades

4. **Headmaster Review**:
   - Log in as Headmaster
   - Check timetable management
   - View grade inbox by class
   - Verify all submitted grades appear
   - Approve a report

### API Testing
Use Postman or curl to test:
```bash
# Get all timetable entries
GET /api/timetable
Headers: Authorization: Bearer <token>, X-School-ID: <school_id>

# Get my timetable
GET /api/timetable/my
Headers: Authorization: Bearer <token>, X-School-ID: <school_id>

# Create timetable entry
POST /api/timetable
Headers: Authorization: Bearer <token>, X-School-ID: <school_id>
Body: {
  "class_name": "JHS 1",
  "subject_name": "Mathematics",
  "teacher_id": 3,
  "day_of_week": "Monday",
  "start_time": "08:00",
  "end_time": "09:00",
  "location": "Room A1"
}

# Delete timetable entry
DELETE /api/timetable/1
Headers: Authorization: Bearer <token>, X-School-ID: <school_id>

# Export timetable as CSV
GET /api/timetable/export
Headers: Authorization: Bearer <token>, X-School-ID: <school_id>
```

## Key Benefits

1. **Transparency**: Teachers see their schedule before submitting grades
2. **Accountability**: Clear assignment of teachers to classes/subjects/times
3. **Efficiency**: Auto-fill report cards from submitted grades
4. **Oversight**: Headmaster can review all grades via grade inbox
5. **Flexibility**: Timetable managed by Proprietor/Headmaster, visible to all
6. **Export & Print**: Download timetable as CSV or print for distribution

## Future Enhancements

1. **Timetable Conflict Detection**: Prevent scheduling two classes for the same teacher at the same time
2. **Bulk Import**: CSV upload for timetable entries
3. **Student Timetable View**: Show students their weekly schedule
4. **Attendance Integration**: Mark attendance directly from timetable view
5. **Notifications**: Alert teachers before their class time (push/email)
6. **Analytics**: Track grade submission rates per teacher/subject
7. **Grade History**: View grade changes over time
8. **Mobile Responsive**: Optimize timetable display for mobile devices

## Deployment Notes

1. Ensure database migration runs successfully (timetable table creation)
2. Verify all staff have `roles` array populated (backward compatibility)
3. Test with existing grade data to ensure report cards still auto-fill
4. Clear browser cache if timetable components don't appear
5. Check CORS settings if timetable endpoints return 403

## Conclusion

This implementation provides a complete timetable management system integrated with the existing grade submission workflow. Teachers now see their schedules, submit grades for their assigned classes, and homeroom teachers aggregate these into terminal reports that auto-fill with all subject grades. The headmaster can review all submissions via the grade inbox before final approval.

The system respects role-based access control, maintains multi-tenant isolation, and leverages existing backend endpoints for grade exchange. All new UI components are reusable and follow the existing design patterns in EduPulse.
