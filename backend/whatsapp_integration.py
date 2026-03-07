"""
WhatsApp Business API Integration for EduPulse (Ghana Market).

Features:
- Send report cards as PDF via WhatsApp
- Automated fee reminders to parents
- Attendance alerts
- Term announcements
- Payment confirmations

Setup:
1. Get WhatsApp Business API access from Meta for Developers
2. Set environment variables: WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID
3. Configure webhook endpoint in Meta Dashboard
"""

import logging
import os
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

# WhatsApp API Configuration
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = "v18.0"
WHATSAPP_BASE_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"


class WhatsAppError(Exception):
    """Custom exception for WhatsApp API errors."""
    pass


def format_ghana_phone(phone: str) -> str:
    """
    Format Ghanaian phone number to WhatsApp format.
    
    Examples:
        0244123456 -> 233244123456
        +233244123456 -> 233244123456
        233244123456 -> 233244123456
    
    Args:
        phone: Ghanaian phone number in any format
    
    Returns:
        str: Phone number in WhatsApp format (233XXXXXXXXX)
    """
    # Remove all non-digit characters except +
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    # Remove leading + if present
    if phone.startswith("+"):
        phone = phone[1:]

    # Keep already international numbers (non-Ghana) unchanged
    if phone.startswith("233"):
        return phone
    if len(phone) > 10 and not phone.startswith("0"):
        return phone

    # Ghana local format -> international format
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    elif len(phone) in [9, 10]:
        phone = "233" + phone.lstrip("0")
    
    return phone


def send_text_message(to_phone: str, message: str) -> Dict[str, Any]:
    """
    Send a text message via WhatsApp.
    
    Args:
        to_phone: Recipient phone number (Ghana format)
        message: Text message content
    
    Returns:
        dict: Response from WhatsApp API
    
    Raises:
        WhatsAppError: If sending fails
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp API credentials not configured")
    
    phone = format_ghana_phone(to_phone)
    
    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WhatsAppError(error_msg)
        
        data = response.json()
        logger.info(f"WhatsApp message sent to {phone}, message_id: {data.get('messages', [{}])[0].get('id')}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending WhatsApp message: {str(e)}"
        logger.error(error_msg)
        raise WhatsAppError(error_msg)


def send_template_message(to_phone: str, template_name: str, language_code: str = "en", 
                          parameters: Optional[list] = None) -> Dict[str, Any]:
    """
    Send a WhatsApp template message (for notifications).
    
    Templates must be pre-approved in Meta Business Manager.
    
    Args:
        to_phone: Recipient phone number
        template_name: Name of approved template
        language_code: Template language ('en', 'en_US')
        parameters: List of parameter values for template variables
    
    Returns:
        dict: Response from WhatsApp API
    
    Raises:
        WhatsAppError: If sending fails
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp API credentials not configured")
    
    phone = format_ghana_phone(to_phone)
    
    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    template_payload = {
        "name": template_name,
        "language": {"code": language_code}
    }
    
    # Add parameters if provided
    if parameters:
        template_payload["components"] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(param)} for param in parameters
                ]
            }
        ]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": template_payload
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WhatsAppError(error_msg)
        
        data = response.json()
        logger.info(f"WhatsApp template '{template_name}' sent to {phone}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending WhatsApp template: {str(e)}"
        logger.error(error_msg)
        raise WhatsAppError(error_msg)


def send_document(to_phone: str, document_url: str, filename: str, 
                  caption: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a document (PDF, Excel, etc.) via WhatsApp.
    
    Perfect for sending report cards!
    
    Args:
        to_phone: Recipient phone number
        document_url: Public URL to the document (must be HTTPS)
        filename: Name of the file
        caption: Optional message to accompany document
    
    Returns:
        dict: Response from WhatsApp API
    
    Raises:
        WhatsAppError: If sending fails
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp API credentials not configured")
    
    phone = format_ghana_phone(to_phone)
    
    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename
        }
    }
    
    if caption:
        payload["document"]["caption"] = caption
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WhatsAppError(error_msg)
        
        data = response.json()
        logger.info(f"WhatsApp document '{filename}' sent to {phone}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending WhatsApp document: {str(e)}"
        logger.error(error_msg)
        raise WhatsAppError(error_msg)


def upload_media(file_bytes: bytes, filename: str, mime_type: str = "application/pdf") -> str:
    """Upload media to WhatsApp and return media ID."""
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp API credentials not configured")

    if not file_bytes:
        raise WhatsAppError("Document bytes are required")

    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
    }

    files = {
        "file": (filename, file_bytes, mime_type)
    }
    data = {
        "messaging_product": "whatsapp"
    }

    try:
        response = requests.post(url, headers=headers, files=files, data=data, timeout=20)
        if response.status_code not in [200, 201]:
            error_msg = f"WhatsApp media upload failed: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WhatsAppError(error_msg)

        media_id = response.json().get("id")
        if not media_id:
            raise WhatsAppError("WhatsApp media upload returned no media ID")

        return media_id
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error uploading WhatsApp media: {str(e)}"
        logger.error(error_msg)
        raise WhatsAppError(error_msg)


def send_document_by_media_id(to_phone: str, media_id: str, filename: str,
                              caption: Optional[str] = None) -> Dict[str, Any]:
    """Send already-uploaded media as WhatsApp document message."""
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppError("WhatsApp API credentials not configured")

    if not media_id:
        raise WhatsAppError("media_id is required")

    phone = format_ghana_phone(to_phone)
    url = f"{WHATSAPP_BASE_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename
        }
    }

    if caption:
        payload["document"]["caption"] = caption

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code not in [200, 201]:
            error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WhatsAppError(error_msg)

        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending WhatsApp document by media id: {str(e)}"
        logger.error(error_msg)
        raise WhatsAppError(error_msg)


def send_document_bytes(to_phone: str, document_bytes: bytes, filename: str,
                        caption: Optional[str] = None) -> Dict[str, Any]:
    """Upload raw document bytes to WhatsApp and send to recipient."""
    media_id = upload_media(document_bytes, filename, mime_type="application/pdf")
    return send_document_by_media_id(to_phone, media_id, filename, caption=caption)


# ============================================
# EduPulse-Specific WhatsApp Functions
# ============================================

def send_report_card_notification(parent_phone: str, student_name: str, 
                                  report_card_url: str, term: str) -> Dict[str, Any]:
    """
    Send report card to parent via WhatsApp.
    
    Args:
        parent_phone: Parent's phone number
        student_name: Name of the student
        report_card_url: Public URL to the PDF report card
        term: Academic term (e.g., "Term 1 2025/2026")
    
    Returns:
        dict: WhatsApp API response
    """
    filename = f"{student_name.replace(' ', '_')}_Report_Card_{term.replace(' ', '_')}.pdf"
    caption = f"📊 Report Card for {student_name} - {term}\n\nGenerated by EduPulse SMT"
    
    return send_document(
        to_phone=parent_phone,
        document_url=report_card_url,
        filename=filename,
        caption=caption
    )


def send_fee_reminder(parent_phone: str, student_name: str, amount_due: float, 
                     due_date: str, school_name: str) -> Dict[str, Any]:
    """
    Send fee payment reminder to parent.
    
    Args:
        parent_phone: Parent's phone number
        student_name: Name of the student
        amount_due: Outstanding fee amount (GHS)
        due_date: Payment due date
        school_name: Name of the school
    
    Returns:
        dict: WhatsApp API response
    """
    message = f"""
🏫 {school_name}

Dear Parent/Guardian,

This is a reminder that school fees for {student_name} are due.

💰 Amount Outstanding: GH₵ {amount_due:.2f}
📅 Due Date: {due_date}

Please make payment at your earliest convenience.

Thank you!
    """.strip()
    
    return send_text_message(parent_phone, message)


def send_attendance_alert(parent_phone: str, student_name: str, date: str, 
                         school_name: str) -> Dict[str, Any]:
    """
    Send absence alert to parent.
    
    Args:
        parent_phone: Parent's phone number
        student_name: Name of the student
        date: Date of absence
        school_name: Name of the school
    
    Returns:
        dict: WhatsApp API response
    """
    message = f"""
⚠️ Attendance Alert - {school_name}

Dear Parent/Guardian,

{student_name} was marked absent on {date}.

If this is an error, please contact the school office.

Powered by EduPulse
    """.strip()
    
    return send_text_message(parent_phone, message)


def send_payment_confirmation(parent_phone: str, student_name: str, amount: float,
                            reference: str, school_name: str) -> Dict[str, Any]:
    """
    Send payment confirmation to parent.
    
    Args:
        parent_phone: Parent's phone number
        student_name: Name of the student
        amount: Amount paid (GHS)
        reference: Payment reference number
        school_name: Name of the school
    
    Returns:
        dict: WhatsApp API response
    """
    message = f"""
✅ Payment Confirmed - {school_name}

Dear Parent/Guardian,

Your payment has been received and confirmed.

👤 Student: {student_name}
💰 Amount: GH₵ {amount:.2f}
📝 Reference: {reference}

Thank you for your payment!

Powered by EduPulse
    """.strip()
    
    return send_text_message(parent_phone, message)


def send_term_announcement(parent_phone: str, term_name: str, start_date: str,
                          end_date: str, school_name: str) -> Dict[str, Any]:
    """
    Send new term announcement to parent.
    
    Args:
        parent_phone: Parent's phone number
        term_name: Name of the term (e.g., "Term 1")
        start_date: Term start date
        end_date: Term end date
        school_name: Name of the school
    
    Returns:
        dict: WhatsApp API response
    """
    message = f"""
📢 New Academic Term - {school_name}

Dear Parent/Guardian,

{term_name} will begin soon!

📅 Start Date: {start_date}
📅 End Date: {end_date}

Please ensure your child is prepared for the new term.

Looking forward to a great term!

Powered by EduPulse
    """.strip()
    
    return send_text_message(parent_phone, message)


# ============================================
# Testing & Utilities
# ============================================

def test_whatsapp_connection(test_phone: str = "233244123456") -> bool:
    """
    Test WhatsApp API connection.
    
    Args:
        test_phone: Test phone number to send message to
    
    Returns:
        bool: True if connection successful
    """
    try:
        send_text_message(
            to_phone=test_phone,
            message="🎉 EduPulse SMT WhatsApp integration test successful!"
        )
        logger.info("WhatsApp connection test passed")
        return True
    except WhatsAppError as e:
        logger.error(f"WhatsApp connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Test the integration
    print("Testing WhatsApp Integration...")
    print(f"Phone Number ID: {WHATSAPP_PHONE_NUMBER_ID}")
    print(f"Token Configured: {'Yes' if WHATSAPP_API_TOKEN else 'No'}")
    
    # Test phone formatting
    test_phones = ["0244123456", "+233244123456", "233244123456"]
    print("\nPhone Number Formatting Tests:")
    for phone in test_phones:
        formatted = format_ghana_phone(phone)
        print(f"  {phone} -> {formatted}")
