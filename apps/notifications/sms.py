import requests
import logging
from django.conf import settings
from typing import Optional

logger = logging.getLogger(__name__)


class AfricasTalkingSMS:
    """
    SMS service using Africa's Talking API.
    """
    
    def __init__(self):
        self.username = settings.AFRICAS_TALKING_USERNAME
        self.api_key = settings.AFRICAS_TALKING_API_KEY
        self.sender_id = settings.AFRICAS_TALKING_FROM
        self.base_url = "https://api.africastalking.com/version1/messaging"
        
        # Use sandbox for testing
        if self.username == 'sandbox':
            self.base_url = "https://api.sandbox.africastalking.com/version1/messaging"
    
    def send_sms(self, phone_number: str, message: str) -> dict:
        """
        Send SMS to a phone number.
        
        Args:
            phone_number (str): Recipient phone number (with country code)
            message (str): SMS message content
            
        Returns:
            dict: API response or error information
        """
        if not self.api_key:
            logger.warning("Africa's Talking API key not configured")
            return {'success': False, 'error': 'SMS service not configured'}
        
        # Format phone number (ensure it starts with +)
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'apiKey': self.api_key
        }
        
        data = {
            'username': self.username,
            'to': phone_number,
            'message': message,
        }
        
        if self.sender_id:
            data['from'] = self.sender_id
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"SMS sent successfully to {phone_number}")
                return {
                    'success': True,
                    'message_id': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('messageId'),
                    'status': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('status'),
                    'cost': result.get('SMSMessageData', {}).get('Recipients', [{}])[0].get('cost')
                }
            else:
                error_msg = f"SMS API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {'success': False, 'error': error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"SMS request failed: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Unexpected SMS error: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}


def send_order_confirmation_sms(phone_number: str, order_number: str, total_amount: str) -> dict:
    """
    Send order confirmation SMS to customer.
    
    Args:
        phone_number (str): Customer phone number
        order_number (str): Order number
        total_amount (str): Total order amount
        
    Returns:
        dict: SMS send result
    """
    message = (
        f"Order Confirmed! Your order #{order_number} totaling KES {total_amount} "
        f"has been received and is being processed. Thank you for shopping with us!"
    )
    
    sms_service = AfricasTalkingSMS()
    return sms_service.send_sms(phone_number, message)


def send_order_status_sms(phone_number: str, order_number: str, status: str, tracking_number: Optional[str] = None) -> dict:
    """
    Send order status update SMS to customer.
    
    Args:
        phone_number (str): Customer phone number
        order_number (str): Order number
        status (str): New order status
        tracking_number (str, optional): Tracking number if available
        
    Returns:
        dict: SMS send result
    """
    status_messages = {
        'confirmed': f"Your order #{order_number} has been confirmed and is being prepared.",
        'processing': f"Your order #{order_number} is now being processed.",
        'shipped': f"Great news! Your order #{order_number} has been shipped." + 
                  (f" Tracking: {tracking_number}" if tracking_number else ""),
        'delivered': f"Your order #{order_number} has been delivered. Thank you for shopping with us!",
        'cancelled': f"Your order #{order_number} has been cancelled. Please contact us if you have questions."
    }
    
    message = status_messages.get(status, f"Order #{order_number} status updated to: {status}")
    
    sms_service = AfricasTalkingSMS()
    return sms_service.send_sms(phone_number, message)


def send_low_stock_alert_sms(phone_number: str, product_name: str, current_stock: int) -> dict:
    """
    Send low stock alert SMS to administrators.
    
    Args:
        phone_number (str): Administrator phone number
        product_name (str): Product name
        current_stock (int): Current stock level
        
    Returns:
        dict: SMS send result
    """
    message = (
        f"STOCK ALERT: {product_name} is running low with only {current_stock} units remaining. "
        f"Please restock soon."
    )
    
    sms_service = AfricasTalkingSMS()
    return sms_service.send_sms(phone_number, message)