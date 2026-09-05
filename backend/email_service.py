"""
Email Service for EduPulse
Handles usage reports, billing alerts, and trial notifications
"""

import os

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from backend.api.models import db, School, Student, Payment, User
from backend.subscription_state import get_trial_days_remaining, normalize_utc_datetime
from backend.subscription_features import PRICING
from backend.utils import send_email_notification


def _html_to_plain_text(html_body):
    plain_text = html_body.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    plain_text = plain_text.replace('</p>', '\n\n').replace('</li>', '\n')
    plain_text = plain_text.replace('<li>', '- ')

    in_tag = False
    output = []
    for char in plain_text:
        if char == '<':
            in_tag = True
            continue
        if char == '>':
            in_tag = False
            continue
        if not in_tag:
            output.append(char)

    return '\n'.join(line.rstrip() for line in ''.join(output).splitlines() if line.strip())


def _deliver_html_email(to_email, subject, html_body):
    plain_text = _html_to_plain_text(html_body)
    return send_email_notification(
        to_email,
        subject,
        plain_text,
        html_body=html_body,
    )


def get_school_usage_stats(school_id, month=None, year=None):
    """
    Calculate comprehensive usage statistics for a school for a given month.
    
    Args:
        school_id (int): School ID
        month (int): Month (1-12), defaults to current month
        year (int): Year, defaults to current year
    
    Returns:
        dict: Usage statistics including fees tracked, transactions, students, etc.
    """
    school = School.query.get(school_id)
    if not school:
        return None
    
    # Default to current month/year
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year
    
    # Calculate date range for the month
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month + 1, 1)
    
    # Import optional models locally to avoid circular imports and tolerate
    # deployments that have not enabled every product module.
    try:
        from backend.api.models import FeedingLog, ReportCard
    except ImportError:
        FeedingLog = None
        ReportCard = None
    
    # Query statistics
    
    # 1. Total fees tracked (confirmed payments only)
    total_fees = db.session.query(func.sum(Payment.amount)).filter(
        Payment.school_id == school_id,
        Payment.status == 'Confirmed',
        Payment.date_paid >= month_start,
        Payment.date_paid < month_end
    ).scalar() or 0.0
    
    # 2. Transaction count
    transaction_count = Payment.query.filter(
        Payment.school_id == school_id,
        Payment.date_paid >= month_start,
        Payment.date_paid < month_end
    ).count()
    
    # 3. Report cards generated
    report_cards_generated = 0
    if ReportCard is not None:
        report_cards_generated = ReportCard.query.filter(
            ReportCard.school_id == school_id,
            ReportCard.generated_at >= month_start,
            ReportCard.generated_at < month_end
        ).count()
    
    # 4. Active students
    active_student_count = Student.query.filter(
        Student.school_id == school_id,
        Student.status == 'Active'
    ).count()
    
    # 5. Feeding logs
    feeding_logs_count = 0
    if FeedingLog is not None:
        feeding_logs_count = FeedingLog.query.filter(
            FeedingLog.school_id == school_id,
            FeedingLog.log_date >= month_start,
            FeedingLog.log_date < month_end
        ).count()
    
    # Get plan pricing
    plan = school.subscription_plan or 'Free Tier'
    pricing = PRICING.get(plan, PRICING['Free Tier'])
    
    # Calculate billing metrics
    included_students = int(
        pricing.get('included_students', pricing.get('max_free_students', 0)) or 0
    )
    current_count = school.current_student_count or active_student_count
    usage_percent = (current_count / included_students * 100) if included_students > 0 else 0
    
    # Determine alert status
    if usage_percent >= 100:
        alert_status = "Over Capacity"
        progress_bar_color = "#ef4444"
        alert_color = "#dc2626"
    elif usage_percent >= 80:
        alert_status = "Approaching Capacity Limit"
        progress_bar_color = "#f59e0b"
        alert_color = "#d97706"
    else:
        alert_status = "All Systems Normal"
        progress_bar_color = "#10b981"
        alert_color = "#059669"
    
    # Calculate overage
    overage_count = max(0, current_count - included_students)
    overage_rate = float(pricing.get('per_student_per_term', 0) or 0)
    overage_cost = overage_count * overage_rate
    base_fee = float(pricing.get('base_fee_per_term', 0) or 0)
    total_term_cost = base_fee + overage_cost
    
    # Forecast next month using current active enrollment. Historical student
    # creation timestamps are not consistently available in this schema.
    growth_count = 0
    growth_trend = "Stable this month"
    projected_students = current_count
    projected_overage = max(0, projected_students - included_students)
    projected_cost = base_fee + (projected_overage * overage_rate)
    projected_percent = (projected_students / included_students * 100) if included_students > 0 else 0
    approaching_capacity = projected_percent > 75
    
    # Trial information
    has_active_trial = school.is_trial_active or False
    trial_days_remaining = 0
    trial_expiring_soon = False
    trial_end_date_str = ""
    
    if has_active_trial and school.trial_end_date:
        trial_days_remaining = get_trial_days_remaining(school.trial_end_date, now=now)
        trial_expiring_soon = trial_days_remaining <= 3
        normalized_trial_end = normalize_utc_datetime(school.trial_end_date)
        trial_end_date_str = normalized_trial_end.strftime('%B %d, %Y') if normalized_trial_end else ""
    
    # Get proprietor info
    proprietor = User.query.filter_by(
        school_id=school_id,
        role='proprietor'
    ).first()
    proprietor_name = proprietor.username if proprietor else 'Proprietor'
    
    return {
        # School info
        'school_name': school.name,
        'proprietor_name': proprietor_name,
        'proprietor_email': proprietor.email if proprietor else None,
        'report_month': datetime(year, month, 1).strftime('%B'),
        'report_year': year,
        
        # Value delivered
        'total_fees_tracked': f"{total_fees:,.2f}",
        'transaction_count': transaction_count,
        'report_cards_generated': report_cards_generated,
        'active_student_count': active_student_count,
        'feeding_logs_count': feeding_logs_count,
        
        # Student meter
        'current_student_count': current_count,
        'included_students': included_students,
        'usage_percent': round(usage_percent, 1),
        'progress_bar_color': progress_bar_color,
        'alert_color': alert_color,
        'alert_status': alert_status,
        
        # Billing
        'subscription_plan': plan,
        'base_fee': f"{base_fee:.2f}",
        'has_overage': overage_count > 0,
        'overage_count': overage_count,
        'overage_rate': f"{overage_rate:.2f}",
        'overage_cost': f"{overage_cost:.2f}",
        'total_term_cost': f"{total_term_cost:.2f}",
        
        # Forecast
        'projected_students': projected_students,
        'growth_trend': growth_trend,
        'projected_cost': f"{projected_cost:.2f}",
        'approaching_capacity': approaching_capacity,
        'projected_percent': round(projected_percent, 1),
        
        # Trial
        'has_active_trial': has_active_trial,
        'trial_days_remaining': trial_days_remaining,
        'trial_end_date': trial_end_date_str,
        'trial_expiring_soon': trial_expiring_soon,
        
        # URLs (configure in production)
        'dashboard_url': f"{os.getenv('FRONTEND_URL', 'https://edupulse.com')}/dashboard",
        'upgrade_url': f"{os.getenv('FRONTEND_URL', 'https://edupulse.com')}/subscription",
        'help_center_url': f"{os.getenv('FRONTEND_URL', 'https://edupulse.com')}/help",
        'should_show_upgrade': (overage_count > 0) or approaching_capacity,
        'unsubscribe_url': f"{os.getenv('FRONTEND_URL', 'https://edupulse.com')}/unsubscribe?school={school_id}",
    }


def render_usage_report_html(stats):
    """
    Render the HTML email template with school statistics.
    
    Args:
        stats (dict): Statistics from get_school_usage_stats()
    
    Returns:
        str: Rendered HTML email
    """
    # Simple template rendering (in production, use Jinja2 or similar)
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EduPulse Monthly Usage Report</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc;">
        
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 40px 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0 0 8px 0; font-size: 28px; font-weight: 800;">
                                    📊 Monthly Usage Report
                                </h1>
                                <p style="color: #e0e7ff; margin: 0; font-size: 16px;">
                                    {school_name} · {report_month} {report_year}
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Greeting -->
                        <tr>
                            <td style="padding: 30px 30px 20px 30px;">
                                <p style="color: #1e293b; font-size: 16px; margin: 0;">
                                    Dear <strong>{proprietor_name}</strong>,
                                </p>
                                <p style="color: #475569; font-size: 15px; margin: 16px 0 0 0;">
                                    Here's your monthly summary of how EduPulse is helping you manage <strong>{school_name}</strong>.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Value Delivered -->
                        <tr>
                            <td style="padding: 0 30px 30px 30px;">
                                <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; border: 2px solid #0ea5e9; padding: 24px;">
                                    <tr>
                                        <td>
                                            <h2 style="color: #0369a1; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                                🎯 Value Delivered This Month
                                            </h2>
                                            <table width="100%" cellpadding="8" cellspacing="0">
                                                <tr>
                                                    <td style="color: #334155; font-size: 14px;">💰 Total Fees Tracked</td>
                                                    <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800;">GH₵ {total_fees_tracked}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #334155; font-size: 14px;">📋 Transactions Logged</td>
                                                    <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800;">{transaction_count}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #334155; font-size: 14px;">📊 Report Cards Generated</td>
                                                    <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800;">{report_cards_generated}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color: #334155; font-size: 14px;">👥 Active Students</td>
                                                    <td align="right" style="color: #0f172a; font-size: 18px; font-weight: 800;">{active_student_count}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Billing Preview -->
                        <tr>
                            <td style="padding: 0 30px 30px 30px;">
                                <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%); border-radius: 12px; border: 2px solid #fbbf24; padding: 24px;">
                                    <tr>
                                        <td>
                                            <h2 style="color: #92400e; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
                                                💰 This Term's Billing Preview
                                            </h2>
                                            <table width="100%" cellpadding="6" cellspacing="0">
                                                <tr>
                                                    <td style="color: #78350f; font-size: 14px;">Base Fee ({subscription_plan})</td>
                                                    <td align="right" style="color: #451a03; font-size: 16px; font-weight: 700;">GH₵ {base_fee}</td>
                                                </tr>
                                                <tr style="border-top: 2px solid #fbbf24;">
                                                    <td style="color: #78350f; font-size: 16px; font-weight: 800; padding-top: 12px;">Total This Term</td>
                                                    <td align="right" style="color: #0369a1; font-size: 24px; font-weight: 900; padding-top: 12px;">GH₵ {total_term_cost}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Action Button -->
                        <tr>
                            <td style="padding: 0 30px 30px 30px;" align="center">
                                <a href="{dashboard_url}" style="display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 700; font-size: 15px;">
                                    📊 View Full Dashboard
                                </a>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0;">
                                <p style="margin: 0; color: #64748b; font-size: 13px; text-align: center;">
                                    EduPulse - Empowering Ghanaian Schools<br>
                                    © 2026 EduPulse. All rights reserved.
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
        
    </body>
    </html>
    """
    
    # Replace placeholders with actual values
    return html_template.format(**stats)


def send_usage_report_email(school_id, month=None, year=None):
    """
    Generate and send monthly usage report email to school proprietor.
    
    Args:
        school_id (int): School ID
        month (int): Month (1-12), defaults to current month
        year (int): Year, defaults to current year
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Get usage statistics
    stats = get_school_usage_stats(school_id, month, year)
    if not stats or not stats.get('proprietor_email'):
        return False
    
    html_body = render_usage_report_html(stats)
    subject = f"📊 {stats['school_name']}: Your {stats['report_month']} Usage Report"
    return _deliver_html_email(stats['proprietor_email'], subject, html_body)


def send_capacity_alert_email(school_id):
    """
    Send immediate alert when school reaches 80% capacity.
    
    Args:
        school_id (int): School ID
    
    Returns:
        bool: True if email sent successfully
    """
    school = School.query.get(school_id)
    if not school:
        return False
    
    proprietor = User.query.filter_by(school_id=school_id, role='proprietor').first()
    if not proprietor or not proprietor.email:
        return False
    
    # Get current usage stats
    stats = get_school_usage_stats(school_id)
    if not stats:
        return False
    
    # Simple alert email
    subject = f"⚠️ {stats['school_name']}: Approaching Student Capacity Limit"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #fff3cd;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; border: 2px solid #ffc107;">
            <h2 style="color: #856404;">⚠️ Capacity Alert</h2>
            <p>Dear {stats['proprietor_name']},</p>
            <p>Your school has reached <strong>{stats['usage_percent']}% capacity</strong> ({stats['current_student_count']} / {stats['included_students']} included students).</p>
            <p><strong>Action Recommended:</strong></p>
            <ul>
                <li>Consider upgrading your plan to avoid overage charges</li>
                <li>Review your student list for any inactive profiles</li>
                <li>Contact support for custom pricing options</li>
            </ul>
            <p style="margin-top: 30px;">
                <a href="{stats['dashboard_url']}" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    View Dashboard
                </a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return _deliver_html_email(proprietor.email, subject, html_body)


def send_trial_expiry_reminder(school_id, days_until_expiry):
    """
    Send trial expiry reminder email.
    
    Args:
        school_id (int): School ID
        days_until_expiry (int): Days until trial expires (3 or 7)
    
    Returns:
        bool: True if email sent successfully
    """
    school = School.query.get(school_id)
    if not school or not school.is_trial_active:
        return False
    
    proprietor = User.query.filter_by(school_id=school_id, role='proprietor').first()
    if not proprietor or not proprietor.email:
        return False
    
    stats = get_school_usage_stats(school_id)
    
    subject = f"⏰ {stats['school_name']}: Your Premium Trial Expires in {days_until_expiry} Days"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%); padding: 30px; border-radius: 12px; border: 2px solid #a855f7;">
            <h2 style="color: #6b21a8;">⏰ Premium Trial Expiring Soon</h2>
            <p>Dear {stats['proprietor_name']},</p>
            <p>Your Premium trial expires in <strong>{days_until_expiry} days</strong> on <strong>{stats['trial_end_date']}</strong>.</p>
            
            <h3 style="color: #6b21a8;">This Month You've Enjoyed:</h3>
            <ul>
                <li>✅ Unlimited students & classes</li>
                <li>✅ AI-powered insights</li>
                <li>✅ Advanced analytics</li>
                <li>✅ Custom templates</li>
            </ul>
            
            <p><strong>Don't lose access!</strong> Upgrade now to continue using Premium features.</p>
            
            <p style="margin-top: 30px;">
                <a href="{stats['upgrade_url']}" style="background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                    Upgrade to Premium
                </a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return _deliver_html_email(proprietor.email, subject, html_body)


# Scheduled job functions (to be called by Celery/cron)

def send_all_monthly_reports():
    """
    Send monthly usage reports to all active schools.
    Should be called on the 1st of each month.
    """
    active_schools = School.query.filter(
        School.subscription_plan.in_(['Basic', 'Premium'])
    ).all()
    
    success_count = 0
    fail_count = 0
    
    for school in active_schools:
        if send_usage_report_email(school.id):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"📧 Monthly reports sent: {success_count} success, {fail_count} failed")
    return success_count, fail_count


def check_and_send_capacity_alerts():
    """
    Check all schools and send capacity alerts for those at 80%+.
    Should be called daily.
    """
    from backend.subscription_features import PRICING
    
    alert_count = 0
    
    for school in School.query.all():
        plan = school.subscription_plan or 'Free Tier'
        pricing = PRICING.get(plan, PRICING['Free Tier'])
        included = pricing['included_students']
        current = school.current_student_count or 0
        usage_percent = (current / included * 100) if included > 0 else 0
        
        # Send alert if at 80%+ and hasn't been alerted recently
        if usage_percent >= 80:
            # TODO: Add logic to prevent duplicate alerts within 7 days
            if send_capacity_alert_email(school.id):
                alert_count += 1
    
    print(f"⚠️  Capacity alerts sent: {alert_count}")
    return alert_count


def check_and_send_trial_reminders():
    """
    Check for expiring trials and send reminders.
    Should be called daily.
    """
    now = datetime.now(timezone.utc)
    reminder_count = 0
    
    # Find schools with active trials
    active_trials = School.query.filter(
        School.is_trial_active == True,
        School.trial_end_date.isnot(None)
    ).all()
    
    for school in active_trials:
        days_remaining = get_trial_days_remaining(school.trial_end_date, now=now)
        
        # Send reminders at 7 days, 3 days, and 1 day before expiry
        if days_remaining in [7, 3, 1]:
            if send_trial_expiry_reminder(school.id, days_remaining):
                reminder_count += 1
    
    print(f"⏰ Trial reminders sent: {reminder_count}")
    return reminder_count
