"""
Paystack Integration for EduPulse Payment Processing.
Handles payment initialization, verification, and webhook processing.
"""

import logging
import os
import requests
from datetime import datetime, timedelta, timezone
from backend.api.models import School, Student, add_ledger_entry, db
from backend.email_templates import get_payment_confirmation_email
from backend.subscription_metering import _normalize_dt
from backend.utils import send_email_notification

logger = logging.getLogger(__name__)

# Paystack API Configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackError(Exception):
    """Custom exception for Paystack-related errors."""
    pass


def _should_inject_failpoint(metadata, failpoint_name):
    env_failpoints = {
        item.strip()
        for item in (os.getenv("EDUPULSE_FAILPOINTS") or "").split(",")
        if item.strip()
    }
    metadata_failpoint = ""
    if isinstance(metadata, dict):
        metadata_failpoint = str(metadata.get("__failpoint__") or "").strip()
    return failpoint_name in env_failpoints or metadata_failpoint == failpoint_name


def initialize_payment(email, amount_cents, plan_name, school_id, metadata=None):
    """
    Initialize a payment transaction with Paystack.
    
    Args:
        email: Customer email address
        amount_cents: Amount in pesewas (e.g., 120000 for GH₵ 1,200.00)
        plan_name: Name of the plan being purchased (Basic, Premium)
        school_id: School/Tenant ID
        metadata: Additional metadata to include in transaction
    
    Returns:
        dict: {
            'status': 'success',
            'access_code': str,
            'authorization_url': str,
            'reference': str
        }
    
    Raises:
        PaystackError: If Paystack API call fails
    """
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")
    
    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    # Extract callback URL from metadata if provided
    callback_url = None
    if metadata and 'callback_url' in metadata:
        callback_url = metadata.pop('callback_url')
    
    payload = {
        "email": email,
        "amount": amount_cents,
        "metadata": {
            "school_id": school_id,
            "plan_name": plan_name,
            "transaction_type": "subscription_upgrade",
            **(metadata or {})
        }
    }
    
    # Add callback URL if provided
    if callback_url:
        payload["callback_url"] = callback_url
    
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            json=payload,
            headers=header,
            timeout=10
        )
        
        if response.status_code != 200:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        data = response.json()
        
        if not data.get("status"):
            error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        logger.info(f"Payment initialized for school {school_id}, reference: {data['data']['reference']}")
        
        return {
            'status': 'success',
            'access_code': data['data']['access_code'],
            'authorization_url': data['data']['authorization_url'],
            'reference': data['data']['reference']
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error calling Paystack API: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def charge_authorization(email, amount_cents, authorization_code, metadata=None):
    """Charge a saved/reusable Paystack authorization token."""
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")

    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": amount_cents,
        "authorization_code": authorization_code,
        "metadata": metadata or {},
    }

    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/charge_authorization",
            json=payload,
            headers=header,
            timeout=10,
        )

        if response.status_code not in [200, 201]:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)

        data = response.json()
        if not data.get("status"):
            error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            raise PaystackError(error_msg)

        tx = data.get("data", {})
        tx_status = tx.get("status")
        if tx_status != "success":
            raise PaystackError(f"Charge authorization returned non-success status: {tx_status}")

        logger.info(f"Auto-charge successful: reference={tx.get('reference')}")
        return tx

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error charging authorization with Paystack: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def verify_payment(reference):
    """
    Verify a payment transaction with Paystack.
    
    Args:
        reference: Paystack transaction reference
    
    Returns:
        dict: Transaction details from Paystack including status
    
    Raises:
        PaystackError: If verification fails
    """
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")
    
    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=header,
            timeout=10
        )
        
        if response.status_code != 200:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        data = response.json()
        
        if not data.get("status"):
            error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        logger.info(f"Payment verified, reference: {reference}, status: {data['data']['status']}")
        return data['data']
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error verifying payment with Paystack: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def process_payment_confirmation(school_id, plan_name, amount_paid_cedis, reference=None, metadata=None):
    """
    Process a confirmed payment and update school subscription.
    Also sends payment confirmation email.
    
    Args:
        school_id: School/Tenant ID
        plan_name: Plan name (Basic, Premium)
        amount_paid_cedis: Amount paid in Ghana Cedis
        reference: Payment reference
        metadata: Additional payment metadata (billing_period, student_count, etc.)
    
    Returns:
        dict: Update result with payment details
    """
    try:
        school = School.query.get(school_id)
        if not school:
            raise PaystackError(f"School {school_id} not found")
        
        # Extract metadata
        meta = metadata or {}
        billing_period = meta.get('billing_period', 'term')
        default_student_count = Student.query.filter_by(school_id=school.id).count()
        student_count = int(meta.get('student_count', default_student_count))
        terms = int(meta.get('terms', 1))
        proration_data = meta.get('proration_data') if isinstance(meta.get('proration_data'), dict) else {}
        
        # Update school subscription
        old_plan = school.subscription_plan
        school.subscription_plan = plan_name
        school.subscription_status = "Active"
        
        # Set next billing date based on billing period
        # Termly billing: approximately 4 months per term (3 terms per year)
        days_per_term = 120  # ~4 months
        days_to_add = days_per_term * terms
        next_billing_override = _normalize_dt(
            datetime.fromisoformat(proration_data.get('next_billing_date_override'))
        ) if proration_data.get('next_billing_date_override') else None

        if next_billing_override:
            school.next_billing_date = next_billing_override
        else:
            school.next_billing_date = datetime.now(timezone.utc) + timedelta(days=days_to_add)
        
        # Clear trial if it exists
        school.trial_plan = None
        school.trial_end_date = None
        school.is_trial_active = False
        
        # Record subscription payment in ledger
        tx_ref = reference or f"SUB-{school_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        add_ledger_entry(
            school_id=school_id,
            tx_type="subscription",
            tx_ref=tx_ref,
            amount=float(amount_paid_cedis),
            actor_id=None,
            student_id=None,
            source="paystack",
            metadata={
                "plan_name": plan_name,
                "previous_plan": old_plan,
                "billing_cycle": f"{terms} Term(s)" if billing_period == 'term' else f"Annual ({terms} Terms)",
                "student_count": student_count,
                "billing_period": billing_period,
                "proration_data": proration_data,
            },
        )

        if _should_inject_failpoint(meta, "subscription_payment_before_commit"):
            db.session.rollback()
            raise PaystackError("Injected failpoint: subscription_payment_before_commit")

        db.session.commit()
        
        logger.info(f"School {school_id} subscription updated: {old_plan} → {plan_name}, {terms} term(s), GH₵ {amount_paid_cedis}")
        
        return {
            'status': 'success',
            'plan_name': plan_name,
            'amount': amount_paid_cedis,
            'reference': tx_ref,
            'next_billing_date': school.next_billing_date.isoformat() if school.next_billing_date else None,
            'student_count': student_count,
            'billing_period': billing_period
        }
        
        # Send confirmation email
        proprietor = school.users.filter_by(role='proprietor').first()
        if proprietor and proprietor.email:
            try:
                invoice_number = f"INV-{school_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                payment_date = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M %Z")
                
                # Basic feature set
                features = {
                    'Basic': "✓ Up to 200 students\n✓ Lesson notes with basic AI analysis\n✓ Standard reporting",
                    'Premium': "✓ Unlimited students\n✓ Full AI-powered lesson notes\n✓ AI-generated narratives\n✓ Advanced analytics"
                }
                
                payment_subject, payment_body = get_payment_confirmation_email(
                    school_name=school.name,
                    invoice_number=invoice_number,
                    payment_date=payment_date,
                    amount_paid=f"₵{amount_paid_naira}",
                    payment_method="Paystack",
                    payment_status="Completed",
                    plan_name=plan_name,
                    billing_cycle="Monthly",
                    subtotal=f"₵{amount_paid_naira}",
                    tax="₵0.00",
                    total_amount=f"₵{amount_paid_naira}",
                    access_details=features.get(plan_name, ""),
                    billing_email=proprietor.email,
                    billing_phone="",
                    dashboard_url=os.getenv("FRONTEND_URL", "http://localhost:5173/dashboard"),
                    receipt_url="",
                    renewal_date=(datetime.now(timezone.utc) + timedelta(days=30)).strftime("%B %d, %Y")
                )
                
                send_email_notification(
                    to_email=proprietor.email,
                    subject=payment_subject,
                    body=payment_body
                )
                logger.info(f"Payment confirmation email sent to {proprietor.email}")
                
            except Exception as e:
                logger.error(f"Failed to send payment confirmation email: {str(e)}")
        
        return {
            'status': 'success',
            'school_id': school_id,
            'plan': plan_name,
            'message': f'Subscription upgraded to {plan_name}'
        }
        
    except Exception as e:
        logger.error(f"Error processing payment confirmation for school {school_id}: {str(e)}")
        db.session.rollback()
        raise PaystackError(f"Error processing payment: {str(e)}")


def create_paystack_customer(email, first_name="", last_name=""):
    """
    Create a customer record in Paystack (optional - for future features).
    
    Args:
        email: Customer email
        first_name: Customer first name
        last_name: Customer last name
    
    Returns:
        dict: Customer data from Paystack
    
    Raises:
        PaystackError: If creation fails
    """
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")
    
    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name
    }
    
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/customer",
            json=payload,
            headers=header,
            timeout=10
        )
        
        if response.status_code not in [200, 201]:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        data = response.json()
        logger.info(f"Paystack customer created/updated for {email}")
        return data.get('data', {})
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error creating Paystack customer: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def create_subscription_plan(plan_name, amount_cents, interval="monthly"):
    """
    Create a subscription plan in Paystack for recurring billing.
    
    For Ghana schools, we use termly billing (3 times/year).
    
    Args:
        plan_name: Name of the plan (e.g., "EduPulse Basic")
        amount_cents: Amount per billing cycle in pesewas (₵1 = 100 pesewas)
        interval: Billing interval ('monthly', 'quarterly', 'annually')
    
    Returns:
        dict: Plan data from Paystack including plan_code
    
    Raises:
        PaystackError: If plan creation fails
    """
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")
    
    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": plan_name,
        "amount": amount_cents,
        "interval": interval,
        "currency": "GHS"
    }
    
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/plan",
            json=payload,
            headers=header,
            timeout=10
        )
        
        if response.status_code not in [200, 201]:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        data = response.json()
        
        if not data.get("status"):
            error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        logger.info(f"Created subscription plan: {plan_name}, code: {data['data']['plan_code']}")
        return data['data']
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error creating subscription plan: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def subscribe_customer(customer_email, plan_code, authorization_code=None):
    """
    Subscribe a customer to a recurring subscription plan.
    
    Args:
        customer_email: Customer email address
        plan_code: Paystack plan code (from create_subscription_plan)
        authorization_code: Payment authorization code (optional, from previous payment)
    
    Returns:
        dict: Subscription data from Paystack
    
    Raises:
        PaystackError: If subscription creation fails
    """
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY not configured")
    
    header = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "customer": customer_email,
        "plan": plan_code
    }
    
    if authorization_code:
        payload["authorization"] = authorization_code
    
    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/subscription",
            json=payload,
            headers=header,
            timeout=10
        )
        
        if response.status_code not in [200, 201]:
            error_msg = f"Paystack API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        data = response.json()
        
        if not data.get("status"):
            error_msg = f"Paystack error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            raise PaystackError(error_msg)
        
        logger.info(f"Customer {customer_email} subscribed to plan {plan_code}")
        return data['data']
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error subscribing customer: {str(e)}"
        logger.error(error_msg)
        raise PaystackError(error_msg)


def initialize_termly_payment(email, plan_name, school_id, num_students, academic_term_id=None):
    """
    Initialize a termly subscription payment (Ghana-specific).
    
    Amount is calculated using hybrid pricing:
    base_fee_per_term + (max(0, num_students - included_students) × per_student_rate)
    Convenience fee is always 0 for subscription billing.
    
    Args:
        email: School proprietor email
        plan_name: Plan name (Basic, Premium)
        school_id: School ID
        num_students: Current enrollment count
        academic_term_id: Optional term ID for tracking
    
    Returns:
        dict: Payment authorization data from Paystack
    
    Raises:
        PaystackError: If initialization fails
    """
    from backend.subscription_features import get_term_cost_breakdown
    
    # Calculate term cost based on enrollment
    breakdown = get_term_cost_breakdown(plan_name, num_students)
    term_cost = breakdown["total"]
    amount_cents = int(term_cost * 100)  # Convert GHS to pesewas
    
    metadata = {
        "school_id": school_id,
        "plan_name": plan_name,
        "num_students": num_students,
        "billing_type": "termly",
        "base_fee": breakdown["base_fee"],
        "included_students": breakdown["included_students"],
        "billable_students": breakdown["billable_students"],
        "per_student_rate": breakdown["per_student_rate"],
        "student_overage_cost": breakdown["student_overage_cost"],
        "convenience_fee": 0,
        "term_cost": term_cost,
    }
    
    if academic_term_id:
        metadata["academic_term_id"] = academic_term_id
    
    result = initialize_payment(
        email=email,
        amount_cents=amount_cents,
        plan_name=plan_name,
        school_id=school_id,
        metadata=metadata
    )

    result.update({
        "term_cost": round(term_cost, 2),
        "base_fee": breakdown["base_fee"],
        "included_students": breakdown["included_students"],
        "billable_students": breakdown["billable_students"],
        "student_overage_cost": breakdown["student_overage_cost"],
        "convenience_fee": 0,
    })
    return result
