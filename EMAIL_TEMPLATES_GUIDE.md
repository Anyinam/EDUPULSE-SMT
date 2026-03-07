# EduPulse Email Template System

This document explains the email template architecture and how to customize emails for your school.

## Overview

EduPulse uses a flexible email template system that separates email content from code. All email templates are stored as text files with placeholder variables that get replaced at runtime.

## Template Location

📁 **Location:** `backend/email_templates/`

Available templates:
- `welcome_email.txt` - School registration welcome email
- `password_reset_email.txt` - Password reset link email
- `staff_welcome_email.txt` - Welcome email for new staff members
- `two_factor_email.txt` - 2FA verification codes
- `lesson_note_submission_email.txt` - Lesson note submission confirmation
- `subscription_confirmation_email.txt` - Subscription plan confirmation
- `subscription_upgrade_email.txt` - Subscription upgrade confirmation
- `payment_confirmation_email.txt` - Payment/invoice confirmation

## Template Format

Each template starts with a `Subject:` line followed by the email body:

```
Subject: Email Subject Line

Email body content here...

You can use {{variable_name}} to insert dynamic values.
```

### Example Template:

```
Subject: Welcome to {{school_name}}

Dear {{username}},

Welcome to EduPulse!

Your school has been created:
• Organization ID: {{school_id}}
• Login: {{login_url}}

Best regards,
The EduPulse Team
```

## Available Placeholders by Template

### Welcome Email (`welcome_email.txt`)
- `{{username}}` - Proprietor username
- `{{school_name}}` - School name
- `{{school_id}}` - Organization ID
- `{{login_url}}` - Frontend login URL
- `{{subscription_plan}}` - Current subscription plan

### Password Reset Email (`password_reset_email.txt`)
- `{{user_name}}` - Username
- `{{reset_link}}` - Password reset link (expires in 1 hour)

### Staff Welcome Email (`staff_welcome_email.txt`)
- `{{staff_name}}` - Staff member name
- `{{username}}` - Staff username
- `{{email}}` - Staff email
- `{{role}}` - Staff role (teacher, homeroom, headmaster, finance)
- `{{school_name}}` - School name
- `{{login_url}}` - Frontend login URL
- `{{role_description}}` - Description of role responsibilities
- `{{role_permissions}}` - List of permissions for the role
- `{{headmaster_name}}` - Headmaster name
- `{{headmaster_email}}` - Headmaster email

### Two-Factor Email (`two_factor_email.txt`)
- `{{user_name}}` - Username
- `{{code}}` - 6-digit verification code

### Lesson Note Submission Email (`lesson_note_submission_email.txt`)
- `{{teacher_name}}` - Teacher name
- `{{class_name}}` - Class name (e.g., JHS 1)
- `{{subject_name}}` - Subject name
- `{{lesson_date}}` - Date of lesson
- `{{submit_to}}` - Person who reviewed it
- `{{approver_name}}` - Name of reviewer
- `{{approver_role}}` - Role of reviewer
- `{{completeness_score}}` - AI completeness score (0-100)
- `{{pedagogical_score}}` - AI pedagogical score (0-100)
- `{{content_quality_score}}` - AI content quality score (0-100)
- `{{overall_score}}` - AI overall score (0-100)
- `{{ai_feedback}}` - Detailed AI feedback on the lesson note
- `{{school_name}}` - School name
- `{{headmaster_name}}` - Headmaster name
- `{{headmaster_email}}` - Headmaster email

### Subscription Confirmation Email (`subscription_confirmation_email.txt`)
- `{{school_name}}` - School name
- `{{plan_name}}` - Name of subscription plan (Free Tier, Basic, Premium)
- `{{price}}` - Price per billing cycle
- `{{billing_cycle}}` - Billing interval (month, year, etc.)
- `{{start_date}}` - Subscription start date
- `{{billing_email}}` - Billing contact email
- `{{features_list}}` - Formatted list of plan features
- `{{usage_limits}}` - Student and class limits
- `{{included_services}}` - Description of included services
- `{{login_url}}` - Frontend login URL
- `{{support_email}}` - Support email address
- `{{support_phone}}` - Support phone number
- `{{billing_management_url}}` - URL to manage subscription
- `{{next_billing_date}}` - Next billing date

### Subscription Upgrade Email (`subscription_upgrade_email.txt`)
- `{{school_name}}` - School name
- `{{previous_plan}}` - Previous subscription plan
- `{{plan_name}}` - New subscription plan
- `{{upgrade_date}}` - Date of upgrade
- `{{price}}` - New price
- `{{billing_cycle}}` - Billing interval
- `{{new_features}}` - List of newly available features
- `{{removed_limitations}}` - Limitations removed in new plan
- `{{new_usage_limits}}` - Updated student/class limits
- `{{new_resources}}` - Training and resource information
- `{{feature_highlights}}` - Key benefits of new plan
- `{{support_email}}` - Support contact
- `{{support_phone}}` - Support phone
- `{{next_billing_date}}` - Next renewal date
- `{{invoice_url}}` - Link to download invoice
- `{{prorated_credit}}` - (Optional) Credit applied for partial billing
- `{{prorated_amount}}` - (Optional) Prorated amount charged today

### Payment Confirmation Email (`payment_confirmation_email.txt`)
- `{{school_name}}` - School name
- `{{invoice_number}}` - Invoice number
- `{{payment_date}}` - Date payment was processed
- `{{amount_paid}}` - Amount paid
- `{{payment_method}}` - Payment method used (card, bank transfer, etc.)
- `{{payment_status}}` - Status (Confirmed, Pending, etc.)
- `{{plan_name}}` - Subscription plan name
- `{{billing_cycle}}` - Billing cycle frequency
- `{{subtotal}}` - Subtotal before tax
- `{{tax}}` - Tax amount
- `{{total_amount}}` - Total amount due
- `{{access_details}}` - Details of what was activated
- `{{billing_email}}` - Billing contact email
- `{{billing_phone}}` - Billing contact phone
- `{{dashboard_url}}` - Link to billing dashboard
- `{{receipt_url}}` - Link to download receipt
- `{{renewal_date}}` - (Optional) Next renewal date

## Customizing Templates

### Step 1: Edit the Template File

Open the template in a text editor:

```bash
# Example: Edit welcome email
nano backend/email_templates/welcome_email.txt
```

### Step 2: Modify Content

You can:
- Change the subject line
- Rewrite the body text
- Add/remove sections
- Rearrange placeholders

**DO NOT** remove placeholder variables unless you're also updating the backend code.

### Step 3: Test Changes

1. Restart the backend:
```bash
docker compose restart backend
```

2. Register a test school to see the new email

3. Check logs for any template errors:
```bash
docker compose logs backend | grep -i email
```

## Customization Examples

### Make Welcome Email More Personal

Original:
```
Dear {{username}},

Welcome to EduPulse!
```

Customized:
```
Hi {{username}},

Welcome to the {{school_name}} family on EduPulse! 🎓

We're thrilled to have you on board!
```

### Add School-Specific Details

In `staff_welcome_email.txt`:
```
Your school {{school_name}} is located at:
[Add your school address]

Contact Information:
- Phone: [Your school phone]
- Email: [Your school email]
```

### Update Support Contact

Find and replace `support@edupulse.com` with your school's support email:

```bash
# In all templates
sed -i 's/support@edupulse.com/your-email@school.edu/g' backend/email_templates/*.txt
```

## Best Practices

✅ **DO:**
- Keep templates professional and friendly
- Test before deploying to production
- Keep template files UTF-8 encoded
- Use consistent formatting/tone across templates
- Include support contact information

❌ **DON'T:**
- Remove placeholder variables without code changes
- Add too much HTML (plain text is recommended)
- Make templates longer than 1000 words
- Include sensitive information (passwords, tokens)
- Use special characters that might break email encoding

## Email Configuration

### SMTP Settings

Make sure your `.env` file has:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@edupulse.edu
FRONTEND_URL=http://localhost:5173
```

### Frontend URL

The `FRONTEND_URL` environment variable is used in email links:

```bash
# Development
FRONTEND_URL=http://localhost:5173

# Production
FRONTEND_URL=https://yourdomain.com
```

## Adding New Email Types

To add a new email template:

1. **Create template file:**
```bash
touch backend/email_templates/your_email_type.txt
```

2. **Add helper function in `backend/email_templates.py`:**
```python
def get_your_email(param1, param2, param3):
    """Generate email for [description]."""
    variables = {
        'param1': param1,
        'param2': param2,
        'param3': param3,
    }
    return render_email_template('your_email_type', variables)
```

3. **Use in your code:**
```python
from backend.email_templates import get_your_email

subject, body = get_your_email(value1, value2, value3)
if subject and body:
    send_email_notification(
        to_email='recipient@example.com',
        subject=subject,
        body=body
    )
```

## Debugging Email Issues

### View Email in Logs

If emails aren't sending, check the backend logs:

```bash
docker compose logs backend | grep -i "email"
```

### Test Email System

```bash
# SSH into backend container
docker compose exec backend bash

# Test send
python3 -c "
from backend.api.api import mail
from flask_mail import Message
msg = Message(subject='Test', recipients=['your@email.com'], body='Test email')
mail.send(msg)
print('Email sent successfully!')
"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| "Email template not found" | Check template file exists in `backend/email_templates/` |
| "Failed to send email" | Verify MAIL_* environment variables in .env |
| "Invalid placeholder" | Check placeholder syntax: `{{variable_name}}` not `{variable}` |
| "Email not received" | Check spam folder, verify SMTP settings, check logs |

## Production Checklist

- [ ] Update MAIL_SERVER to production SMTP (not localhost)
- [ ] Set MAIL_USERNAME and MAIL_PASSWORD to production account
- [ ] Update FRONTEND_URL to production domain
- [ ] Test all email types with real email addresses
- [ ] Customize templates with school branding
- [ ] Set MAIL_DEFAULT_SENDER to school email
- [ ] Review spam/email settings with hosting provider

## Support

For issues with email templates:
1. Check backend logs: `docker compose logs backend`
2. Verify template syntax
3. Ensure environment variables are set
4. Contact support@edupulse.com with error details
