#!/usr/bin/env python3
"""Backfill missing student codes for legacy student records.

Why this exists:
- Normal student admission and upload flows already assign student IDs automatically.
- Some legacy or inconsistent records may still exist without a usable `student_code`.
- Payment instructions and tracked transfer routes depend on a stable student code.

Behavior:
- Finds students whose `student_code` is null, empty, or whitespace-only.
- Proposes the next available code using the existing school prefix convention.
- Leaves valid existing student codes unchanged.

Usage:
- Dry run (default):
  python backfill_missing_student_codes.py
- Apply changes:
  python backfill_missing_student_codes.py --apply
- Restrict to one school:
  python backfill_missing_student_codes.py --school-id TEST-001 --apply
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from backend.api.api import app
from backend.api.models import Student, db
from backend.routes import generate_student_code, normalize_student_code_prefix


def _normalized_code(value: object) -> str:
    return str(value or "").strip().upper()


def _student_needs_code(student: Student) -> bool:
    return not _normalized_code(getattr(student, "student_code", ""))


def _existing_codes() -> set[str]:
    rows = db.session.query(Student.student_code).filter(Student.student_code.isnot(None)).all()
    return {_normalized_code(row[0]) for row in rows if _normalized_code(row[0])}


def _generate_code_for_school(school_id: str, reserved_codes: set[str]) -> str:
    prefix = normalize_student_code_prefix(school_id)
    next_index = Student.query.filter_by(school_id=school_id).count() + 1

    while True:
        candidate = generate_student_code(prefix, next_index)
        if candidate not in reserved_codes:
            reserved_codes.add(candidate)
            return candidate
        next_index += 1


def _load_target_students(school_id: str | None) -> list[Student]:
    query = Student.query
    if school_id:
        query = query.filter_by(school_id=school_id)
    students = query.order_by(Student.school_id.asc(), Student.id.asc()).all()
    return [student for student in students if _student_needs_code(student)]


def run_backfill(*, apply_changes: bool, school_id: str | None) -> int:
    target_students = _load_target_students(school_id)
    if not target_students:
        scope = school_id or "all schools"
        print(f"No students with missing codes found for {scope}.")
        return 0

    reserved_codes = _existing_codes()
    summary_by_school: dict[str, list[tuple[int, str, str]]] = defaultdict(list)

    for student in target_students:
        new_code = _generate_code_for_school(student.school_id, reserved_codes)
        student_name = getattr(student, "name", None) or f"{getattr(student, 'first_name', '')} {getattr(student, 'surname', '')}".strip() or "Unknown"
        summary_by_school[student.school_id].append((student.id, student_name, new_code))
        if apply_changes:
            student.student_code = new_code

    print("Missing student code backfill summary")
    print("=" * 60)
    total = 0
    for scoped_school_id in sorted(summary_by_school):
        entries = summary_by_school[scoped_school_id]
        total += len(entries)
        print(f"{scoped_school_id}: {len(entries)} student(s)")
        for student_id, student_name, new_code in entries:
            print(f"  - Student #{student_id} | {student_name} -> {new_code}")

    print("=" * 60)
    print(f"Total students to update: {total}")

    if apply_changes:
        db.session.commit()
        print("Changes committed.")
    else:
        db.session.rollback()
        print("Dry run only. Re-run with --apply to persist changes.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing student codes.")
    parser.add_argument("--apply", action="store_true", help="Persist generated student codes.")
    parser.add_argument("--school-id", help="Restrict the backfill to a single school ID.")
    args = parser.parse_args()

    with app.app_context():
        return run_backfill(apply_changes=args.apply, school_id=args.school_id)


if __name__ == "__main__":
    sys.exit(main())