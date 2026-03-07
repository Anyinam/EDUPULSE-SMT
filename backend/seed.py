import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from backend.api.api import app
from backend.api.models import (
    AcademicTerm,
    AuditLog,
    Inventory,
    Payment,
    ReportCard,
    School,
    SchoolSettings,
    Student,
    User,
    add_ledger_entry,
    db,
)


def seed_everything():
    with app.app_context():
        print(" Initializing EduPulse SMT Database for CCA Ofankor...")
        db.drop_all()
        db.create_all()

        # 1. Setup School
        cca = School(
            id="CCA-OFK",
            name="Christian Centre Academy - Ofankor",
            # Payment Account Details
            bank_name="GCB Bank",
            bank_account="1234567890123",
            bank_account_name="Christian Centre Academy - Ofankor",
            bank_branch="Ofankor Branch",
            # Contact Details
            school_email="info@cca-ofankor.edu.gh",
            school_phone="0302123456",
            school_address="Plot 45, Ofankor Estates, Accra",
            school_website="www.cca-ofankor.edu.gh",
        )
        db.session.add(cca)

        # 1b. Setup Default Business Rules
        cca_settings = SchoolSettings(
            school_id="CCA-OFK",
            tuition_fee=1000.0,
            feeding_fee=200.0,
            uniform_fee=150.0,
            transport_fee=100.0,
            terminal_report_fee=50.0,
            currency="GH₵",
        )
        db.session.add(cca_settings)

        # 2. Setup Staff with Hashed Passwords
        # Proprietor (The Boss)
        boss = User(
            username="proprietor_cca",
            password_hash=generate_password_hash("cca2026"),
            role="proprietor",
            school_id="CCA-OFK",
        )

        # Homeroom Teacher (Class Administrator)
        homeroom = User(
            username="homeroom_teacher",
            password_hash=generate_password_hash("homeroom123"),
            role="teacher",
            school_id="CCA-OFK",
            assigned_class="JHS 1",
        )

        # Subject Teacher (Subject Specialist)
        subject_teacher = User(
            username="subject_teacher",
            password_hash=generate_password_hash("subject123"),
            role="teacher",
            school_id="CCA-OFK",
        )

        # Headmaster (Academic Overseer)
        headmaster = User(
            username="headmaster_cca",
            password_hash=generate_password_hash("headmaster123"),
            role="headmaster",
            school_id="CCA-OFK",
        )

        # Finance Officer (Bursar)
        finance = User(
            username="finance_cca",
            password_hash=generate_password_hash("finance123"),
            role="finance",
            school_id="CCA-OFK",
        )

        # Kitchen Staff (Canteen Manager)
        kitchen = User(
            username="kitchen_staff",
            password_hash=generate_password_hash("kitchen123"),
            role="kitchen",
            school_id="CCA-OFK",
        )

        # Store Manager (Inventory)
        store_manager = User(
            username="store_manager",
            password_hash=generate_password_hash("store123"),
            role="inventory_manager",
            school_id="CCA-OFK",
        )

        db.session.add_all(
            [boss, homeroom, subject_teacher, headmaster, finance, kitchen, store_manager]
        )

        # 3. Setup Students (Sack Risk Scenarios)
        # Kofi is the 'Stable' control
        kofi = Student(
            first_name="Kofi",
            surname="Mensah",
            name="Kofi Mensah",
            student_code="S001",
            school_id="CCA-OFK",
            current_class="JHS 1",
            feeding_paid=True,
            is_present=True,
            guardian_name="Ama Mensah",
            parent_phone="+233501234567",
            parent_email="ama@example.com",
            total_tuition_owed=500.0,
            tuition_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            gender="Male",
        )
        # Abena is our 'At Risk' student for the demo
        abena = Student(
            first_name="Abena",
            surname="Selorm",
            name="Abena Selorm",
            student_code="S002",
            school_id="CCA-OFK",
            current_class="JHS 1",
            feeding_paid=False,
            is_present=True,
            guardian_name="John Selorm",
            parent_phone="+233502345678",
            parent_email="john@example.com",
            total_tuition_owed=750.0,
            tuition_deadline=datetime.now(timezone.utc) - timedelta(days=10),
            gender="Female",
        )
        db.session.add_all([kofi, abena])
        db.session.commit()  # Commit to get student IDs for payments

        # 4. Financials: Test payment tracking (MoMo + Bank Transfer Automation with Reference Parsing)
        # Reference Format: STUDENT_CODE-CATEGORY (e.g., S001-T1, S002-FEED-MON)
        # This mimics how parents would enter reference when making MoMo/Bank transfers

        # Kofi: Successful automated bank transfer for TERM 1 TUITION (Reference: S001-T1)
        kofi_bank = Payment(
            student_id=kofi.id,
            school_id="CCA-OFK",
            amount=500.0,
            payment_type="Tuition",
            method="Bank_Auto",  # Automated bank transfer
            reference_id="BANK-GCB-2026-001",  # Transaction ID from bank
            status="Confirmed",
            verified_by=finance.id,  # Finance officer verified
            payment_category={"term": "Term 1"},  # Extracted from reference: S001-T1
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(kofi_bank)

        # Kofi: DAILY FEEDING payment via MoMo (Reference: S001-FEED-DAY)
        kofi_feeding = Payment(
            student_id=kofi.id,
            school_id="CCA-OFK",
            amount=5.0,
            payment_type="Feeding",
            method="MoMo_Auto",
            reference_id="MOMO-2026-001",
            status="Confirmed",
            verified_by=kitchen.id,  # Kitchen staff verified
            payment_category={
                "frequency": "Daily"
            },  # Extracted from reference: S001-FEED-DAY
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(kofi_feeding)

        # Abena: Pending bank transfers as backup (manual workflow)
        for i in range(4):
            missed = Payment(
                student_id=abena.id,
                school_id="CCA-OFK",
                amount=5.0,
                payment_type="Feeding",
                method="Bank",
                status="Pending",
                date_paid=datetime.now(timezone.utc),
            )
            db.session.add(missed)

        # Abena: One confirmed bank payment for TERM 2 TUITION
        abena_bank_confirmed = Payment(
            student_id=abena.id,
            school_id="CCA-OFK",
            amount=250.0,
            payment_type="Tuition",
            method="Bank_Auto",  # Auto-recorded from bank webhook
            reference_id="BANK-ECO-2026-001",
            status="Confirmed",
            verified_by=finance.id,  # Finance officer verified
            payment_category={"term": "Term 2"},  # Different term
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(abena_bank_confirmed)

        # Abena: MONTHLY FEEDING payment
        abena_feeding = Payment(
            student_id=abena.id,
            school_id="CCA-OFK",
            amount=100.0,
            payment_type="Feeding",
            method="Cash",
            status="Confirmed",
            verified_by=kitchen.id,  # Kitchen staff verified
            payment_category={"frequency": "Monthly"},  # Monthly feeding plan
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(abena_feeding)

        # Abena: UNIFORM purchase (specific item)
        abena_uniform = Payment(
            student_id=abena.id,
            school_id="CCA-OFK",
            amount=150.0,
            payment_type="Uniform",
            method="Cash",
            status="Confirmed",
            verified_by=store_manager.id,  # Store manager verified
            payment_category={
                "item": "School Uniform - Size Large",
                "quantity": 2,
            },  # Item-level tracking
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(abena_uniform)

        # 5. Inventory: School Store items
        inventory_items = [
            Inventory(
                school_id="CCA-OFK",
                item_name="School Uniform",
                category="Uniform",
                item_type="Top Only",
                size="M",
                class_group="Class 1-6",
                gender="Unisex",
                sku="UNIFTOPM",
                unit="piece",
                quantity=20,
                price=70.0,
            ),
            Inventory(
                school_id="CCA-OFK",
                item_name="School Uniform",
                category="Uniform",
                item_type="Shorts Only",
                size="M",
                class_group="Class 1-6",
                gender="Male",
                sku="UNIFSHM",
                unit="piece",
                quantity=8,
                price=60.0,
            ),
            Inventory(
                school_id="CCA-OFK",
                item_name="School Uniform",
                category="Uniform",
                item_type="Top Only",
                size="L",
                class_group="JHS",
                gender="Unisex",
                sku="UNIFTOPL",
                unit="piece",
                quantity=4,
                price=85.0,
            ),
            Inventory(
                school_id="CCA-OFK",
                item_name="Friday Wear",
                category="Uniform",
                item_type="Friday Wear",
                size="L",
                class_group="All",
                gender="Unisex",
                sku="FRIWEL",
                unit="set",
                quantity=6,
                price=120.0,
            ),
            Inventory(
                school_id="CCA-OFK",
                item_name="Mathematics Textbook",
                category="Books",
                item_type="Textbook",
                size="N/A",
                class_group="JHS",
                gender="Unisex",
                sku="MATHJHS",
                unit="piece",
                quantity=12,
                price=90.0,
            ),
        ]
        db.session.add_all(inventory_items)

        # 6. Academic Terms
        term_1 = AcademicTerm(
            school_id="CCA-OFK",
            name="Term 1",
            academic_year="2025/2026",
            start_date=datetime.now(timezone.utc).date() - timedelta(days=60),
            end_date=datetime.now(timezone.utc).date() + timedelta(days=30),
            is_active=True,
            billing_due_date=datetime.now(timezone.utc).date() - timedelta(days=45),
            created_by=boss.id,
        )
        term_2 = AcademicTerm(
            school_id="CCA-OFK",
            name="Term 2",
            academic_year="2025/2026",
            start_date=datetime.now(timezone.utc).date() + timedelta(days=40),
            end_date=datetime.now(timezone.utc).date() + timedelta(days=120),
            is_active=False,
            billing_due_date=datetime.now(timezone.utc).date() + timedelta(days=45),
            created_by=boss.id,
        )
        db.session.add_all([term_1, term_2])

        # 7. Inventory payment (store purchase)
        abena_inventory = Payment(
            student_id=abena.id,
            school_id="CCA-OFK",
            amount=120.0,
            payment_type="Inventory",
            method="Cash",
            status="Confirmed",
            verified_by=store_manager.id,  # Store manager verified
            payment_category={
                "item_name": "Friday Wear",
                "item_type": "Friday Wear",
                "size": "L",
                "sku": "FRIWEL",
                "quantity": 1,
            },
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(abena_inventory)

        # 8. Terminal report printing fee
        kofi_report_fee = Payment(
            student_id=kofi.id,
            school_id="CCA-OFK",
            amount=50.0,
            payment_type="Terminal Report",
            method="Cash",
            status="Confirmed",
            verified_by=finance.id,  # Finance officer verified
            payment_category={"term": "Term 1"},
            date_paid=datetime.now(timezone.utc),
        )
        db.session.add(kofi_report_fee)

        # 9. Report cards for performance analytics
        report_kofi = ReportCard(
            school_id="CCA-OFK",
            student_id=kofi.id,
            academic_term="Term 1",
            academic_year="2025/2026",
            class_name="JHS 1",
            term_average=78.5,
            overall_position="3rd",
            out_of_students=25,
            status="Published",
        )
        report_abena = ReportCard(
            school_id="CCA-OFK",
            student_id=abena.id,
            academic_term="Term 1",
            academic_year="2025/2026",
            class_name="JHS 1",
            term_average=62.0,
            overall_position="12th",
            out_of_students=25,
            status="Published",
        )
        db.session.add_all([report_kofi, report_abena])

        # 10. Audit Log: Mock initial action
        init_log = AuditLog(
            actor_id=boss.id,
            action="SYSTEM_INIT",
            details="Proprietor initialized the 2026 Academic Term data.",
        )
        db.session.add(init_log)

        # Flush to get payment IDs before creating ledger entries
        db.session.flush()

        # 11. Create ledger entries for all confirmed payments
        # (Event listener is disabled, so we create them manually)
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="tuition",
            tx_ref=kofi_bank.reference_id,
            amount=kofi_bank.amount,
            currency="GH₵",
            actor_id=finance.id,
            student_id=kofi.id,
            source="bank_auto",
            metadata={
                "payment_id": kofi_bank.id,
                "student_name": kofi.name,
                "student_code": kofi.student_code,
                "payment_category": kofi_bank.payment_category,
                "recorded_by": "Finance Officer"
            },
            created_at=kofi_bank.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="feeding",
            tx_ref=kofi_feeding.reference_id,
            amount=kofi_feeding.amount,
            currency="GH₵",
            actor_id=kitchen.id,
            student_id=kofi.id,
            source="momo_auto",
            metadata={
                "payment_id": kofi_feeding.id,
                "student_name": kofi.name,
                "student_code": kofi.student_code,
                "payment_category": kofi_feeding.payment_category,
                "recorded_by": "Kitchen Staff"
            },
            created_at=kofi_feeding.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="tuition",
            tx_ref=abena_bank_confirmed.reference_id,
            amount=abena_bank_confirmed.amount,
            currency="GH₵",
            actor_id=finance.id,
            student_id=abena.id,
            source="bank_auto",
            metadata={
                "payment_id": abena_bank_confirmed.id,
                "student_name": abena.name,
                "student_code": abena.student_code,
                "payment_category": abena_bank_confirmed.payment_category,
                "recorded_by": "Finance Officer"
            },
            created_at=abena_bank_confirmed.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="feeding",
            tx_ref=f"PAY-{abena_feeding.id}",
            amount=abena_feeding.amount,
            currency="GH₵",
            actor_id=kitchen.id,
            student_id=abena.id,
            source="cash",
            metadata={
                "payment_id": abena_feeding.id,
                "student_name": abena.name,
                "student_code": abena.student_code,
                "payment_category": abena_feeding.payment_category,
                "recorded_by": "Kitchen Staff"
            },
            created_at=abena_feeding.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="uniform",
            tx_ref=f"PAY-{abena_uniform.id}",
            amount=abena_uniform.amount,
            currency="GH₵",
            actor_id=store_manager.id,
            student_id=abena.id,
            source="cash",
            metadata={
                "payment_id": abena_uniform.id,
                "student_name": abena.name,
                "student_code": abena.student_code,
                "payment_category": abena_uniform.payment_category,
                "recorded_by": "Store Manager"
            },
            created_at=abena_uniform.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="inventory",
            tx_ref=f"PAY-{abena_inventory.id}",
            amount=abena_inventory.amount,
            currency="GH₵",
            actor_id=store_manager.id,
            student_id=abena.id,
            source="cash",
            metadata={
                "payment_id": abena_inventory.id,
                "student_name": abena.name,
                "student_code": abena.student_code,
                "payment_category": abena_inventory.payment_category,
                "recorded_by": "Store Manager"
            },
            created_at=abena_inventory.date_paid,
        )
        
        add_ledger_entry(
            school_id="CCA-OFK",
            tx_type="terminal_report",
            tx_ref=f"PAY-{kofi_report_fee.id}",
            amount=kofi_report_fee.amount,
            currency="GH₵",
            actor_id=finance.id,
            student_id=kofi.id,
            source="cash",
            metadata={
                "payment_id": kofi_report_fee.id,
                "student_name": kofi.name,
                "student_code": kofi.student_code,
                "payment_category": kofi_report_fee.payment_category,
                "recorded_by": "Finance Officer"
            },
            created_at=kofi_report_fee.date_paid,
        )

        db.session.commit()
        print("✅ CCA Ofankor Environment Ready for Demo!")


if __name__ == "__main__":
    seed_everything()
