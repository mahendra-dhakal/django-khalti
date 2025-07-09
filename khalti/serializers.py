# subscription/serializers.py
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from .models import (
    SubscriptionPlan, 
    Subscription, 
    Payment, 
    SubscriptionUsage,
    SubscriptionStatus,
    PaymentStatus,
    PlanType
)

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan model"""
    duration_display = serializers.CharField(source='get_duration_display', read_only=True)
    formatted_price = serializers.SerializerMethodField()
    features_list = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'slug', 'description', 'plan_type', 
            'price', 'formatted_price', 'currency', 'duration', 'duration_display',
            'trial_period_days', 'trial_enabled', 'features', 'features_list',
            'max_users', 'max_projects', 'storage_limit_gb',
            'is_active', 'is_popular', 'sort_order', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'duration_display', 'formatted_price', 'features_list']
    
    def get_formatted_price(self, obj):
        """Format price with currency"""
        return f"Rs. {obj.price:,.2f}"
    
    def get_features_list(self, obj):
        """Convert features JSON to list format"""
        features = obj.features or {}
        return [
            f"Up to {obj.max_users} users",
            f"Up to {obj.max_projects} projects", 
            f"{obj.storage_limit_gb} GB storage",
            *features.get('additional_features', [])
        ]

class SubscriptionUsageSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionUsage model"""
    usage_percentage = serializers.SerializerMethodField()
    limits = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionUsage
        fields = [
            'id', 'users_count', 'projects_count', 'storage_used_gb',
            'api_calls_count', 'api_calls_limit', 'usage_percentage',
            'limits', 'last_reset', 'created_at'
        ]
        read_only_fields = ['id', 'last_reset', 'created_at']
    
    def get_usage_percentage(self, obj):
        """Calculate usage percentages"""
        plan = obj.subscription.plan
        return {
            'users': (obj.users_count / plan.max_users) * 100 if plan.max_users > 0 else 0,
            'projects': (obj.projects_count / plan.max_projects) * 100 if plan.max_projects > 0 else 0,
            'storage': (float(obj.storage_used_gb) / plan.storage_limit_gb) * 100 if plan.storage_limit_gb > 0 else 0,
            'api_calls': (obj.api_calls_count / obj.api_calls_limit) * 100 if obj.api_calls_limit > 0 else 0
        }
    
    def get_limits(self, obj):
        """Get usage limits"""
        plan = obj.subscription.plan
        return {
            'users': plan.max_users,
            'projects': plan.max_projects,
            'storage': plan.storage_limit_gb,
            'api_calls': obj.api_calls_limit
        }

class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    user = UserSerializer(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    usage = SubscriptionUsageSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_trial_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'plan', 'status', 'status_display',
            'trial_start_date', 'trial_end_date', 'start_date', 'end_date',
            'trial_used', 'trial_extended', 'trial_extension_days',
            'auto_renew', 'cancel_at_period_end', 'cancelled_at',
            'is_active', 'is_trial_active', 'days_until_expiry',
            'time_remaining', 'usage', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'trial_used', 'trial_extended', 'trial_extension_days',
            'cancelled_at', 'created_at', 'updated_at'
        ]
    
    def get_time_remaining(self, obj):
        """Get formatted time remaining"""
        now = timezone.now()
        
        if obj.is_trial_active():
            time_left = obj.trial_end_date - now
            return {
                'type': 'trial',
                'days': time_left.days,
                'hours': time_left.seconds // 3600,
                'formatted': f"{time_left.days} days, {time_left.seconds // 3600} hours"
            }
        elif obj.status == SubscriptionStatus.ACTIVE and obj.end_date:
            time_left = obj.end_date - now
            return {
                'type': 'subscription',
                'days': time_left.days,
                'hours': time_left.seconds // 3600,
                'formatted': f"{time_left.days} days, {time_left.seconds // 3600} hours"
            }
        
        return None

class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    user = UserSerializer(read_only=True)
    subscription = SubscriptionSerializer(read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_retry = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'subscription', 'amount', 'formatted_amount',
            'currency', 'payment_method', 'pidx', 'khalti_transaction_id',
            'status', 'status_display', 'failure_reason', 'retry_count',
            'refund_amount', 'refund_reason', 'refunded_at',
            'initiated_at', 'completed_at', 'failed_at', 'can_retry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'subscription', 'khalti_transaction_id',
            'failure_reason', 'retry_count', 'refund_amount', 'refund_reason',
            'refunded_at', 'initiated_at', 'completed_at', 'failed_at',
            'created_at', 'updated_at'
        ]
    
    def get_formatted_amount(self, obj):
        """Format amount with currency"""
        return f"Rs. {obj.amount:,.2f}"

class SubscriptionCreateSerializer(serializers.Serializer):
    """Serializer for creating subscription"""
    plan_id = serializers.UUIDField()
    start_trial = serializers.BooleanField(default=False)
    auto_renew = serializers.BooleanField(default=True)
    
    def validate_plan_id(self, value):
        """Validate plan exists and is active"""
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise ValidationError("Invalid or inactive plan")
        return value
    
    def validate(self, attrs):
        """Validate subscription creation"""
        user = self.context['request'].user
        plan = SubscriptionPlan.objects.get(id=attrs['plan_id'])
        
        # Check if user already has subscription for this plan
        if Subscription.objects.filter(user=user, plan=plan).exists():
            raise ValidationError("You already have a subscription for this plan")
        
        # Check if trial is requested but not available
        if attrs['start_trial'] and not plan.trial_enabled:
            raise ValidationError("Trial is not available for this plan")
        
        # Check if user has already used trial for this plan
        if attrs['start_trial'] and Subscription.objects.filter(
            user=user, plan=plan, trial_used=True
        ).exists():
            raise ValidationError("You have already used the trial for this plan")
        
        return attrs

class PaymentInitiateSerializer(serializers.Serializer):
    """Serializer for initiating payment"""
    subscription_id = serializers.UUIDField()
    return_url = serializers.URLField()
    website_url = serializers.URLField()
    customer_name = serializers.CharField(max_length=100, required=False)
    customer_email = serializers.EmailField(required=False)
    customer_phone = serializers.CharField(max_length=15, required=False)
    
    def validate_subscription_id(self, value):
        """Validate subscription exists and belongs to user"""
        user = self.context['request'].user
        try:
            subscription = Subscription.objects.get(id=value, user=user)
        except Subscription.DoesNotExist:
            raise ValidationError("Invalid subscription")
        return value
    
    def validate(self, attrs):
        """Additional validation"""
        user = self.context['request'].user
        subscription = Subscription.objects.get(id=attrs['subscription_id'])
        
        # Check if payment is already in progress
        if Payment.objects.filter(
            subscription=subscription,
            status__in=[PaymentStatus.PENDING, PaymentStatus.INITIATED]
        ).exists():
            raise ValidationError("Payment is already in progress for this subscription")
        
        # Set default customer info
        if not attrs.get('customer_name'):
            attrs['customer_name'] = user.get_full_name() or user.username
        if not attrs.get('customer_email'):
            attrs['customer_email'] = user.email
        if not attrs.get('customer_phone'):
            attrs['customer_phone'] = '9800000000'  # Default phone
        
        return attrs

class PaymentVerifySerializer(serializers.Serializer):
    """Serializer for verifying payment"""
    pidx = serializers.CharField(max_length=255)
    
    def validate_pidx(self, value):
        """Validate pidx exists"""
        try:
            payment = Payment.objects.get(pidx=value)
        except Payment.DoesNotExist:
            raise ValidationError("Invalid payment identifier")
        return value

class SubscriptionCancelSerializer(serializers.Serializer):
    """Serializer for cancelling subscription"""
    immediate = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=500, required=False)

class TrialExtendSerializer(serializers.Serializer):
    """Serializer for extending trial"""
    days = serializers.IntegerField(min_value=1, max_value=30)
    reason = serializers.CharField(max_length=500, required=False)

class RefundInitiateSerializer(serializers.Serializer):
    """Serializer for initiating refund"""
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    reason = serializers.CharField(max_length=500)
    
    def validate_payment_id(self, value):
        """Validate payment exists and can be refunded"""
        try:
            payment = Payment.objects.get(id=value, status=PaymentStatus.COMPLETED)
        except Payment.DoesNotExist:
            raise ValidationError("Invalid or non-completed payment")
        return value
    
    def validate_amount(self, value):
        """Validate refund amount"""
        if value and value <= 0:
            raise ValidationError("Refund amount must be positive")
        return value
    
    def validate(self, attrs):
        """Additional validation"""
        payment = Payment.objects.get(id=attrs['payment_id'])
        
        # Check if full refund amount is specified
        if attrs.get('amount') and attrs['amount'] > payment.amount:
            raise ValidationError("Refund amount cannot exceed payment amount")
        
        # Check if payment is already refunded
        if payment.refund_amount:
            raise ValidationError("Payment is already refunded")
        
        return attrs

class SubscriptionStatsSerializer(serializers.Serializer):
    """Serializer for subscription statistics"""
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    trial_subscriptions = serializers.IntegerField()
    expired_subscriptions = serializers.IntegerField()
    cancelled_subscriptions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    plan_wise_subscriptions = serializers.DictField()
    
class PlanStatsSerializer(serializers.Serializer):
    """Serializer for plan statistics"""
    plan_name = serializers.CharField()
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    trial_subscriptions = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    conversion_rate = serializers.FloatField()

class DashboardSerializer(serializers.Serializer):
    """Serializer for dashboard data"""
    user_subscription = SubscriptionSerializer(allow_null=True)
    available_plans = SubscriptionPlanSerializer(many=True)
    recent_payments = PaymentSerializer(many=True)
    usage_summary = serializers.DictField()
    notifications = serializers.ListField(child=serializers.DictField())
    
class SubscriptionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for subscription list"""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_type = serializers.CharField(source='plan.plan_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    formatted_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan_name', 'plan_type', 'status', 'status_display',
            'formatted_price', 'start_date', 'end_date', 'trial_end_date',
            'auto_renew', 'created_at'
        ]
    
    def get_formatted_price(self, obj):
        return f"Rs. {obj.plan.price:,.2f}"

class PaymentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for payment list"""
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'plan_name', 'amount', 'formatted_amount',
            'status', 'status_display', 'payment_method',
            'created_at', 'completed_at'
        ]
    
    def get_formatted_amount(self, obj):
        return f"Rs. {obj.amount:,.2f}"