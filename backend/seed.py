import os
import sys
import base64
import shutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from backend.api.api import app
from backend.api.models import (
    AcademicTerm,
    AuditLog,
    Inventory,
    Payment,
    ParentAdmissionApplication,
    ReportCard,
    School,
    SchoolSettings,
    SchoolVerification,
    Student,
    User,
    add_ledger_entry,
    db,
)
from backend.schema_management import rebuild_database_from_migrations


def _build_demo_profile_picture(name, primary_color, accent_color):
    initials = "".join(part[0].upper() for part in str(name).split()[:2] if part) or "ST"
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 240'>
      <defs>
        <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='{primary_color}' />
          <stop offset='100%' stop-color='{accent_color}' />
        </linearGradient>
      </defs>
      <rect width='240' height='240' rx='56' fill='url(#bg)' />
      <circle cx='120' cy='94' r='42' fill='rgba(255,255,255,0.24)' />
      <path d='M54 196c10-34 36-54 66-54s56 20 66 54' fill='rgba(255,255,255,0.18)' />
      <text x='120' y='214' text-anchor='middle' font-size='42' font-family='Arial, sans-serif' font-weight='700' fill='white'>{initials}</text>
    </svg>
    """.strip()
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _reset_school_storage(instance_path, folder_name, school_id):
    school_dir = os.path.join(instance_path, folder_name, school_id)
    if os.path.isdir(school_dir):
        shutil.rmtree(school_dir)
    os.makedirs(school_dir, exist_ok=True)
    return school_dir


def _write_demo_document(instance_path, folder_name, school_id, document_id, original_filename, content_type, body_bytes):
    school_dir = os.path.join(instance_path, folder_name, school_id)
    os.makedirs(school_dir, exist_ok=True)
    stored_filename = f"{document_id}_{original_filename}"
    file_path = os.path.join(school_dir, stored_filename)
    with open(file_path, "wb") as handle:
        handle.write(body_bytes)
    return {
        "document_id": document_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": os.path.getsize(file_path),
    }


def _build_demo_student_document_manifest(instance_path, school_id, student_code, uploaded_by_user_id):
    documents = []

    birth_certificate = _write_demo_document(
        instance_path,
        "student-documents",
        school_id,
        f"student_doc_{student_code.lower()}_birth",
        f"{student_code.lower()}_birth_certificate.txt",
        "text/plain",
        (
            f"Learner Birth Record\nStudent: {student_code}\nIssued by: Demo Civil Registry\n"
            f"Verified for demo profile view on {datetime.now(timezone.utc).date().isoformat()}\n"
        ).encode("utf-8"),
    )
    birth_certificate.update(
        {
            "category": "birth_certificate",
            "source": "student_profile",
            "note": "Seeded proof-of-age record for the student dossier demo.",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by_user_id": uploaded_by_user_id,
        }
    )
    documents.append(birth_certificate)

    consent_letter = _write_demo_document(
        instance_path,
        "student-documents",
        school_id,
        f"student_doc_{student_code.lower()}_consent",
        f"{student_code.lower()}_guardian_consent_letter.txt",
        "text/plain",
        (
            f"Guardian Consent Letter\nStudent: {student_code}\nPurpose: Academic records, welfare follow-up, and school communication.\n"
            f"Status: Accepted in demo environment.\n"
        ).encode("utf-8"),
    )
    consent_letter.update(
        {
            "category": "consent_letter",
            "source": "student_profile",
            "note": "Guardian communication and data-use consent.",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by_user_id": uploaded_by_user_id,
        }
    )
    documents.append(consent_letter)

    return documents


def _build_demo_admission_manifest(instance_path, school_id, student_code):
    admission_form = _write_demo_document(
        instance_path,
        "parent-admission-documents",
        school_id,
        f"parent_doc_{student_code.lower()}_form",
        f"{student_code.lower()}_admission_form.txt",
        "text/plain",
        (
            f"Parent Admissions Form\nApplicant Code: APP-{student_code}\n"
            f"Contains original intake details used to admit learner {student_code}.\n"
        ).encode("utf-8"),
    )
    admission_form.update(
        {
            "category": "admission_form",
        }
    )

    prior_report = _write_demo_document(
        instance_path,
        "parent-admission-documents",
        school_id,
        f"parent_doc_{student_code.lower()}_report",
        f"{student_code.lower()}_previous_report.txt",
        "text/plain",
        (
            f"Previous Academic Report\nStudent: {student_code}\nAverage: 64.0\nStrength: English and Social Studies\n"
            f"Support Need: Mathematics improvement plan.\n"
        ).encode("utf-8"),
    )
    prior_report.update(
        {
            "category": "previous_report",
        }
    )

    return [admission_form, prior_report]


def seed_everything():
    with app.app_context():
        print(" Initializing EduPulse SMT Database for CCA Ofankor...")
        rebuild_database_from_migrations(db)
        _reset_school_storage(app.instance_path, "student-documents", "CCA-OFK")
        _reset_school_storage(app.instance_path, "parent-admission-documents", "CCA-OFK")

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
            email=(os.getenv("SEED_PROPRIETOR_EMAIL") or os.getenv("MAIL_USERNAME") or None),
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
        db.session.flush()

        cca.trial_plan = "Premium"
        cca.trial_end_date = datetime.now(timezone.utc) + timedelta(days=30)
        cca.is_trial_active = True

        cca_settings.report_template_config = {
            "__global_report_settings__": {
                "data_compliance_workflow": {
                    "registration_acknowledgements": {
                        "school_data_authority_confirmed": True,
                        "legacy_and_exam_consent_plan_confirmed": True,
                        "aggregated_analytics_accepted": True,
                        "accepted_at": datetime.now(timezone.utc).isoformat(),
                        "accepted_ip": "127.0.0.1",
                        "terms_version": "demo-seed",
                        "policy_version": "demo-seed",
                        "proprietor_user_id": boss.id,
                    },
                    "legacy_migration": {
                        "parent_notice_dispatched": True,
                        "consent_collection_completed": True,
                        "consent_collection_date": datetime.now(timezone.utc).date().isoformat(),
                        "evidence_notes": "Seeded demo environment includes exam-intelligence policy readiness.",
                        "evidence_artifacts": [],
                        "bece_result_processing_enabled": True,
                        "bece_parent_notice_confirmed": True,
                    },
                }
            }
        }

        db.session.add(
            SchoolVerification(
                school_id="CCA-OFK",
                status="verified",
                risk_tier="low",
                legal_name="Christian Centre Academy - Ofankor",
                organization_id="CCA-OFK",
                registration_number="DEMO-CCA-2026",
                bank_account_name="Christian Centre Academy - Ofankor",
                bank_account_number="1234567890123",
                bank_name="GCB Bank",
                submitted_by_user_id=boss.id,
                review_notes="Seeded demo verification approved for local development.",
                submitted_at=datetime.now(timezone.utc),
                reviewed_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
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
            profile_picture=_build_demo_profile_picture("Kofi Mensah", "#0f766e", "#14b8a6"),
            feeding_paid=True,
            is_present=True,
            guardian_name="Ama Mensah",
            parent_name="Ama Mensah",
            parent_phone="+233501234567",
            parent_email="ama@example.com",
            total_tuition_owed=500.0,
            tuition_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            date_of_birth=date(2012, 5, 14),
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
            profile_picture=_build_demo_profile_picture("Abena Selorm", "#7c3aed", "#ec4899"),
            feeding_paid=False,
            is_present=True,
            guardian_name="John Selorm",
            parent_name="John Selorm",
            parent_phone="+233502345678",
            parent_email="john@example.com",
            total_tuition_owed=750.0,
            tuition_deadline=datetime.now(timezone.utc) - timedelta(days=10),
            date_of_birth=date(2013, 1, 23),
            gender="Female",
        )
        db.session.add_all([kofi, abena])
        db.session.commit()  # Commit to get student IDs for payments

        kofi.custom_attributes = {
            "document_manifest": _build_demo_student_document_manifest(
                app.instance_path,
                "CCA-OFK",
                kofi.student_code,
                boss.id,
            ),
            "profile_highlights": [
                "Reads confidently and contributes actively in class.",
                "Maintains steady attendance and positive conduct.",
            ],
        }
        abena.custom_attributes = {
            "document_manifest": _build_demo_student_document_manifest(
                app.instance_path,
                "CCA-OFK",
                abena.student_code,
                boss.id,
            ),
            "profile_highlights": [
                "Needs close math support and fee follow-up.",
                "Responds well to structured mentoring and guardianship check-ins.",
            ],
        }

        abena_application = ParentAdmissionApplication(
            school_id="CCA-OFK",
            application_code="APP-S002-DEMO",
            status_token="demo-status-abena-s002",
            first_name="Abena",
            surname="Selorm",
            gender="Female",
            date_of_birth=abena.date_of_birth,
            preferred_class="JHS 1",
            guardian_name="John Selorm",
            parent_email="john@example.com",
            parent_phone="+233502345678",
            prior_school="Glorious Future Preparatory",
            desired_test_mode="either",
            internet_quality="limited",
            parent_notes="Seeded linked admissions file set for student profile demo.",
            document_manifest=_build_demo_admission_manifest(
                app.instance_path,
                "CCA-OFK",
                abena.student_code,
            ),
            ai_summary="Admissions review found enough supporting records to proceed, with follow-up recommended on mathematics support and fee planning.",
            ai_recommendation="manual_review",
            ai_readiness_score=74,
            ai_flags=["fee_follow_up", "math_support"],
            ai_missing_items=[],
            status="Approved",
            submitted_at=datetime.now(timezone.utc) - timedelta(days=30),
            reviewed_at=datetime.now(timezone.utc) - timedelta(days=27),
            reviewed_by_user_id=headmaster.id,
            reviewer_notes="Approved after review. Keep guardian updated on academic support milestones.",
            admitted_student_id=abena.id,
        )
        db.session.add(abena_application)
        db.session.commit()

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

        # 9b. Add more students across multiple classes for Class Performance Analytics
        # JHS 1 Additional Students
        kwame = Student(
            first_name="Kwame", surname="Boateng", name="Kwame Boateng",
            student_code="S003", school_id="CCA-OFK", current_class="JHS 1",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Yaa Boateng", parent_phone="+233503456789",
            parent_email="yaa@example.com"
        )
        esi = Student(
            first_name="Esi", surname="Addo", name="Esi Addo",
            student_code="S004", school_id="CCA-OFK", current_class="JHS 1",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Papa Addo", parent_phone="+233504567890",
            parent_email="papa@example.com"
        )
        yaw = Student(
            first_name="Yaw", surname="Appiah", name="Yaw Appiah",
            student_code="S005", school_id="CCA-OFK", current_class="JHS 1",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Grace Appiah", parent_phone="+233505678901",
            parent_email="grace@example.com"
        )
        
        # JHS 2 Students
        akua = Student(
            first_name="Akua", surname="Owusu", name="Akua Owusu",
            student_code="S006", school_id="CCA-OFK", current_class="JHS 2",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Mr. Owusu", parent_phone="+233506789012",
            parent_email="owusu@example.com"
        )
        kojo = Student(
            first_name="Kojo", surname="Asante", name="Kojo Asante",
            student_code="S007", school_id="CCA-OFK", current_class="JHS 2",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Mrs. Asante", parent_phone="+233507890123",
            parent_email="asante@example.com"
        )
        ama = Student(
            first_name="Ama", surname="Tetteh", name="Ama Tetteh",
            student_code="S008", school_id="CCA-OFK", current_class="JHS 2",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Mr. Tetteh", parent_phone="+233508901234",
            parent_email="tetteh@example.com"
        )
        kwesi = Student(
            first_name="Kwesi", surname="Darko", name="Kwesi Darko",
            student_code="S009", school_id="CCA-OFK", current_class="JHS 2",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Mrs. Darko", parent_phone="+233509012345",
            parent_email="darko@example.com"
        )
        
        # JHS 3 Students
        efua = Student(
            first_name="Efua", surname="Ansah", name="Efua Ansah",
            student_code="S010", school_id="CCA-OFK", current_class="JHS 3",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Mr. Ansah", parent_phone="+233510123456",
            parent_email="ansah@example.com"
        )
        kofi_jhs3 = Student(
            first_name="Kofi", surname="Sarpong", name="Kofi Sarpong",
            student_code="S011", school_id="CCA-OFK", current_class="JHS 3",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Mrs. Sarpong", parent_phone="+233511234567",
            parent_email="sarpong@example.com"
        )
        adwoa = Student(
            first_name="Adwoa", surname="Manu", name="Adwoa Manu",
            student_code="S012", school_id="CCA-OFK", current_class="JHS 3",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Mr. Manu", parent_phone="+233512345678",
            parent_email="manu@example.com"
        )
        
        # Primary 6 Students
        kwabena = Student(
            first_name="Kwabena", surname="Osei", name="Kwabena Osei",
            student_code="S013", school_id="CCA-OFK", current_class="Primary 6",
            feeding_paid=True, is_present=True, gender="Male",
            guardian_name="Mrs. Osei", parent_phone="+233513456789",
            parent_email="osei@example.com"
        )
        afua = Student(
            first_name="Afua", surname="Oppong", name="Afua Oppong",
            student_code="S014", school_id="CCA-OFK", current_class="Primary 6",
            feeding_paid=True, is_present=True, gender="Female",
            guardian_name="Mr. Oppong", parent_phone="+233514567890",
            parent_email="oppong@example.com"
        )
        
        db.session.add_all([
            kwame, esi, yaw, akua, kojo, ama, kwesi,
            efua, kofi_jhs3, adwoa, kwabena, afua
        ])
        db.session.commit()  # Commit to get student IDs
        
        # 9c. Create Report Cards for multiple terms to test Class Performance Analytics
        report_cards = []
        
        # Term 1 Report Cards (2025/2026)
        # JHS 1 - Term 1
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kwame.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 1", term_average=85.2,
                      overall_position="1st", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=esi.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 1", term_average=72.5,
                      overall_position="5th", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=yaw.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 1", term_average=68.0,
                      overall_position="8th", out_of_students=25, status="Published"),
        ])
        
        # JHS 2 - Term 1
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=akua.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 2", term_average=88.5,
                      overall_position="1st", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kojo.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 2", term_average=76.3,
                      overall_position="4th", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=ama.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 2", term_average=81.0,
                      overall_position="2nd", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kwesi.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 2", term_average=70.5,
                      overall_position="7th", out_of_students=30, status="Published"),
        ])
        
        # JHS 3 - Term 1
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=efua.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 3", term_average=91.2,
                      overall_position="1st", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kofi_jhs3.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 3", term_average=83.7,
                      overall_position="3rd", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=adwoa.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="JHS 3", term_average=87.5,
                      overall_position="2nd", out_of_students=28, status="Published"),
        ])
        
        # Primary 6 - Term 1
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kwabena.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="Primary 6", term_average=79.0,
                      overall_position="3rd", out_of_students=22, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=afua.id, academic_term="Term 1",
                      academic_year="2025/2026", class_name="Primary 6", term_average=84.5,
                      overall_position="1st", out_of_students=22, status="Published"),
        ])
        
        # Term 2 Report Cards (2025/2026) - Show performance changes
        # JHS 1 - Term 2
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kofi.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 1", term_average=82.0,
                      overall_position="2nd", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=abena.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 1", term_average=68.5,
                      overall_position="10th", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kwame.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 1", term_average=87.5,
                      overall_position="1st", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=esi.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 1", term_average=75.0,
                      overall_position="4th", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=yaw.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 1", term_average=71.5,
                      overall_position="6th", out_of_students=25, status="Published"),
        ])
        
        # JHS 2 - Term 2
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=akua.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 2", term_average=90.0,
                      overall_position="1st", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kojo.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 2", term_average=78.5,
                      overall_position="3rd", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=ama.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 2", term_average=83.5,
                      overall_position="2nd", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kwesi.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 2", term_average=73.0,
                      overall_position="5th", out_of_students=30, status="Published"),
        ])
        
        # JHS 3 - Term 2
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=efua.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 3", term_average=92.5,
                      overall_position="1st", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kofi_jhs3.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 3", term_average=85.0,
                      overall_position="3rd", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=adwoa.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="JHS 3", term_average=89.0,
                      overall_position="2nd", out_of_students=28, status="Published"),
        ])
        
        # Primary 6 - Term 2
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kwabena.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="Primary 6", term_average=81.5,
                      overall_position="2nd", out_of_students=22, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=afua.id, academic_term="Term 2",
                      academic_year="2025/2026", class_name="Primary 6", term_average=86.0,
                      overall_position="1st", out_of_students=22, status="Published"),
        ])
        
        # Term 3 Report Cards (2025/2026) - Final term performance
        # JHS 1 - Term 3
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kofi.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 1", term_average=80.5,
                      overall_position="3rd", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=abena.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 1", term_average=70.0,
                      overall_position="9th", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kwame.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 1", term_average=89.0,
                      overall_position="1st", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=esi.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 1", term_average=77.5,
                      overall_position="4th", out_of_students=25, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=yaw.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 1", term_average=73.5,
                      overall_position="5th", out_of_students=25, status="Published"),
        ])
        
        # JHS 2 - Term 3
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=akua.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 2", term_average=91.5,
                      overall_position="1st", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kojo.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 2", term_average=80.0,
                      overall_position="3rd", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=ama.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 2", term_average=85.5,
                      overall_position="2nd", out_of_students=30, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kwesi.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 2", term_average=75.5,
                      overall_position="4th", out_of_students=30, status="Published"),
        ])
        
        # JHS 3 - Term 3
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=efua.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 3", term_average=93.0,
                      overall_position="1st", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=kofi_jhs3.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 3", term_average=86.5,
                      overall_position="3rd", out_of_students=28, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=adwoa.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="JHS 3", term_average=90.5,
                      overall_position="2nd", out_of_students=28, status="Published"),
        ])
        
        # Primary 6 - Term 3
        report_cards.extend([
            ReportCard(school_id="CCA-OFK", student_id=kwabena.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="Primary 6", term_average=83.0,
                      overall_position="2nd", out_of_students=22, status="Published"),
            ReportCard(school_id="CCA-OFK", student_id=afua.id, academic_term="Term 3",
                      academic_year="2025/2026", class_name="Primary 6", term_average=87.5,
                      overall_position="1st", out_of_students=22, status="Published"),
        ])
        
        db.session.add_all(report_cards)

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
