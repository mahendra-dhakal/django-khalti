# subscription/utils.py
import uuid
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import SubscriptionUsage, Subscription

def generate_order_id(subscription_id):
    """
    Generate a unique order ID for payment.
    Combines subscription ID with a timestamp for uniqueness.
    """
    timestamp = int(timezone.now().timestamp())
    return f"SUB-{subscription_id}-{timestamp}"

def send_payment_notification(user, template_name, context):
    """
    Send a notification email to the user.

    Args:
        user: The user object to send the email to.
        template_name: The name of the email template (without extension).
        context: The context dictionary for the template.
    """
    try:
        subject_map = {
            'subscription_created': 'Your Subscription has been Created',
            'payment_completed': 'Your Payment was Successful',
            'payment_failed': 'Your Payment Failed',
            'refund_initiated': 'Your Refund has been Initiated',
            'refund_completed': 'Your Refund is Complete',
        }
        subject = subject_map.get(template_name, 'Subscription Notification')

        # Assuming you have email templates in a 'templates/emails/' directory
        html_message = render_to_string(f'emails/{template_name}.html', context)
        plain_message = render_to_string(f'emails/{template_name}.txt', context)

        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        # In a production environment, use a robust logging framework
        print(f"Error sending email notification: {e}")

def create_usage_record(subscription):
    """
    Create a usage record for a new subscription if it doesn't exist.
    """
    SubscriptionUsage.objects.get_or_create(subscription=subscription)