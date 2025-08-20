import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from typing import List, Optional

logger = logging.getLogger(__name__)


def send_order_notification_email(order_data: dict, recipient_email: str) -> bool:
    """
    Send order notification email to administrator.
    
    Args:
        order_data (dict): Order information
        recipient_email (str): Administrator email address
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        subject = f"New Order Placed - #{order_data['order_number']}"
        
        # Create email content
        context = {
            'order': order_data,
            'customer_name': f"{order_data['billing_first_name']} {order_data['billing_last_name']}",
            'total_amount': order_data['total_amount'],
        }
        
        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>New Order Notification</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .order-info {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                .items-table th, .items-table td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
                .items-table th {{ background-color: #f8f9fa; }}
                .total {{ font-weight: bold; font-size: 1.2em; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Order Notification</h1>
                    <p>A new order has been placed on your e-commerce platform.</p>
                </div>
                
                <div class="order-info">
                    <h2>Order Details</h2>
                    <p><strong>Order Number:</strong> {order_data['order_number']}</p>
                    <p><strong>Customer:</strong> {context['customer_name']}</p>
                    <p><strong>Email:</strong> {order_data['billing_email']}</p>
                    <p><strong>Phone:</strong> {order_data['billing_phone']}</p>
                    <p><strong>Order Date:</strong> {order_data['created_at']}</p>
                    <p><strong>Status:</strong> {order_data['status'].title()}</p>
                </div>
                
                <h3>Order Items</h3>
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>SKU</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Add order items
        for item in order_data.get('items', []):
            html_content += f"""
                        <tr>
                            <td>{item['product_name']}</td>
                            <td>{item['product_sku']}</td>
                            <td>{item['quantity']}</td>
                            <td>KES {item['unit_price']}</td>
                            <td>KES {item['total_price']}</td>
                        </tr>
            """
        
        html_content += f"""
                    </tbody>
                </table>
                
                <div class="order-info">
                    <h3>Order Summary</h3>
                    <p><strong>Subtotal:</strong> KES {order_data['subtotal']}</p>
                    <p><strong>Tax:</strong> KES {order_data['tax_amount']}</p>
                    <p><strong>Shipping:</strong> KES {order_data['shipping_cost']}</p>
                    <p class="total"><strong>Total:</strong> KES {order_data['total_amount']}</p>
                </div>
                
                <div class="order-info">
                    <h3>Billing Address</h3>
                    <p>
                        {order_data['billing_first_name']} {order_data['billing_last_name']}<br>
                        {order_data['billing_address']}<br>
                        {order_data['billing_city']}, {order_data['billing_country']}
                    </p>
                </div>
                
                <div class="order-info">
                    <h3>Shipping Address</h3>
                    <p>
                        {order_data['shipping_first_name']} {order_data['shipping_last_name']}<br>
                        {order_data['shipping_address']}<br>
                        {order_data['shipping_city']}, {order_data['shipping_country']}
                    </p>
                </div>
                
                {f'<div class="order-info"><h3>Notes</h3><p>{order_data["notes"]}</p></div>' if order_data.get('notes') else ''}
                
                <div class="footer">
                    <p>Please process this order promptly. You can manage orders through the admin panel.</p>
                    <p>This is an automated notification from your e-commerce system.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_content = f"""
        New Order Notification
        
        Order Number: {order_data['order_number']}
        Customer: {context['customer_name']}
        Email: {order_data['billing_email']}
        Phone: {order_data['billing_phone']}
        Total Amount: KES {order_data['total_amount']}
        Status: {order_data['status'].title()}
        
        Please check the admin panel for full order details.
        """
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Order notification email sent to {recipient_email} for order {order_data['order_number']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send order notification email: {str(e)}")
        return False


def send_customer_order_confirmation_email(order_data: dict, customer_email: str) -> bool:
    """
    Send order confirmation email to customer.
    
    Args:
        order_data (dict): Order information
        customer_email (str): Customer email address
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        subject = f"Order Confirmation - #{order_data['order_number']}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Order Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #28a745; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; text-align: center; }}
                .order-info {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                .items-table th, .items-table td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
                .items-table th {{ background-color: #f8f9fa; }}
                .total {{ font-weight: bold; font-size: 1.2em; color: #28a745; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Thank You for Your Order!</h1>
                    <p>Your order has been successfully placed and is being processed.</p>
                </div>
                
                <div class="order-info">
                    <h2>Order Details</h2>
                    <p><strong>Order Number:</strong> {order_data['order_number']}</p>
                    <p><strong>Order Date:</strong> {order_data['created_at']}</p>
                    <p><strong>Status:</strong> {order_data['status'].title()}</p>
                </div>
                
                <h3>Your Items</h3>
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Quantity</th>
                            <th>Price</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Add order items
        for item in order_data.get('items', []):
            html_content += f"""
                        <tr>
                            <td>{item['product_name']}</td>
                            <td>{item['quantity']}</td>
                            <td>KES {item['unit_price']}</td>
                            <td>KES {item['total_price']}</td>
                        </tr>
            """
        
        html_content += f"""
                    </tbody>
                </table>
                
                <div class="order-info">
                    <h3>Order Summary</h3>
                    <p><strong>Subtotal:</strong> KES {order_data['subtotal']}</p>
                    <p><strong>Tax:</strong> KES {order_data['tax_amount']}</p>
                    <p><strong>Shipping:</strong> KES {order_data['shipping_cost']}</p>
                    <p class="total"><strong>Total:</strong> KES {order_data['total_amount']}</p>
                </div>
                
                <div class="order-info">
                    <h3>Shipping Address</h3>
                    <p>
                        {order_data['shipping_first_name']} {order_data['shipping_last_name']}<br>
                        {order_data['shipping_address']}<br>
                        {order_data['shipping_city']}, {order_data['shipping_country']}
                    </p>
                </div>
                
                <div class="footer">
                    <p>We'll send you another email when your order ships.</p>
                    <p>Thank you for shopping with us!</p>
                    <p>If you have any questions, please contact our customer service.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_content = f"""
        Thank you for your order!
        
        Order Number: {order_data['order_number']}
        Total Amount: KES {order_data['total_amount']}
        Status: {order_data['status'].title()}
        
        We'll send you updates as your order is processed.
        Thank you for shopping with us!
        """
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Order confirmation email sent to {customer_email} for order {order_data['order_number']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send customer order confirmation email: {str(e)}")
        return False


def send_stock_alert_email(product_name: str, current_stock: int, minimum_stock: int, recipient_emails: List[str]) -> bool:
    """
    Send low stock alert email to administrators.
    
    Args:
        product_name (str): Product name
        current_stock (int): Current stock level
        minimum_stock (int): Minimum stock threshold
        recipient_emails (List[str]): Administrator email addresses
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        subject = f"LOW STOCK ALERT: {product_name}"
        
        message = f"""
        Stock Alert Notification
        
        Product: {product_name}
        Current Stock: {current_stock} units
        Minimum Stock Level: {minimum_stock} units
        
        This product is running low and needs to be restocked.
        Please take appropriate action to replenish inventory.
        
        This is an automated notification from your inventory management system.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_emails,
            fail_silently=False
        )
        
        logger.info(f"Stock alert email sent for product: {product_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send stock alert email: {str(e)}")
        return False