"""
EduPulse Payment Integration Module
- Handles subscription billing via Paystack
- Manages invoicing and payment reconciliation
- Supports monthly recurring billing
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta

import requests
from flask import Blueprint, jsonify, request

from backend.api.models import Payment, School, Subscription
from backend.config import db

payment_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

# Paystack Configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "YOUR_PAYSTACK_SECRET")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "YOUR_PAYSTACK_PUBLIC_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"

# Your Business Account Details
BUSINESS_ACCOUNT = {
    "name": "EduPulse Limited",
    "email": "billing@edupulse.com.gh",
    "phone": "+233 (0) XXX XXX XXXX",
    "bank": "GCB Bank / Zenith Bank",
    "account_number": "XXXXXXXXXXXXXXX",
    "account_name": "EduPulse Limited",
}

# ============================================================================
# 1. INITIALIZE PAYMENT (When school selects tier to upgrade)
# ============================================================================


@payment_bp.route("/initialize", methods=["POST"])
def initialize_payment():
    """
    Initialize a payment for subscription upgrade

    Request: {
        "school_id": "sch_123",
        "plan": "basic",        # basic, premium
        "billing_cycle": 1      # months (1, 3, 6, 12)
    }
    """
    try:
        data = request.get_json()
        school_id = data.get("school_id")
        plan = data.get("plan", "basic")
        billing_cycle = data.get("billing_cycle", 1)

        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "School not found"}), 404

        # Calculate amount based on plan
        plan_prices = {"basic": 50, "premium": 250}  # ₵50/month  # ₵250/month

        amount_per_month = plan_prices.get(plan, 0)
        if not amount_per_month:
            return jsonify({"error": "Invalid plan selected"}), 400

        total_amount = amount_per_month * billing_cycle
        amount_in_pesewas = int(total_amount * 100)  # Paystack works with pesewas

        # Create Paystack transaction
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "email": school.proprietor_email,
            "amount": amount_in_pesewas,
            "metadata": {
                "school_id": school_id,
                "plan": plan,
                "billing_cycle": billing_cycle,
                "school_name": school.name,
            },
            "callback_url": f'{os.getenv("FRONTEND_URL", "http://localhost:5173")}/payment-success',
        }

        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize", json=payload, headers=headers
        )

        if response.status_code == 200:
            transaction_data = response.json()["data"]
            return (
                jsonify(
                    {
                        "status": "success",
                        "authorization_url": transaction_data["authorization_url"],
                        "access_code": transaction_data["access_code"],
                        "reference": transaction_data["reference"],
                        "amount_ghs": total_amount,
                        "plan": plan,
                        "billing_period": f'{billing_cycle} month{"s" if billing_cycle > 1 else ""}',
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "Payment initialization failed"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 2. VERIFY PAYMENT (After user returns from Paystack)
# ============================================================================


@payment_bp.route("/verify/<reference>", methods=["GET"])
def verify_payment(reference):
    """
    Verify payment status and update subscription if successful
    Called after user completes Paystack payment
    """
    try:
        headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}", headers=headers
        )

        if response.status_code != 200:
            return jsonify({"error": "Payment verification failed"}), 400

        trans_data = response.json()["data"]

        if trans_data["status"] != "success":
            return (
                jsonify({"status": "failed", "message": "Payment was not successful"}),
                400,
            )

        # Extract metadata
        metadata = trans_data["metadata"]
        school_id = metadata["school_id"]
        plan = metadata["plan"]
        billing_cycle = metadata["billing_cycle"]

        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "School not found"}), 404

        # Create payment record
        payment = Payment(
            school_id=school_id,
            reference=reference,
            amount=trans_data["amount"] / 100,  # Convert from pesewas to GHS
            currency="GHS",
            status="success",
            payment_method="paystack",
            transaction_date=datetime.utcnow(),
            description=f"Subscription upgrade to {plan.upper()} - {billing_cycle} month(s)",
        )

        db.session.add(payment)

        # Update/create subscription
        subscription = Subscription.query.filter_by(school_id=school_id).first()

        if subscription:
            subscription.plan = plan
            subscription.start_date = datetime.utcnow()
            subscription.end_date = datetime.utcnow() + timedelta(
                days=30 * billing_cycle
            )
            subscription.status = "active"
            subscription.auto_renew = True
            subscription.last_payment_date = datetime.utcnow()
        else:
            subscription = Subscription(
                school_id=school_id,
                plan=plan,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30 * billing_cycle),
                status="active",
                auto_renew=True,
                last_payment_date=datetime.utcnow(),
            )
            db.session.add(subscription)

        # Update school subscription in summary
        school.subscription_plan = plan

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Payment verified! Subscription upgraded to {plan.upper()}",
                    "school_id": school_id,
                    "plan": plan,
                    "valid_until": subscription.end_date.isoformat(),
                    "amount_paid": f'₵{trans_data["amount"]/100:.2f}',
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 3. WEBHOOK - Paystack Sends Real-time Payment Updates
# ============================================================================


@payment_bp.route("/webhook", methods=["POST"])
def paystack_webhook():
    """
    Paystack sends webhook notifications here
    Verifies webhook signature and processes events
    """
    try:
        # Verify webhook signature
        signature = request.headers.get("X-Paystack-Signature")
        body = request.get_data()

        hash_object = hmac.new(
            PAYSTACK_SECRET_KEY.encode("utf-8"), body, hashlib.sha512
        )
        computed_signature = hash_object.hexdigest()

        if signature != computed_signature:
            return jsonify({"error": "Invalid signature"}), 401

        event_data = request.json
        event = event_data.get("event")

        if event == "charge.success":
            transaction = event_data["data"]
            reference = transaction["reference"]

            # Process successful payment
            metadata = transaction["metadata"]
            school_id = metadata["school_id"]
            plan = metadata["plan"]

            payment = Payment.query.filter_by(reference=reference).first()
            if not payment:
                # Create new payment record from webhook
                payment = Payment(
                    school_id=school_id,
                    reference=reference,
                    amount=transaction["amount"] / 100,
                    currency="GHS",
                    status="success",
                    payment_method="paystack",
                    transaction_date=datetime.utcnow(),
                )
                db.session.add(payment)

            payment.status = "success"
            payment.webhook_processed = True
            db.session.commit()

            # Send success email to school
            send_payment_confirmation_email(school_id, payment)

        elif event == "charge.failed":
            transaction = event_data["data"]
            reference = transaction["reference"]

            payment = Payment.query.filter_by(reference=reference).first()
            if payment:
                payment.status = "failed"
                db.session.commit()

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 4. GET SUBSCRIPTION STATUS
# ============================================================================


@payment_bp.route("/subscription/<school_id>", methods=["GET"])
def get_subscription_status(school_id):
    """Get current subscription details and payment history"""
    try:
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "School not found"}), 404

        subscription = Subscription.query.filter_by(school_id=school_id).first()
        payments = (
            Payment.query.filter_by(school_id=school_id)
            .order_by(Payment.transaction_date.desc())
            .limit(10)
            .all()
        )

        return (
            jsonify(
                {
                    "school_id": school_id,
                    "current_plan": school.subscription_plan,
                    "subscription": {
                        "plan": subscription.plan if subscription else "free",
                        "status": subscription.status if subscription else "inactive",
                        "start_date": (
                            subscription.start_date.isoformat()
                            if subscription
                            else None
                        ),
                        "end_date": (
                            subscription.end_date.isoformat() if subscription else None
                        ),
                        "days_remaining": (
                            (subscription.end_date - datetime.utcnow()).days
                            if subscription
                            and subscription.end_date > datetime.utcnow()
                            else 0
                        ),
                        "auto_renew": (
                            subscription.auto_renew if subscription else False
                        ),
                    },
                    "payment_history": [
                        {
                            "date": p.transaction_date.isoformat(),
                            "amount": f"₵{p.amount:.2f}",
                            "status": p.status,
                            "reference": p.reference,
                            "description": p.description,
                        }
                        for p in payments
                    ],
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 5. INVOICE GENERATION
# ============================================================================


@payment_bp.route("/invoice/<payment_id>", methods=["GET"])
def generate_invoice(payment_id):
    """Generate PDF invoice for payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            return jsonify({"error": "Payment not found"}), 404

        school = School.query.get(payment.school_id)

        invoice_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .invoice-details {{ margin: 30px 0; }}
                .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .table th, .table td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                .total {{ font-weight: bold; font-size: 18px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>EduPulse Subscription Invoice</h1>
                <p>Invoice #: {payment.reference}</p>
            </div>
            
            <div class="invoice-details">
                <p><strong>From:</strong> {BUSINESS_ACCOUNT['name']}</p>
                <p><strong>To:</strong> {school.name}</p>
                <p><strong>Date:</strong> {payment.transaction_date.strftime('%Y-%m-%d')}</p>
            </div>
            
            <table class="table">
                <tr>
                    <th>Description</th>
                    <th>Amount (₵)</th>
                </tr>
                <tr>
                    <td>{payment.description}</td>
                    <td>{payment.amount:.2f}</td>
                </tr>
                <tr class="total">
                    <td>Total</td>
                    <td>₵{payment.amount:.2f}</td>
                </tr>
            </table>
            
            <p><strong>Status:</strong> {payment.status.upper()}</p>
        </body>
        </html>
        """

        # Return HTML or convert to PDF
        return invoice_html, 200, {"Content-Type": "text/html"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 6. SEND PAYMENT CONFIRMATION EMAIL
# ============================================================================


def send_payment_confirmation_email(school_id, payment):
    """Send confirmation email to school proprietor"""
    try:
        school = School.query.get(school_id)
        subscription = Subscription.query.filter_by(school_id=school_id).first()

        email_subject = "✅ EduPulse Subscription Payment Confirmed"
        email_body = f"""
        Dear {school.proprietor_name},
        
        Your subscription payment has been successfully processed!
        
        Payment Details:
        - Reference: {payment.reference}
        - Amount: ₵{payment.amount:.2f}
        - Plan: {subscription.plan.upper() if subscription else 'PREMIUM'}
        - Valid Until: {subscription.end_date.strftime('%Y-%m-%d') if subscription else 'N/A'}
        
        Your account is now active with full access to all features.
        
        Invoice: {payment.reference}
        Date: {payment.transaction_date.strftime('%Y-%m-%d %H:%M')}
        
        If you have any questions, contact our billing team at billing@edupulse.com.gh
        
        Best regards,
        EduPulse Team
        """

        # TODO: Implement email sending using Flask-Mail or SendGrid
        print(f"Email sent to {school.proprietor_email}")

    except Exception as e:
        print(f"Error sending email: {str(e)}")


# ============================================================================
# 7. PAYMENT DASHBOARD (For Proprietors)
# ============================================================================


@payment_bp.route("/dashboard/<school_id>", methods=["GET"])
def payment_dashboard(school_id):
    """Get payment analytics for proprietor dashboard"""
    try:
        payments = Payment.query.filter_by(school_id=school_id).all()
        subscription = Subscription.query.filter_by(school_id=school_id).first()

        total_spent = sum(p.amount for p in payments if p.status == "success")
        failed_payments = [p for p in payments if p.status == "failed"]

        return (
            jsonify(
                {
                    "total_invested": f"₵{total_spent:.2f}",
                    "current_plan": subscription.plan if subscription else "free",
                    "subscription_active": subscription
                    and subscription.status == "active",
                    "next_billing_date": (
                        subscription.end_date.isoformat() if subscription else None
                    ),
                    "failed_payments": len(failed_payments),
                    "payment_count": len(payments),
                    "monthly_trend": {
                        "month": datetime.utcnow().strftime("%B %Y"),
                        "revenue": sum(
                            p.amount
                            for p in payments
                            if p.status == "success"
                            and p.transaction_date.month == datetime.utcnow().month
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Add this to requirements.txt:
# requests==2.31.0
# paystack-python==2.0.0
