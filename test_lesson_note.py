#!/usr/bin/env python
"""
Test script to verify lesson note submission with daily phases
"""

import os
import sys

# Add backend to path
sys.path.insert(0, "/home/anyinam/Documents/EduPulse")

# Set test environment
os.environ["FLASK_ENV"] = "testing"
os.environ["DATABASE_URL"] = (
    "sqlite:////home/anyinam/Documents/EduPulse/backend/instance/edupulse.db"
)

from backend.api.api import app, db
from backend.api.models import DailyLessonPhase, LessonNote

print("Testing lesson note submission with daily phases...\n")

try:
    with app.app_context():
        # Create test lesson note
        note = LessonNote(
            school_id="TEST-001",
            teacher_id=1,
            week_number=3,
            subject="Mathematics",
            class_name="Class 4",
            indicator_code="MATH-4-1",
            content_standard_code="CS-M-4-1",
            performance_indicator="Student can solve equations",
            core_competencies="Problem solving, Critical thinking",
            key_words="Algebra, Equations, Variables",
            teaching_learning_resources="Textbooks, Whiteboard, Calculator",
            references="Math Curriculum 2023",
            content="Lesson on solving linear equations",
            ai_score=75,
            ai_feedback="Good structure",
        )

        db.session.add(note)
        db.session.flush()  # Get the ID without committing

        print(f"✓ Created test lesson note with ID: {note.id}")

        # Create daily phases
        phases = [
            {
                "day": "Monday",
                "phase_1_starter": "Review previous concepts",
                "phase_2_main": "Introduce linear equations and solve 3 examples",
                "phase_3_plenary": "Students reflect and summarize",
            },
            {
                "day": "Wednesday",
                "phase_1_starter": "Quick recap of Monday lesson",
                "phase_2_main": "Practice problems on equations with group work",
                "phase_3_plenary": "Class discussion on challenges faced",
            },
        ]

        for phase_data in phases:
            phase = DailyLessonPhase(
                lesson_note_id=note.id,
                day=phase_data["day"],
                phase_1_starter=phase_data["phase_1_starter"],
                phase_2_main=phase_data["phase_2_main"],
                phase_3_plenary=phase_data["phase_3_plenary"],
            )
            db.session.add(phase)
            print(f"✓ Created daily phase for {phase_data['day']}")

        db.session.commit()
        print(
            f"\n✓ Successfully saved lesson note and {len(phases)} daily phases to database"
        )

        # Verify by querying back
        saved_note = LessonNote.query.filter_by(id=note.id).first()
        saved_phases = DailyLessonPhase.query.filter_by(lesson_note_id=note.id).all()

        print(f"\nVerification:")
        print(f"✓ Lesson note: {saved_note.subject} - {saved_note.class_name}")
        print(f"✓ Teacher ID: {saved_note.teacher_id}")
        print(f"✓ Indicator code: {saved_note.indicator_code}")
        print(f"✓ Daily phases count: {len(saved_phases)}")

        for phase in saved_phases:
            print(
                f"  - {phase.day}: Phase 1 starter set: {bool(phase.phase_1_starter)}, Phase 2 main set: {bool(phase.phase_2_main)}, Phase 3 plenary set: {bool(phase.phase_3_plenary)}"
            )

        print(
            "\n✅ Test passed! Database migration is complete and models work correctly."
        )

except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
