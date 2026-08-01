"""
Background job for handling trial expirations in EduPulse.
This job runs periodically to:
1. Check for expired trials
2. Downgrade schools from trial to free tier
3. Send expiry notification emails
"""

import logging
from datetime import datetime, timezone
from backend.api.models import School, db
from backend.subscription_state import get_trial_days_remaining, normalize_utc_datetime
from backend.email_templates import get_trial_expiry_email, get_trial_reminder_email
from backend.utils import send_email_notification
import os

logger = logging.getLogger(__name__)


def process_expired_trials():
    """
    Check for schools with expired trials and process expiration.
    This should be called periodically (e.g., daily via cron/APScheduler).
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Find schools with expired trials
        expired_trials = School.query.filter(
            School.trial_plan.isnot(None),
            School.trial_end_date.isnot(None),
            School.trial_end_date <= now
        ).all()
        
        if not expired_trials:
            logger.info("No expired trials found")
            return {'status': 'success', 'schools_processed': 0}
        
        processed_count = 0
        error_count = 0
        
        for school in expired_trials:
            try:
                # Send expiry notification email (if school has contact email)
                proprietor = school.users.filter_by(role='proprietor').first()
                if proprietor and proprietor.email:
                    login_url = os.getenv("FRONTEND_URL", "http://localhost:5173/login")
                    trial_subject, trial_body = get_trial_expiry_email(
                        school_name=school.name,
                        login_url=login_url
                    )
                    
                    if trial_subject and trial_body:
                        try:
                            send_email_notification(
                                to_email=proprietor.email,
                                subject=trial_subject,
                                body=trial_body
                            )
                            logger.info(f"Trial expiry email sent to {proprietor.email} for school {school.id}")
                        except Exception as e:
                            logger.error(f"Failed to send trial expiry email for school {school.id}: {str(e)}")
                
                # End the trial but retain the end timestamp for audit/history and one-time-use enforcement.
                school.trial_plan = None
                school.is_trial_active = False
                db.session.commit()
                
                logger.info(f"Trial expired for school {school.id} ({school.name}). Downgraded to Free Tier.")
                processed_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing trial expiration for school {school.id}: {str(e)}")
                db.session.rollback()
                continue
        
        logger.info(f"Trial expiration job completed: {processed_count} schools processed, {error_count} errors")
        return {
            'status': 'success',
            'schools_processed': processed_count,
            'errors': error_count
        }
        
    except Exception as e:
        logger.error(f"Fatal error in trial expiration job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def send_trial_reminder_email(days_before_expiry=3):
    """
    Send reminder emails to schools with trials expiring soon.
    This should be called periodically (e.g., daily).
    
    Args:
        days_before_expiry: Number of days before expiry to send reminder
    """
    try:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        
        # Find schools with trials expiring within N days
        expiry_date_start = now
        expiry_date_end = now + timedelta(days=days_before_expiry + 1)
        
        expiring_soon = School.query.filter(
            School.trial_plan.isnot(None),
            School.trial_end_date.isnot(None),
            School.trial_end_date > now,  # Not yet expired
            School.trial_end_date >= expiry_date_start,
            School.trial_end_date <= expiry_date_end
        ).all()
        
        if not expiring_soon:
            logger.info(f"No trials expiring within {days_before_expiry} days")
            return {'status': 'success', 'reminders_sent': 0}
        
        reminders_sent = 0
        
        for school in expiring_soon:
            try:
                proprietor = school.users.filter_by(role='proprietor').first()
                if proprietor and proprietor.email:
                    login_url = os.getenv("FRONTEND_URL", "http://localhost:5173/login")
                    trial_end_date = normalize_utc_datetime(school.trial_end_date)
                    days_remaining = get_trial_days_remaining(trial_end_date, now=now)
                    
                    trial_subject, trial_body = get_trial_reminder_email(
                        school_name=school.name,
                        login_url=login_url,
                        trial_end_date=trial_end_date,
                        days_remaining=days_remaining
                    )
                    
                    if trial_subject and trial_body:
                        try:
                            send_email_notification(
                                to_email=proprietor.email,
                                subject=trial_subject,
                                body=trial_body
                            )
                            logger.info(f"Trial reminder email sent to {proprietor.email} for school {school.id} ({days_remaining} days remaining)")
                            reminders_sent += 1
                        except Exception as e:
                            logger.error(f"Failed to send trial reminder email for school {school.id}: {str(e)}")
                            
            except Exception as e:
                logger.error(f"Error sending trial reminder for school {school.id}: {str(e)}")
                continue
        
        logger.info(f"Trial reminder job completed: {reminders_sent} reminders sent")
        return {'status': 'success', 'reminders_sent': reminders_sent}
        
    except Exception as e:
        logger.error(f"Fatal error in trial reminder job: {str(e)}")
        return {'status': 'error', 'message': str(e)}
