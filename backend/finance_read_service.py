from datetime import timedelta


def _payment_amount_details(payment):
    category = payment.payment_category if isinstance(payment.payment_category, dict) else {}
    applied_amount = round(float(category.get("applied_school_fee_amount", payment.amount) or 0), 2)
    display_amount = round(
        float(category.get("gross_amount_paid") or category.get("charged_total_amount") or payment.amount or 0),
        2,
    )
    return category, applied_amount, display_amount


def get_finance_dashboard_payload(
    school_id,
    *,
    now,
    student_model,
    payment_model,
    db,
    serialize_pending_payment,
    group_pending_payments_by_class,
    tuition_balances_fn=None,
):
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_30_days = now - timedelta(days=30)
    last_365_days = now - timedelta(days=365)

    students = student_model.query.filter_by(school_id=school_id).all()
    payments = payment_model.query.filter_by(school_id=school_id, status="Confirmed").all()

    total_collected = sum(payment.amount for payment in payments) if payments else 0
    active_students = [student for student in students if (student.status or "Active").lower() == "active"]
    tuition_balances = tuition_balances_fn(active_students, school_id) if tuition_balances_fn else {}
    outstanding_by_student = {
        student.id: tuition_balances.get(student.id, {}).get("tuition_outstanding_amount", float(student.total_tuition_owed or 0))
        for student in students
    }
    outstanding_balance = round(sum(outstanding_by_student.values()), 2) if students else 0

    daily_revenue = (
        db.session.query(db.func.sum(payment_model.amount))
        .filter(
            payment_model.school_id == school_id,
            payment_model.status == "Confirmed",
            payment_model.date_paid.isnot(None),
            payment_model.date_paid >= start_of_day,
        )
        .scalar()
        or 0
    )

    monthly_revenue = (
        db.session.query(db.func.sum(payment_model.amount))
        .filter(
            payment_model.school_id == school_id,
            payment_model.status == "Confirmed",
            payment_model.date_paid.isnot(None),
            payment_model.date_paid >= last_30_days,
        )
        .scalar()
        or 0
    )

    yearly_revenue = (
        db.session.query(db.func.sum(payment_model.amount))
        .filter(
            payment_model.school_id == school_id,
            payment_model.status == "Confirmed",
            payment_model.date_paid.isnot(None),
            payment_model.date_paid >= last_365_days,
        )
        .scalar()
        or 0
    )

    paid_count = sum(1 for student in students if outstanding_by_student[student.id] <= 0.009)
    unpaid_count = len(students) - paid_count

    recent_payments = (
        payment_model.query.filter_by(school_id=school_id, status="Confirmed")
        .order_by(payment_model.date_paid.desc())
        .limit(10)
        .all()
    )
    recent_transactions = []
    for payment in recent_payments:
        student = student_model.query.get(payment.student_id)
        payment_category, applied_amount, display_amount = _payment_amount_details(payment)
        recent_transactions.append(
            {
                "id": payment.id,
                "date": payment.date_paid.strftime("%Y-%m-%d"),
                "student_name": student.name if student else "Unknown",
                "amount": applied_amount,
                "display_amount": display_amount,
                "applied_amount": applied_amount,
                "type": payment.payment_type,
                "method": payment.method,
                "status": payment.status,
                "reference_id": payment.reference_id,
                "payment_category": payment_category,
            }
        )

    pending_payments = (
        db.session.query(payment_model, student_model)
        .join(student_model)
        .filter(payment_model.school_id == school_id, payment_model.status == "Pending")
        .order_by(student_model.current_class.asc(), payment_model.created_at.asc(), payment_model.id.asc())
        .all()
    )
    pending_list = [
        serialize_pending_payment(row.Payment, row.Student)
        for row in pending_payments
    ]

    return {
        "daily_revenue": daily_revenue,
        "monthly_revenue": monthly_revenue,
        "yearly_revenue": yearly_revenue,
        "total_collected": total_collected,
        "outstanding_balance": outstanding_balance,
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
        "recent_transactions": recent_transactions,
        "pending_payments": pending_list,
        "pending_payments_by_class": group_pending_payments_by_class(pending_list),
    }


def get_transactions_payload(
    school_id,
    *,
    payment_model,
    student_model,
    db,
    to_iso_utc,
):
    payments = (
        db.session.query(payment_model, student_model)
        .join(student_model, payment_model.student_id == student_model.id)
        .filter(payment_model.school_id == school_id)
        .order_by(payment_model.date_paid.desc(), payment_model.created_at.desc(), payment_model.id.desc())
        .all()
    )

    return [
        {
            "id": payment.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "amount": applied_amount,
            "display_amount": display_amount,
            "applied_amount": applied_amount,
            "type": payment.payment_type,
            "method": payment.method,
            "status": payment.status,
            "reference_id": payment.reference_id,
            "payment_category": payment_category,
            "date": (payment.date_paid or payment.created_at).strftime("%Y-%m-%d %H:%M") if (payment.date_paid or payment.created_at) else None,
            "created_at": to_iso_utc(payment.created_at),
            "verified_at": to_iso_utc(payment.verified_at),
        }
        for payment, student in payments
        for payment_category, applied_amount, display_amount in [_payment_amount_details(payment)]
    ]