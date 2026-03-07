# Report Builder - Quick Start Guide

## For Homeroom Teachers

### Creating a Report Card

1. **Login** as a homeroom teacher (must have `assigned_class` set)

2. **Navigate** to Report Builder
   - Click "📝 Report Builder" in the left sidebar
   - Or go to: `http://localhost:5173/report-builder`

3. **Select Term & Year**
   - Choose Academic Term (Term 1, 2, or 3)
   - Enter Academic Year (e.g., "2024/2025")
   - Your assigned class is shown (read-only)

4. **Select Student**
   - Click on a student name in the left sidebar
   - If a report already exists for this term/year, it will load
   - If no report exists, a blank form appears with default subjects

5. **Enter Subject Grades**
   - For each subject:
     - Subject name (editable)
     - Class Score (0-30)
     - Exam Score (0-70)
     - Total (auto-calculated)
     - Position (e.g., "1st", "2nd", "3rd")
     - Grade (auto-assigned: A-F)
     - Remarks (optional)
   - Click "+ Add Subject" to add more subjects
   - Click "Remove" to delete a subject row

6. **Enter Performance Summary**
   - Overall Position (e.g., "3rd")
   - Out of Students (e.g., 40)
   - Attendance % (e.g., 95.5)
   - Total Attendance (e.g., 160 days)

7. **Add Teacher Remarks**
   - Enter your comments about the student's overall performance
   - This will appear on the printed report card

8. **Save or Submit**
   - **Save Draft**: Saves without submitting (you can edit later)
   - **Submit for Approval**: Locks the report and sends to headmaster

### Importing Grades from Subject Teachers

If subject teachers have submitted finalized grades:

```javascript
// Fetch via API endpoint
GET /api/homeroom/get-subject-grades/JHS%201
```

Returns:
```json
[
  {
    "student_id": 1,
    "student_name": "John Doe",
    "student_code": "STU-001",
    "subject_grades": [
      {"subject": "Mathematics", "class_score": 25, "exam_score": 65, "total": 90, "remarks": ""}
    ]
  }
]
```

You can then manually copy these grades into the report builder form.

### Viewing Status

After submitting, the status badge shows:
- 🟡 **Submitted**: Waiting for headmaster approval
- 🟢 **Approved**: Report is finalized
- 🔴 **Rejected**: Headmaster requests changes (check remarks)

---

## For Headmasters

### Reviewing Pending Reports

1. **Login** as headmaster

2. **Navigate** to Report Builder
   - Click "📝 Report Builder" in sidebar
   - Or use API: `GET /api/headmaster/report-builder/pending`

3. **Review Reports**
   - View all submitted report cards
   - Check for errors or inconsistencies

4. **Approve or Reject**
   - **Approve**: Click approve button
   - **Reject**: Add remarks explaining what needs correction

### API Endpoints

```bash
# Get pending reports
curl -X GET http://localhost:5000/api/headmaster/report-builder/pending \
  -H "Authorization: Bearer <token>" \
  -H "X-School-ID: <school_id>"

# Approve a report
curl -X POST http://localhost:5000/api/headmaster/report-builder/approve \
  -H "Authorization: Bearer <token>" \
  -H "X-School-ID: <school_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "report_id": 1,
    "status": "Approved",
    "headmaster_remarks": "Well done!"
  }'
```

---

## For Subject Teachers

### Submitting Grades to Homeroom

Subject teachers can submit finalized grades that homeroom teachers can pull into reports:

```bash
curl -X POST http://localhost:5000/api/teacher/submit-grades-to-homeroom \
  -H "Authorization: Bearer <token>" \
  -H "X-School-ID: <school_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "class_name": "JHS 1",
    "subject": "Mathematics",
    "grade_data": {
      "1": {"class_score": 25, "exam_score": 65},
      "2": {"class_score": 20, "exam_score": 55}
    }
  }'
```

This creates `StudentGrade` records with `is_finalized=True` that homeroom teachers can query.

---

## Tips & Best Practices

### Data Entry
- ✅ **Do**: Enter scores immediately after marking exams
- ✅ **Do**: Save drafts frequently (auto-save not implemented yet)
- ✅ **Do**: Double-check calculations even though totals are auto-calculated
- ❌ **Don't**: Submit incomplete reports (fill all subjects first)

### Remarks
- Be specific: "Excellent performance in problem-solving" > "Good"
- Mention both strengths and areas for improvement
- Keep it professional and constructive

### Workflow
1. Subject teachers finalize grades throughout the term
2. Homeroom pulls grades when ready to compile terminal report
3. Homeroom adds attendance, position, and remarks
4. Homeroom submits for headmaster approval
5. Headmaster reviews and approves
6. (Future) Report is printed/exported for parents

---

## Troubleshooting

### "No students found"
- **Cause**: Your user account has no `assigned_class` set
- **Fix**: Ask headmaster/proprietor to assign you to a class

### "Report card not found"
- **Cause**: No report exists for this student + term + year combination
- **Fix**: The system will create a blank report automatically when you select the student

### "Access denied"
- **Cause**: You're trying to access a class that's not your assigned_class
- **Fix**: Only access your own homeroom class (headmaster can access any class)

### Grades not saving
- **Cause**: JWT token expired or missing
- **Fix**: Logout and login again

### Subject teacher grades not showing
- **Cause**: Subject teacher hasn't finalized grades yet
- **Fix**: Ask subject teacher to submit grades via `/api/teacher/submit-grades-to-homeroom`

---

## Database Schema Reference

### `report_cards` Table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| school_id | String(20) | Multi-tenant isolation |
| student_id | Integer | FK to students table |
| academic_term | String(20) | "Term 1", "Term 2", "Term 3" |
| academic_year | String(20) | "2024/2025" |
| class_name | String(20) | "JHS 1", "Class 4", etc. |
| subject_grades | JSON | Array of subject entries |
| term_average | Float | Calculated percentage |
| overall_position | String(10) | "1st", "2nd", etc. |
| attendance_percentage | Float | % present |
| homeroom_teacher_remarks | Text | Teacher comments |
| headmaster_remarks | Text | Headmaster feedback |
| status | String(20) | Draft/Submitted/Approved/Rejected |
| created_at | DateTime | When created |
| submitted_at | DateTime | When submitted for approval |
| approved_at | DateTime | When approved/rejected |

### `subject_grades` JSON Structure
```json
[
  {
    "subject": "Mathematics",
    "class_score": 25,
    "exam_score": 65,
    "total": 90,
    "position": "1st",
    "grade": "A",
    "remarks": "Excellent work"
  }
]
```

---

## Support

For technical issues or feature requests:
- Create a support ticket via the Support panel
- Email: support@edupulse.com (if configured)
- Check audit logs: `AuditLog` table for `REPORT_CARD_*` actions
