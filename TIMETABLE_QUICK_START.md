# Quick Start Guide: Timetable & Grade Exchange

## What Was Implemented

### 1. Timetable Management
Teachers can now see their teaching schedule, and proprietors/headmasters can manage the school timetable.

### 2. Grade Exchange with Auto-Fill
The existing grade submission workflow now integrates with timetables, making it clear which classes/subjects each teacher handles. Report cards auto-fill from submitted grades.

## How to Test

### Step 1: Database Setup (Already Done ✅)
The timetable table has been created in the database.

### Step 2: Start the Application
```bash
# Terminal 1: Start Backend
cd /home/anyinam/Documents/EduPulse
source Eduenv/bin/activate
python -m flask --app backend.routes run --port 5000

# Terminal 2: Start Frontend
cd /home/anyinam/Documents/EduPulse/frontend/react
npm run dev
```

### Step 3: Test as Proprietor
1. Login as proprietor
2. Go to **System Settings** (Settings Panel)
3. Scroll down to **"🗓️ School Timetable"** section
4. Add a timetable entry:
   - Class: JHS 1
   - Subject: Mathematics
   - Teacher: Select a teacher from dropdown
   - Day: Monday
   - Start Time: 08:00
   - End Time: 09:00
   - Location: Room A1
5. Click **"Add Timetable Slot"**
6. Verify the entry appears in the list below

### Step 4: Test as Teacher
1. Login as a teacher (must be assigned in the timetable)
2. View **"My Teaching Schedule"** section at the top
3. Verify you see only your assigned classes/subjects/times
4. Select a class and subject from your schedule
5. Enter grades (Class Work 0-30, Exam 0-70)
6. Click **"Submit Grades to Homeroom"**

### Step 5: Test as Homeroom
1. Login as homeroom teacher
2. View **"My Teaching Schedule"** section
3. Go to **"Subject Teaching (All Classes)"** tab
4. Enter grades for your subjects
5. Switch to **"My Homeroom"** tab
6. Click **"Generate Terminal Reports"**
7. Verify all grades from subject teachers appear in the report (auto-filled)

### Step 6: Test as Headmaster
1. Login as headmaster
2. View **"🗓️ Timetable Management"** section (can add/remove entries)
3. View **"📘 Grade Inbox"** section
4. Select a class from the dropdown
5. Verify all submitted grades appear per student
6. Scroll down to **"Terminal Report Approvals"**
7. Approve or reject pending reports

### Step 7: Test Export & Print
1. Login as any role (Proprietor, Headmaster, Teacher, or Homeroom)
2. Navigate to the timetable view
3. Click **"📥 Export CSV"** button
4. Verify CSV file downloads with format: `timetable_SchoolName_YYYYMMDD.csv`
5. Open the CSV in Excel/Google Sheets to verify data
6. Click **"🖨️ Print"** button
7. Verify print preview opens in new window with formatted table
8. Print or save as PDF

## Key Features to Verify

### Timetable Display
- ✅ Proprietor sees full timetable in system settings
- ✅ Headmaster sees full timetable and can manage it
- ✅ Teacher sees only their assigned schedule (read-only)
- ✅ Homeroom sees their teaching schedule (read-only)

### Grade Exchange Flow
- ✅ Teacher submits grades via `/api/teacher/submit-grades-to-homeroom`
- ✅ Homeroom retrieves grades via `/api/homeroom/get-subject-grades/<class>`
- ✅ Headmaster views grade inbox for any class
- ✅ Report cards auto-fill from StudentGrade table

### Role-Based Access
- ✅ Proprietor: Full timetable management
- ✅ Headmaster: Full timetable management + grade inbox
- ✅ Homeroom: Read-only timetable + grade submission/aggregation
- ✅ Teacher: Read-only timetable + grade submission

## API Endpoints Added

### Timetable Endpoints (in backend/routes.py)
- `GET /api/timetable` - Get all timetable entries (Proprietor, Headmaster, Teachers)
- `GET /api/timetable/my` - Get my schedule (Teacher, Homeroom)
- `POST /api/timetable` - Create entry (Proprietor, Headmaster)
- `DELETE /api/timetable/<id>` - Remove entry (Proprietor, Headmaster)
- `GET /api/timetable/export` - Export as CSV (All roles)

### Existing Grade Endpoints (Enhanced with Timetable Context)
- `POST /api/teacher/submit-grades-to-homeroom` - Submit grades
- `GET /api/homeroom/get-subject-grades/<class>` - Get submitted grades
- `POST /api/homeroom/generate-terminal-report` - Aggregate into reports

## Files Created/Modified

### New Files
- `frontend/react/src/components/TimetableManager.jsx` - Reusable timetable component
- `TIMETABLE_IMPLEMENTATION.md` - Detailed implementation guide

### Modified Frontend Files
- `frontend/react/src/components/SettingsPanel.jsx` - Added timetable section
- `frontend/react/src/features/TeacherDashboard.jsx` - Added schedule display
- `frontend/react/src/features/HomeroomDashboard.jsx` - Added schedule display
- `frontend/react/src/features/HeadmasterDashboard.jsx` - Added timetable management + grade inbox

### Modified Backend Files
- `backend/api/models.py` - Added Timetable model
- `backend/routes.py` - Added timetable endpoints

## Common Issues & Solutions

### Issue: Timetable doesn't appear
**Solution**: Clear browser cache and refresh. Ensure you're logged in with the correct role.

### Issue: "Select teacher" dropdown is empty
**Solution**: Ensure staff members exist in the system. Go to Staff Management and add teachers first.

### Issue: Teacher doesn't see their schedule
**Solution**: Ensure the teacher is assigned to classes in the timetable. Proprietor/Headmaster must add entries with that teacher selected.

### Issue: Grades not auto-filling in reports
**Solution**: Ensure grades have `is_finalized=True` in the database. Subject teachers must use "Submit Grades to Homeroom" button (not save locally).

### Issue: 403 Forbidden on timetable endpoints
**Solution**: Check role permissions. Ensure JWT token is valid and user has the required role.

## Next Steps

1. **Test each role**: Login as Proprietor, Headmaster, Homeroom, and Teacher
2. **Create sample timetable**: Add 5-10 entries covering different classes/subjects
3. **Submit sample grades**: Have teachers submit grades for their classes
4. **Generate reports**: Homeroom aggregates grades into terminal reports
5. **Review in grade inbox**: Headmaster views all submitted grades
6. **Approve reports**: Headmaster approves terminal reports

## Success Criteria

- ✅ Proprietor can add/remove timetable entries
- ✅ Headmaster can manage timetable and view grade inbox
- ✅ Teachers see their schedule and submit grades
- ✅ Homeroom aggregates grades into reports
- ✅ Report cards auto-fill with all subject grades
- ✅ No role can see unauthorized data (multi-tenant isolation)
- ✅ Timetable can be exported as CSV
- ✅ Timetable can be printed with formatted layout

## Documentation

For detailed technical documentation, see:
- `TIMETABLE_IMPLEMENTATION.md` - Full implementation details
- `backend/routes.py` - Timetable endpoint code (lines 3261-3373)
- `backend/api/models.py` - Timetable model definition (lines 398-410)
