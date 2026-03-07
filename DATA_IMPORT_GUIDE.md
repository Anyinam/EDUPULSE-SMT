# EduPulse Data Import Guide

This guide explains the CSV import format and which fields are required for bulk uploads.

## Students (Bulk Upload)

Upload CSV to the Admissions Panel using the fields below.

### Required fields:
- first_name
- surname
- gender
- class_assigned

### Optional fields:
- student_code (leave blank to auto-generate)
- guardian_name
- parent_email

### Notes:
- If student_code is blank, the system generates one using the school ID.
- gender must be: Male, Female, or Other
- parent_email is optional but recommended for notifications.
- class_assigned must match a valid grade level (e.g., Class 1, Class 2, JHS 1, JHS 2, JHS 3, SHS 1, SHS 2, SHS 3).

### Example Row:
```csv
first_name,surname,gender,class_assigned,guardian_name,parent_email
Kwame,Asante,Male,JHS 1,Kweku Asante,kwaku@example.com
Ama,Osei,Female,JHS 1,Ama Serwa,ama@example.com
```

---

## Staff (Bulk Upload)

Upload CSV to Staff Management using the fields below.

### Required Fields:
- username (unique per school, e.g., kwame_teacher, ama_homeroom)
- email (required for notifications and password recovery)
- password (minimum 8 characters)

### Optional Fields:
- roles (comma-separated: teacher, homeroom, headmaster, finance. Default: teacher)
- assigned_class (homeroom class, e.g., JHS 1, Class 4)
- assigned_classes (pipe or semicolon-separated list of classes to teach, e.g., JHS 1|JHS 2)
- assigned_subjects (pipe or semicolon-separated list of subjects, e.g., Mathematics|Science)

### Notes:
- Passwords must be at least 8 characters (you can set custom ones during bulk upload)
- Multiple roles can be assigned using comma separation (e.g., "teacher,homeroom")
- For teacher/homeroom roles, assign teaching classes and subjects using pipe (|) or semicolon (;) separators
- assigned_class is typically the primary class they manage as a homeroom teacher
- If no roles specified, defaults to "teacher"

### Example Rows:
```csv
username,email,password,roles,assigned_class,assigned_classes,assigned_subjects
kwame_teacher,kwame@school.edu,SecurePass123,teacher,JHS 1,JHS 1|JHS 2,Mathematics|Science
ama_homeroom,ama@school.edu,SecurePass123,homeroom,Class 4,Class 4,English Language|Social Studies
kofi_math,kofi@school.edu,SecurePass123,teacher,,JHS 2|JHS 3,Mathematics
abena_head,abena@school.edu,SecurePass123,headmaster,,,
nana_finance,nana@school.edu,SecurePass123,finance,,,
adwoa_multi,adwoa@school.edu,SecurePass123,teacher;homeroom,Class 6,Class 5|Class 6,English Language;French
```

### Staff Roles Explained:
- **teacher**: Can enter grades and submit lesson notes for assigned classes/subjects
- **homeroom**: Manages attendance and reports for their homeroom class (usually also a teacher)
- **headmaster**: Approves lesson notes and manages academic reports for the school
- **finance**: Manages payment records and financial reports

---

## Import Best Practices

1. **Always test with a small batch first** - Export 2-3 rows and test before uploading hundreds of records
2. **Check for duplicates** - The system prevents duplicate usernames (students) and staff usernames
3. **Validate class names** - Class assignments must match existing classes: Class 1-6, JHS 1-3, SHS 1-3, Nursery, KG
4. **Email format** - All emails must be valid format (user@domain.com)
5. **Keep backups** - Always keep a copy of your import data in case you need to re-import
6. **Review errors** - The system reports errors clearly (row number, field, reason) to help you fix issues

---

## Troubleshooting

### Student Import Issues
- **"Invalid class_assigned"**: Check that class names match exactly (e.g., "JHS 1" not "JHS1")
- **"Student code already exists"**: If providing student codes, ensure they're unique
- **"Missing first_name and/or surname"**: Check that you have both first and last names

### Staff Import Issues
- **"Username already exists"**: Choose unique usernames for each staff member
- **"Password must be at least 8 characters"**: Ensure all passwords are 8+ characters
- **"Invalid role"**: Use only: teacher, homeroom, headmaster, finance
- **"Missing email"**: Email is required for all staff members
