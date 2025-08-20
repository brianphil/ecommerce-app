from celery import shared_task
from django.conf import settings
import logging

from .models import Order
from apps.notifications.sms import send_order_confirmation_sms, send_order_status_sms
from apps.notifications.email import send_order_notification_email, send_customer_order_confirmation_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_notifications(self, order_id):
    """
    Send SMS and email notifications when an order is placed.
    
    Args:
        order_id (int): Order ID
    """
    try:
        order = Order.objects.select_related('customer').prefetch_related(
            'items__product'
        ).get(id=order_id)
        
        # Prepare order data for notifications
        order_data = {
            'order_number': order.order_number,
            'customer_id': order.customer.id,
            'subtotal': str(order.subtotal),
            'tax_amount': str(order.tax_amount),
            'shipping_cost': str(order.shipping_cost),
            'discount_amount': str(order.discount_amount),
            'total_amount': str(order.total_amount),
            'status': order.status,
            'billing_first_name': order.billing_first_name,
            'billing_last_name': order.billing_last_name,
            'billing_email': order.billing_email,
            'billing_phone': order.billing_phone,
            'billing_address': order.billing_address,
            'billing_city': order.billing_city,
            'billing_country': order.billing_country,
            'shipping_first_name': order.shipping_first_name,
            'shipping_last_name': order.shipping_last_name,
            'shipping_phone': order.shipping_phone,
            'shipping_address': order.shipping_address,
            'shipping_city': order.shipping_city,
            'shipping_country': order.shipping_country,
            'notes': order.notes,
            'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'items': []
        }
        
        # Add order items
        for item in order.items.all():
            order_data['items'].append({
                'product_name': item.product_name,
                'product_sku': item.product_sku,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price)
            })
        
        # Send SMS notification to customer
        if order.customer.phone_number:
            sms_result = send_order_confirmation_sms(
                phone_number=order.customer.phone_number,
                order_number=order.order_number,
                total_amount=str(order.total_amount)
            )
            
            if sms_result['success']:
                logger.info(f"SMS notification sent for order {order.order_number}")
            else:
                logger.error(f"Failed to send SMS for order {order.order_number}: {sms_result['error']}")
        
        # Send email notification to customer
        customer_email_result = send_customer_order_confirmation_email(
            order_data=order_data,
            customer_email=order.customer.email
        )
        
        if customer_email_result:
            logger.info(f"Customer email notification sent for order {order.order_number}")
        else:
            logger.error(f"Failed to send customer email for order {order.order_number}")
        
        # Send email notification to administrator
        admin_email_result = send_order_notification_email(
            order_data=order_data,
            recipient_email=settings.ADMIN_EMAIL
        )
        
        if admin_email_result:
            logger.info(f"Admin email notification sent for order {order.order_number}")
        else:
            logger.error(f"Failed to send admin email for order {order.order_number}")
        
        logger.info(f"Order notifications processed for order {order.order_number}")
        
    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_id} not found")
        raise
    
    except Exception as exc:
        logger.error(f"Error sending notifications for order {order_id}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_order_status_notification(self, order_id, new_status, tracking_number=None):
    """
    Send notifications when order status changes.
    
    Args:
        order_id (int): Order ID
        new_status (str): New order status
        tracking_number (str, optional): Tracking number if available
    """
    try:
        order = Order.objects.select_related('customer').get(id=order_id)
        
        # Send SMS notification to customer
        if order.customer.phone_number:
            sms_result = send_order_status_sms(
                phone_number=order.customer.phone_number,
                order_number=order.order_number,
                status=new_status,
                tracking_number=tracking_number
            )
            
            if sms_result['success']:
                logger.info(f"Status SMS sent for order {order.order_number} - Status: {new_status}")
            else:
                logger.error(f"Failed to send status SMS for order {order.order_number}: {sms_result['error']}")
        
        logger.info(f"Order status notifications sent for order {order.order_number}")
        
    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_id} not found")
        raise
    
    except Exception as exc:
        logger.error(f"Error sending status notifications for order {order_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def check_low_stock_products():
    """
    Check for products with low stock and send alerts.
    """
    from apps.products.models import Product
    from apps.notifications.email import send_stock_alert_email
    from apps.notifications.sms import send_low_stock_alert_sms
    
    try:
        # Find products with low stock
        low_stock_products = Product.objects.filter(
            stock_quantity__lte=models.F('minimum_stock'),
            status='active'
        )
        
        if low_stock_products.exists():
            for product in low_stock_products:
                # Send email alert
                send_stock_alert_email(
                    product_name=product.name,
                    current_stock=product.stock_quantity,
                    minimum_stock=product.minimum_stock,
                    recipient_emails=[settings.ADMIN_EMAIL]
                )
                
                logger.info(f"Low stock alert sent for product: {product.name}")
            
            logger.info(f"Low stock check completed. {low_stock_products.count()} products need restocking.")
        else:
            logger.info("Low stock check completed. No products need immediate restocking.")
            
    except Exception as e:
        logger.error(f"Error during low stock check: {str(e)}")


@shared_task
def cleanup_abandoned_carts():
    """
    Clean up abandoned carts older than 30 days.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.orders.models import Cart
    
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Find carts older than 30 days with no recent updates
        abandoned_carts = Cart.objects.filter(
            updated_at__lt=cutoff_date
        )
        
        count = abandoned_carts.count()
        abandoned_carts.delete()
        
        logger.info(f"Cleaned up {count} abandoned carts")
        
    except Exception as e:
        logger.error(f"Error during cart cleanup: {str(e)}")


@shared_task
def generate_daily_sales_report():
    """
    Generate daily sales report and send to administrators.
    """
    from datetime import date, timedelta
    from django.db.models import Sum, Count
    
    try:
        yesterday = date.today() - timedelta(days=1)
        
        # Get yesterday's orders
        daily_orders = Order.objects.filter(
            created_at__date=yesterday,
            status__in=['confirmed', 'processing', 'shipped', 'delivered']
        )
        
        # Calculate metrics
        total_orders = daily_orders.count()
        total_revenue = daily_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        average_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Prepare report
        report = f"""
        Daily Sales Report - {yesterday.strftime('%Y-%m-%d')}
        
        Total Orders: {total_orders}
        Total Revenue: KES {total_revenue}
        Average Order Value: KES {average_order_value:.2f}
        
        Order Status Breakdown:
        """
        
        # Add status breakdown
        status_counts = daily_orders.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        for status_data in status_counts:
            report += f"- {status_data['status'].title()}: {status_data['count']}\n"
        
        # Send report email
        from django.core.mail import send_mail
        
        send_mail(
            subject=f"Daily Sales Report - {yesterday.strftime('%Y-%m-%d')}",
            message=report,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=False
        )
        
        logger.info(f"Daily sales report sent for {yesterday}")
        
    except Exception as e:
        logger.error(f"Error generating daily sales report: {str(e)}")