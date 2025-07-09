# subscription/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import uuid
from decimal import Decimal
from enum import Enum

class SubscriptionStatus(models.TextChoices):
    TRIAL = 'trial', 'Trial'
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    CANCELLED = 'cancelled', 'Cancelled'
    SUSPENDED = 'suspended', 'Suspended'

class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    INITIATED = 'initiated', 'Initiated'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'
    CANCELLED = 'cancelled', 'Cancelled'

class PlanType(models.TextChoices):
    BASIC = 'basic', 'Basic'
    STANDARD = 'standard', 'Standard'
    PREMIUM = 'premium', 'Premium'
    ENTERPRISE = 'enterprise', 'Enterprise'

class SubscriptionPlan(models.Model):
    DURATION_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    plan_type = models.CharField(max_length=20, choices=PlanType.choices, default=PlanType.BASIC)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NPR')
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    
    # Trial settings
    trial_period_days = models.PositiveIntegerField(default=7)
    trial_enabled = models.BooleanField(default=True)
    
    # Features and limits
    features = models.JSONField(default=dict, help_text="Plan features and limits")
    max_users = models.PositiveIntegerField(default=1)
    max_projects = models.PositiveIntegerField(default=5)
    storage_limit_gb = models.PositiveIntegerField(default=10)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'price']
        
    def __str__(self):
        return f"{self.name} - Rs.{self.price} ({self.duration})"
    
    def get_duration_days(self):
        """Get duration in days for calculation"""
        duration_map = {
            'monthly': 30,
            'quarterly': 90,
            'yearly': 365
        }
        return duration_map.get(self.duration, 30)

class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    
    # Status and dates
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIAL)
    trial_start_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Trial tracking
    trial_used = models.BooleanField(default=False)
    trial_extended = models.BooleanField(default=False)
    trial_extension_days = models.PositiveIntegerField(default=0)
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=True)
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'plan']
        
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"
    
    def clean(self):
        if self.trial_start_date and self.trial_end_date:
            if self.trial_end_date <= self.trial_start_date:
                raise ValidationError("Trial end date must be after trial start date")
        
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError("End date must be after start date")
    
    def is_trial_active(self):
        """Check if trial is currently active"""
        if not self.trial_start_date or not self.trial_end_date:
            return False
        now = timezone.now()
        return (self.status == SubscriptionStatus.TRIAL and 
                self.trial_start_date <= now <= self.trial_end_date)
    
    def is_active(self):
        """Check if subscription is currently active"""
        if self.status == SubscriptionStatus.CANCELLED:
            return False
            
        now = timezone.now()
        
        # Check trial status
        if self.is_trial_active():
            return True
            
        # Check paid subscription
        if self.status == SubscriptionStatus.ACTIVE and self.end_date:
            return now <= self.end_date
            
        return False
    
    def days_until_expiry(self):
        """Get days until expiry (trial or paid)"""
        now = timezone.now()
        
        if self.is_trial_active():
            return (self.trial_end_date - now).days
        elif self.status == SubscriptionStatus.ACTIVE and self.end_date:
            return (self.end_date - now).days
        
        return 0
    
    def start_trial(self):
        """Start free trial"""
        if self.trial_used:
            raise ValidationError("Trial already used for this plan")
        
        if not self.plan.trial_enabled:
            raise ValidationError("Trial not enabled for this plan")
        
        self.trial_start_date = timezone.now()
        self.trial_end_date = self.trial_start_date + timedelta(days=self.plan.trial_period_days)
        self.status = SubscriptionStatus.TRIAL
        self.trial_used = True
        self.save()
    
    def convert_to_paid(self):
        """Convert trial to paid subscription"""
        if self.status != SubscriptionStatus.TRIAL:
            raise ValidationError("Can only convert trial subscriptions")
        
        self.status = SubscriptionStatus.ACTIVE
        self.start_date = timezone.now()
        self.end_date = self.start_date + timedelta(days=self.plan.get_duration_days())
        self.save()
    
    def extend_trial(self, days):
        """Extend trial period"""
        if self.status != SubscriptionStatus.TRIAL:
            raise ValidationError("Can only extend trial subscriptions")
        
        self.trial_end_date += timedelta(days=days)
        self.trial_extended = True
        self.trial_extension_days += days
        self.save()
    
    def cancel(self, immediate=False):
        """Cancel subscription"""
        if immediate:
            self.status = SubscriptionStatus.CANCELLED
            self.end_date = timezone.now()
        else:
            self.cancel_at_period_end = True
            self.auto_renew = False
        
        self.cancelled_at = timezone.now()
        self.save()
    
    def renew(self):
        """Renew subscription"""
        if self.status != SubscriptionStatus.ACTIVE:
            raise ValidationError("Can only renew active subscriptions")
        
        self.start_date = self.end_date
        self.end_date = self.start_date + timedelta(days=self.plan.get_duration_days())
        self.save()

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NPR')
    payment_method = models.CharField(max_length=50, default='khalti')
    
    # Khalti specific fields
    pidx = models.CharField(max_length=255, unique=True, help_text="Payment identifier from Khalti")
    khalti_transaction_id = models.CharField(max_length=255, null=True, blank=True)
    khalti_payment_url = models.URLField(null=True, blank=True)
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_gateway_response = models.JSONField(default=dict, help_text="Full response from payment gateway")
    
    # Failure tracking
    failure_reason = models.TextField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Refund tracking
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_reason = models.TextField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Payment {self.id} - {self.user.username} - Rs.{self.amount} ({self.status})"
    
    def mark_as_completed(self, transaction_id=None, gateway_response=None):
        """Mark payment as completed"""
        self.status = PaymentStatus.COMPLETED
        self.completed_at = timezone.now()
        
        if transaction_id:
            self.khalti_transaction_id = transaction_id
        
        if gateway_response:
            self.payment_gateway_response = gateway_response
        
        self.save()
        
        # Convert trial to paid if applicable
        if self.subscription.status == SubscriptionStatus.TRIAL:
            self.subscription.convert_to_paid()
    
    def mark_as_failed(self, reason=None, gateway_response=None):
        """Mark payment as failed"""
        self.status = PaymentStatus.FAILED
        self.failed_at = timezone.now()
        self.failure_reason = reason
        
        if gateway_response:
            self.payment_gateway_response = gateway_response
        
        self.save()
    
    def can_retry(self):
        """Check if payment can be retried"""
        return self.status == PaymentStatus.FAILED and self.retry_count < 3

class SubscriptionUsage(models.Model):
    """Track subscription usage and limits"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.OneToOneField(Subscription, on_delete=models.CASCADE, related_name='usage')
    
    # Usage metrics
    users_count = models.PositiveIntegerField(default=0)
    projects_count = models.PositiveIntegerField(default=0)
    storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Feature usage
    api_calls_count = models.PositiveIntegerField(default=0)
    api_calls_limit = models.PositiveIntegerField(default=1000)
    
    # Reset tracking
    last_reset = models.DateTimeField(auto_now_add=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Usage for {self.subscription}"
    
    def is_over_limit(self, resource_type):
        """Check if usage is over limit for a specific resource"""
        if resource_type == 'users':
            return self.users_count >= self.subscription.plan.max_users
        elif resource_type == 'projects':
            return self.projects_count >= self.subscription.plan.max_projects
        elif resource_type == 'storage':
            return self.storage_used_gb >= self.subscription.plan.storage_limit_gb
        
        return False
    
    def reset_usage(self):
        """Reset monthly usage counters"""
        self.api_calls_count = 0
        self.last_reset = timezone.now()
        self.save()

class WebhookEvent(models.Model):
    """Store webhook events from Khalti"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    
    # Event data
    event_data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Webhook {self.event_type} - {self.created_at}"