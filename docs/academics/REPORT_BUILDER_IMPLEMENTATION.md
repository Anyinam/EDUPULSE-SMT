# Report Builder Feature Implementation

## Overview
Implemented a complete **Manual Report Card Entry System** that allows homeroom teachers to create, edit, and submit terminal report cards with full academic performance data. This addresses the limitation of unreliable OCR by providing a robust manual data entry interface.

## Architecture

### Database Layer
**New Model: `ReportCard`** ([backend/api/models.py](backend/api/models.py))
- Stores complete terminal report card data per student per term
- Fields:
  - Academic context: `academic_term`, `academic_year`, `class_name`
  - Subject grades: `subject_grades` (JSON array with class_score, exam_score, total, position, grade, remarks)
  - Performance summary: `total_marks_obtained`, `term_average`, `overall_position`, `out_of_students`
  - Attendance: `attendance_percentage`, `total_attendance`
  - Comments: `homeroom_teacher_remarks`, `headmaster_remarks`
  - Workflow: `status` (Draft → Submitted → Approved/Rejected)
  - Audit: `created_by`, `submitted_at`, `approved_at`, `approved_by`

**Database Migration**: [alembic/versions/004_add_report_cards.py](alembic/versions/004_add_report_cards.py)
- Creates `report_cards` table
- Adds indexes on `(student_id, academic_term, academic_year)` for fast lookups
- Run with: `PYTHONPATH=. python scripts/maintenance/init_report_cards.py`

### API Layer
**Report Builder Endpoints** ([backend/routes.py](backend/routes.py))

#### Homeroom Teacher Operations
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/homeroom/report-builder/students` | GET | Get list of students in homeroom class |
| `/api/homeroom/report-builder/report` | POST | Create or update a report card |
| `/api/homeroom/report-builder/report/<student_id>` | GET | Fetch existing report card |
| `/api/homeroom/report-builder/submit` | POST | Submit report card for headmaster approval |
| `/api/homeroom/get-subject-grades/<class_name>` | GET | Fetch finalized grades from subject teachers |

#### Headmaster Operations
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/headmaster/report-builder/pending` | GET | Get all pending report cards |
| `/api/headmaster/report-builder/approve` | POST | Approve or reject report cards |

#### Subject Teacher Operations
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/teacher/submit-grades-to-homeroom` | POST | Submit finalized subject grades to homeroom |

### Frontend Layer
**Report Builder UI** ([frontend/react/src/features/ReportBuilder.jsx](frontend/react/src/features/ReportBuilder.jsx))

#### Features
1. **Student Selection**
   - Left sidebar with list of students in homeroom class
   - Click to select student and load/create report

2. **Report Form**
   - Academic context selector (Term 1/2/3, Academic Year)
   - Subject grades table:
     - Subject name (editable)
     - Class score (0-30)
     - Exam score (0-70)
     - Total (auto-calculated)
     - Position (1st, 2nd, etc.)
     - Grade (auto-assigned A-F)
     - Remarks
   - Add/Remove subject rows dynamically
  - Optional diagnostic strands per subject for topic-level mock sub-scores
   - Performance summary fields:
     - Overall position
     - Out of X students
     - Attendance percentage
     - Total attendance days
   - Homeroom teacher remarks (textarea)

3. **Actions**
   - **Save Draft**: Save without submitting
   - **Submit for Approval**: Lock and send to headmaster
   - Status indicator (Draft/Submitted/Approved/Rejected)
   - Headmaster remarks display (if any)

4. **Routing**
   - Route: `/report-builder`
   - Accessible to: Homeroom teachers, Headmaster
   - Navigation link added to [Layout.jsx](frontend/react/src/components/Layout.jsx)

## User Workflows

### Workflow 1: Manual Report Card Entry
```
1. Homeroom teacher navigates to Report Builder
2. Selects academic term and year
3. Clicks student name in sidebar
4. Enters subject grades (class scores, exam scores)
5. Fills in overall position, attendance, remarks
6. Optionally adds diagnostic strands for weak-topic tracking and pathway guidance
7. Saves draft (can return later to edit)
8. When complete, submits for approval
9. Headmaster reviews and approves/rejects
```

### Workflow 2: Subject Teacher Grade Submission
```
1. Subject teacher finalizes grades via existing grade entry UI
2. Calls POST /api/teacher/submit-grades-to-homeroom with:
   - class_name: "JHS 1"
   - subject: "Mathematics"
   - grade_data: {student_id: {class_score: 25, exam_score: 65}}
3. Grades saved to StudentGrade table with is_finalized=True
4. Homeroom teacher fetches grades via GET /api/homeroom/get-subject-grades/JHS%201
5. Homeroom teacher copies grades into report card form
```

## Role-Based Access Control

| Role | Permissions |
|------|-------------|
| **Homeroom Teacher** | - Create/edit report cards for assigned class<br>- Submit for approval<br>- View own submitted reports |
| **Subject Teacher** | - Submit finalized subject grades to homeroom<br>- Cannot create terminal reports |
| **Headmaster** | - All homeroom permissions for any class<br>- Approve/reject submitted reports<br>- Add headmaster remarks |
| **Proprietor** | - Read-only access to all reports (via existing financial dashboard) |

## Data Flow

```
┌─────────────────┐
│ Subject Teacher │
│   Grade Entry   │
└────────┬────────┘
         │
         ├─ POST /api/teacher/submit-grades-to-homeroom
         │
         ▼
┌─────────────────┐
│  StudentGrade   │  (is_finalized = True)
│   Database      │
└────────┬────────┘
         │
         ├─ GET /api/homeroom/get-subject-grades/<class>
         │
         ▼
┌─────────────────┐
│  Homeroom       │
│  Report Builder │
└────────┬────────┘
         │
         ├─ POST /api/homeroom/report-builder/report
         │
         ▼
┌─────────────────┐
│   ReportCard    │  (status: Draft)
│   Database      │
└────────┬────────┘
         │
         ├─ POST /api/homeroom/report-builder/submit
         │
         ▼
┌─────────────────┐
│   ReportCard    │  (status: Submitted)
└────────┬────────┘
         │
         ├─ POST /api/headmaster/report-builder/approve
         │
         ▼
┌─────────────────┐
│   ReportCard    │  (status: Approved)
└─────────────────┘
```

## Key Implementation Details

### Auto-Calculations
- **Total Score**: `class_score + exam_score` (updated on input change)
- **Grade Assignment**:
  - 80-100: A
  - 70-79: B
  - 60-69: C
  - 50-59: D
  - 40-49: E
  - 0-39: F
- **Term Average**: `(sum of all subject totals) / (number of subjects × 100) × 100`

### Diagnostic Strands
- Each subject row can include optional `diagnostic_topics`
- Each topic stores `topic`, `score`, and `max_score`
- These topic-level scores are persisted with `subject_grades`
- Terminal report print/review surfaces render them in a separate `Diagnostic Strand Insights` section
- Weak strands are shown by default when the topic score is $\le 55\%$ of the topic maximum, while stronger strands remain expandable in on-screen review views

### Validation
- Class score: 0-30 range enforced
- Exam score: 0-70 range enforced
- Total score: 0-100 (auto-calculated, read-only)
- Required fields: student_id, academic_term, academic_year, subject_grades

### Security
- Multi-tenant isolation via `school_id` filter
- JWT authentication required for all endpoints
- Role-based middleware: `@role_required('teacher', 'headmaster', 'proprietor')`
- Homeroom teachers can only access their assigned class
- Headmaster can access any class

### Performance
- Indexed lookups on `(student_id, academic_term, academic_year)`
- Lazy loading of report data (only fetches when student selected)
- Optimistic UI updates (saves immediately on button click)

## Integration with Existing Features

### OCR Pipeline (Optional Assist)
- OCR endpoints remain functional: `POST /api/reports/parse`
- If OCR quality improves, can populate report builder form automatically
- Current recommendation: Use OCR as reference, manual entry as primary

### Grade Submission Workflow
- Subject teachers continue using existing grade entry UI
- New endpoint bridges subject grades → terminal reports
- Homeroom can pull grades via API and populate report builder

### Headmaster Approval
- Reuses existing `ReportCardStatus` workflow pattern
- New dedicated endpoints for report card approval
- Status tracking: Draft → Submitted → Approved/Rejected

## Testing

### Manual Testing Checklist
1. ✅ Database table creation (`scripts/maintenance/init_report_cards.py`)
2. ⏳ Login as homeroom teacher
3. ⏳ Navigate to `/report-builder`
4. ⏳ Select student and term
5. ⏳ Enter subject grades
6. ⏳ Save draft
7. ⏳ Submit for approval
8. ⏳ Login as headmaster
9. ⏳ Review pending reports
10. ⏳ Approve/reject with remarks

### API Testing
```bash
# Get students for report builder
curl -X GET http://localhost:5000/api/homeroom/report-builder/students?class_name=JHS%201 \
  -H "Authorization: Bearer <token>" \
  -H "X-School-ID: <school_id>"

# Create/update report card
curl -X POST http://localhost:5000/api/homeroom/report-builder/report \
  -H "Authorization: Bearer <token>" \
  -H "X-School-ID: <school_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": 1,
    "academic_term": "Term 1",
    "academic_year": "2024/2025",
    "subject_grades": [
      {"subject": "Mathematics", "class_score": 25, "exam_score": 65, "total": 90, "position": "1st", "grade": "A", "remarks": "Excellent", "diagnostic_topics": [{"topic": "Geometry", "score": 6, "max_score": 15}]}
    ],
    "overall_position": "3rd",
    "out_of_students": 40,
    "attendance_percentage": 95.5,
    "total_attendance": 160,
    "homeroom_teacher_remarks": "Outstanding performance this term."
  }'
```

## Future Enhancements

### Phase 2 (Template System)
- [ ] Load subject list from tenant's uploaded template
- [ ] Dynamic form generation based on template structure
- [ ] Template preview before data entry
- [ ] Multi-template support per school

### Phase 3 (Print/Export)
- [x] Print report card with tenant branding
- [x] Render diagnostic strand insights on printable reports when present
- [ ] PDF export with digital signature
- [ ] Bulk print for entire class
- [ ] Parent portal view (read-only)

### Phase 4 (AI Integration)
- [ ] Auto-generate teacher remarks based on grades
- [ ] Performance trend analysis
- [ ] Comparison with previous terms
- [ ] Predictive insights

## Files Changed/Created

### Backend
- ✅ [backend/api/models.py](backend/api/models.py) - Added `ReportCard` model
- ✅ [backend/routes.py](backend/routes.py) - Added 7 new endpoints
- ✅ [alembic/versions/004_add_report_cards.py](alembic/versions/004_add_report_cards.py) - Migration script
- ✅ [init_report_cards.py](../../scripts/maintenance/init_report_cards.py) - Database initialization helper

### Frontend
- ✅ [frontend/react/src/features/ReportBuilder.jsx](frontend/react/src/features/ReportBuilder.jsx) - Main UI component
- ✅ [frontend/react/src/App.jsx](frontend/react/src/App.jsx) - Added `/report-builder` route
- ✅ [frontend/react/src/components/Layout.jsx](frontend/react/src/components/Layout.jsx) - Added navigation link

## Deployment Checklist

1. ✅ Database migration applied
2. ⏳ Backend restarted to load new routes
3. ⏳ Frontend rebuilt with new component
4. ⏳ Test homeroom teacher access
5. ⏳ Test headmaster approval flow
6. ⏳ Verify subject teacher grade submission
7. ⏳ Update user documentation with new feature

## Support & Maintenance

### Common Issues
- **Report not saving**: Check JWT token validity and school_id header
- **Student not showing**: Verify student has `current_class` matching homeroom teacher's `assigned_class`
- **Grades not loading**: Subject teacher must finalize grades with `is_finalized=True`

### Monitoring
- Track report card submission rate via audit logs
- Monitor approval turnaround time
- Alert on rejected reports (requires follow-up)

## Conclusion

This implementation provides a complete, production-ready manual report card entry system that:
- ✅ Eliminates dependency on unreliable OCR
- ✅ Maintains flexibility for different school formats
- ✅ Supports full role-based workflow (teacher → headmaster)
- ✅ Integrates with existing grade submission infrastructure
- ✅ Provides audit trail and approval workflow
- ✅ Ready for tenant-specific template customization

**Status**: Feature complete and ready for testing
**Next Steps**: User acceptance testing with homeroom teacher and headmaster roles
