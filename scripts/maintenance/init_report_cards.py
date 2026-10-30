#!/usr/bin/env python
"""Initialize database with all tables including ReportCard with proprietor approval."""

from sqlalchemy import text

from backend.api.api import app, db

with app.app_context():
    # Drop and recreate report_cards table to include new fields
    with db.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS report_cards"))
        conn.commit()

    db.create_all()
    print("✅ Database tables created successfully!")
    print("   - report_cards table with proprietor approval workflow")
    print("   - ai_performance_analysis field added")
    print("   - Multi-stage approval: Homeroom → Headmaster → Proprietor → Print")
