"""Email template loader and renderer for EduPulse."""

import os
import logging

logger = logging.getLogger(__name__)


def load_email_template(template_name):
    """Load an email template from the templates directory.
    
    Args:
        template_name: Name of the template file (e.g., 'welcome_email')
        
    Returns:
        Tuple of (subject, body) with first line as subject if present
    """
    template_path = os.path.join(
        os.path.dirname(__file__),
        'email_templates',
        f'{template_name}.txt'
    )
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
            # Extract subject line (starts with "Subject: ")
            lines = content.split('\n')
            subject = None
            body_start = 0
            
            if lines and lines[0].startswith('Subject: '):
                subject = lines[0].replace('Subject: ', '').strip()
                body_start = 1
                # Skip empty lines after subject
                while body_start < len(lines) and lines[body_start].strip() == '':
                    body_start += 1
            
            body = '\n'.join(lines[body_start:]).strip()
            
            return subject, body
    except FileNotFoundError:
        logger.error(f"Email template not found: {template_name}")
        return None, None
    except Exception as e:
        logger.error(f"Error loading email template {template_name}: {str(e)}")
        return None, None


def render_email_template(template_name, variables):
    """Load and render an email template with variables.
    
    Args:
        template_name: Name of the template file
        variables: Dictionary of variables to replace in template
        
    Returns:
        Tuple of (subject, body) with variables substituted
    """
    subject, body = load_email_template(template_name)
    
    if subject is None or body is None:
        return None, None
    
    # Replace variables in format {{variable_name}}
    for key, value in variables.items():
        placeholder = f'{{{{{key}}}}}'
        subject = subject.replace(placeholder, str(value) if value is not None else '')
        body = body.replace(placeholder, str(value) if value is not None else '')
    
    return subject, body


def get_welcome_email(username, school_name, school_id, login_url, subscription_plan):
    """Generate welcome email for new school registration."""
    variables = {
        'username': username,
        'school_name': school_name,
        'school_id': school_id,
        'login_url': login_url,
        'subscription_plan': subscription_plan,
    }
    return render_email_template('welcome_email', variables)


def get_password_reset_email(user_name, reset_link):
    """Generate password reset email."""
    variables = {
        'user_name': user_name,
        'reset_link': reset_link,
    }
    return render_email_template('password_reset_email', variables)


def get_staff_welcome_email(staff_name, school_name, username, temporary_password,
                           assigned_role, login_url, expiry_days=30,
                           role_description=None, role_permissions=None,
                           headmaster_name=None, headmaster_email=None, email=None,
                           school_id=None, support_contact_name=None,
                           support_contact_email=None, support_contact_phone=None):
    """Generate welcome email for new staff member."""
    variables = {
        'staff_name': staff_name,
        'username': username,
        'email': email or '',
        'temporary_password': temporary_password,
        'role': assigned_role,
        'assigned_role': assigned_role,
        'school_name': school_name,
        'login_url': login_url,
        'expiry_days': expiry_days,
        'role_description': role_description or '',
        'role_permissions': role_permissions or '',
        'headmaster_name': headmaster_name or '',
        'headmaster_email': headmaster_email or '',
        'school_id': school_id or '',
        'support_contact_name': support_contact_name or headmaster_name or '',
        'support_contact_email': support_contact_email or headmaster_email or '',
        'support_contact_phone': support_contact_phone or '',
    }
    return render_email_template('staff_welcome_email', variables)


def get_two_factor_email(user_name, code):
    """Generate 2FA verification email."""
    variables = {
        'user_name': user_name,
        'code': code,
    }
    return render_email_template('two_factor_email', variables)


def get_lesson_note_submission_email(teacher_name, class_name, subject_name, lesson_dates,
                                     class_size, submit_to, approver_name, approver_role,
                                     completeness_score, pedagogical_score, content_quality_score,
                                     overall_score, ai_feedback, school_name, 
                                     headmaster_name, headmaster_email):
    """Generate lesson note submission confirmation email."""
    variables = {
        'teacher_name': teacher_name,
        'class_name': class_name,
        'subject_name': subject_name,
        'lesson_dates': lesson_dates,
        'class_size': class_size,
        'submit_to': submit_to,
        'approver_name': approver_name,
        'approver_role': approver_role,
        'completeness_score': completeness_score,
        'pedagogical_score': pedagogical_score,
        'content_quality_score': content_quality_score,
        'overall_score': overall_score,
        'ai_feedback': ai_feedback,
        'school_name': school_name,
        'headmaster_name': headmaster_name,
        'headmaster_email': headmaster_email,
    }
    return render_email_template('lesson_note_submission_email', variables)

def get_subscription_confirmation_email(school_name, plan_name, price, billing_cycle, 
                                       start_date, billing_email, features_list, 
                                       usage_limits, included_services, login_url,
                                       support_email, support_phone, billing_management_url,
                                       next_billing_date=None):
    """Generate subscription confirmation email for new plans."""
    variables = {
        'school_name': school_name,
        'plan_name': plan_name,
        'price': price,
        'billing_cycle': billing_cycle,
        'start_date': start_date,
        'billing_email': billing_email,
        'features_list': features_list,
        'usage_limits': usage_limits,
        'included_services': included_services,
        'login_url': login_url,
        'support_email': support_email,
        'support_phone': support_phone,
        'billing_management_url': billing_management_url,
        'next_billing_date': next_billing_date or 'TBD',
    }
    return render_email_template('subscription_confirmation_email', variables)


def get_subscription_upgrade_email(school_name, previous_plan, plan_name, upgrade_date,
                                  price, billing_cycle, new_features, removed_limitations,
                                  new_usage_limits, new_resources, feature_highlights,
                                  support_email, support_phone, next_billing_date,
                                  invoice_url, prorated_credit=None, prorated_amount=None):
    """Generate subscription upgrade confirmation email."""
    variables = {
        'school_name': school_name,
        'previous_plan': previous_plan,
        'plan_name': plan_name,
        'upgrade_date': upgrade_date,
        'price': price,
        'billing_cycle': billing_cycle,
        'new_features': new_features,
        'removed_limitations': removed_limitations,
        'new_usage_limits': new_usage_limits,
        'new_resources': new_resources,
        'feature_highlights': feature_highlights,
        'support_email': support_email,
        'support_phone': support_phone,
        'next_billing_date': next_billing_date,
        'invoice_url': invoice_url,
        'prorated_credit': prorated_credit or '',
        'prorated_amount': prorated_amount or '',
    }
    return render_email_template('subscription_upgrade_email', variables)


def get_payment_confirmation_email(school_name, invoice_number, payment_date, amount_paid,
                                  payment_method, payment_status, plan_name, billing_cycle,
                                  subtotal, tax, total_amount, access_details, 
                                  billing_email, billing_phone, dashboard_url, receipt_url,
                                  renewal_date=None):
    """Generate payment/invoice confirmation email."""
    variables = {
        'school_name': school_name,
        'invoice_number': invoice_number,
        'payment_date': payment_date,
        'amount_paid': amount_paid,
        'payment_method': payment_method,
        'payment_status': payment_status,
        'plan_name': plan_name,
        'billing_cycle': billing_cycle,
        'subtotal': subtotal,
        'tax': tax,
        'total_amount': total_amount,
        'access_details': access_details,
        'billing_email': billing_email,
        'billing_phone': billing_phone,
        'dashboard_url': dashboard_url,
        'receipt_url': receipt_url,
        'renewal_date': renewal_date or 'TBD',
    }
    return render_email_template('payment_confirmation_email', variables)


def get_trial_confirmation_email(school_name, username, login_url, trial_end_date):
    """Generate trial confirmation email for new registrations."""
    variables = {
        'school_name': school_name,
        'username': username,
        'login_url': login_url,
        'trial_end_date': trial_end_date.strftime('%B %d, %Y') if hasattr(trial_end_date, 'strftime') else trial_end_date,
    }
    return render_email_template('trial_confirmation_email', variables)


def get_trial_expiry_email(school_name, login_url):
    """Generate trial expiry notification email."""
    variables = {
        'school_name': school_name,
        'login_url': login_url,
    }
    return render_email_template('trial_expiry_email', variables)


def get_trial_reminder_email(school_name, login_url, trial_end_date, days_remaining):
    """Generate trial reminder email for expiring trials."""
    variables = {
        'school_name': school_name,
        'login_url': login_url,
        'trial_end_date': trial_end_date.strftime('%B %d, %Y') if hasattr(trial_end_date, 'strftime') else trial_end_date,
        'days_remaining': days_remaining,
    }
    return render_email_template('trial_reminder_email', variables)


def get_paystack_payment_link_email(school_name, plan_name, amount, billing_cycle, features_list,
                                    payment_link, trial_days_remaining, billing_email):
    """Generate Paystack payment link email for plan upgrades."""
    variables = {
        'school_name': school_name,
        'plan_name': plan_name,
        'amount': amount,
        'billing_cycle': billing_cycle,
        'features_list': features_list,
        'payment_link': payment_link,
        'trial_days_remaining': trial_days_remaining,
        'billing_email': billing_email,
    }
    return render_email_template('paystack_payment_link_email', variables)


def get_term_billing_notification_email(school_name, proprietor_name, term_name, academic_year,
                                        invoice_number, billing_date, due_date, plan_name,
                                        num_students, rate_per_student, term_cost,
                                        term_start_date, vacation_date, reopening_date,
                                        payment_link, features_list, support_email, support_phone,
                                        dashboard_url, base_fee=None, included_students=None,
                                        billable_students=None, student_overage_cost=None):
    """Generate term activation billing notification email with hybrid pricing breakdown."""
    variables = {
        'school_name': school_name,
        'proprietor_name': proprietor_name,
        'term_name': term_name,
        'academic_year': academic_year,
        'invoice_number': invoice_number,
        'billing_date': billing_date,
        'due_date': due_date,
        'plan_name': plan_name,
        'num_students': num_students,
        'rate_per_student': rate_per_student,
        'term_cost': term_cost,
        'term_start_date': term_start_date,
        'vacation_date': vacation_date,
        'reopening_date': reopening_date,
        'payment_link': payment_link,
        'features_list': features_list,
        'support_email': support_email,
        'support_phone': support_phone,
        'dashboard_url': dashboard_url,
        'base_fee': base_fee,
        'included_students': included_students,
        'billable_students': billable_students,
        'student_overage_cost': student_overage_cost,
    }
    return render_email_template('term_billing_notification', variables)


def get_parent_admission_status_email(
    guardian_name,
    school_name,
    student_name,
    application_code,
    status_token,
    status,
    summary,
    status_url,
    next_step,
    payment_url=None,
):
    """Generate parent admission status notification email."""
    variables = {
        'guardian_name': guardian_name,
        'school_name': school_name,
        'student_name': student_name,
        'application_code': application_code,
        'status_token': status_token,
        'status': status,
        'summary': summary,
        'status_url': status_url,
        'next_step': next_step,
        'payment_url': payment_url or '',
    }
    return render_email_template('parent_admission_status_email', variables)