# subscription/filters.py
import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import Subscription, Payment, SubscriptionStatus, PaymentStatus, PlanType

class SubscriptionFilter(django_filters.FilterSet):
    """Filter for subscriptions"""
    
    # Status filters
    status = django_filters.ChoiceFilter(choices=SubscriptionStatus.choices)
    active = django_filters.BooleanFilter(method='filter_active')
    trial = django_filters.BooleanFilter(method='filter_trial')
    expiring_soon = django_filters.BooleanFilter(method='filter_expiring_soon')
    
    # Plan filters
    plan_type = django_filters.ChoiceFilter(
        field_name='plan__plan_type',
        choices=PlanType.choices
    )
    plan_name = django_filters.CharFilter(
        field_name='plan__name',
        lookup_expr='icontains'
    )
    plan_id = django_filters.UUIDFilter(field_name='plan__id')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    start_date_after = django_filters.DateTimeFilter(
        field_name='start_date',
        lookup_expr='gte'
    )
    start_date_before = django_filters.DateTimeFilter(
        field_name='start_date',
        lookup_expr='lte'
    )
    end_date_after = django_filters.DateTimeFilter(
        field_name='end_date',
        lookup_expr='gte'
    )
    end_date_before = django_filters.DateTimeFilter(
        field_name='end_date',
        lookup_expr='lte'
    )
    
    # User filters
    user_id = django_filters.UUIDFilter(field_name='user__id')
    username = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains'
    )
    user_email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains'
    )
    
    # Auto-renewal filters
    auto_renew = django_filters.BooleanFilter()
    cancel_at_period_end = django_filters.BooleanFilter()
    
    # Trial filters
    trial_used = django_filters.BooleanFilter()
    trial_extended = django_filters.BooleanFilter()
    
    class Meta:
        model = Subscription
        fields = [
            'status', 'plan_type', 'auto_renew', 'cancel_at_period_end',
            'trial_used', 'trial_extended'
        ]
    
    def filter_active(self, queryset, name, value):
        """Filter for active subscriptions"""
        if value:
            now = timezone.now()
            return queryset.filter(
                Q(status=SubscriptionStatus.ACTIVE, end_date__gte=now) |
                Q(status=SubscriptionStatus.TRIAL, trial_end_date__gte=now)
            )
        return queryset
    
    def filter_trial(self, queryset, name, value):
        """Filter for trial subscriptions"""
        if value:
            now = timezone.now()
            return queryset.filter(
                status=SubscriptionStatus.TRIAL,
                trial_start_date__lte=now,
                trial_end_date__gte=now
            )
        return queryset
    
    def filter_expiring_soon(self, queryset, name, value):
        """Filter for subscriptions expiring within 7 days"""
        if value:
            now = timezone.now()
            week_from_now = now + timedelta(days=7)
            return queryset.filter(
                Q(status=SubscriptionStatus.ACTIVE, end_date__lte=week_from_now) |
                Q(status=SubscriptionStatus.TRIAL, trial_end_date__lte=week_from_now)
            )
        return queryset

class PaymentFilter(django_filters.FilterSet):
    """Filter for payments"""
    
    # Status filters
    status = django_filters.ChoiceFilter(choices=PaymentStatus.choices)
    completed = django_filters.BooleanFilter(method='filter_completed')
    failed = django_filters.BooleanFilter(method='filter_failed')
    pending = django_filters.BooleanFilter(method='filter_pending')
    refunded = django_filters.BooleanFilter(method='filter_refunded')
    
    # Amount filters
    amount_min = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='gte'
    )
    amount_max = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='lte'
    )
    amount_range = django_filters.RangeFilter(field_name='amount')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    completed_after = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte'
    )
    completed_before = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte'
    )
    
    # Subscription filters
    subscription_id = django_filters.UUIDFilter(field_name='subscription__id')
    plan_type = django_filters.ChoiceFilter(
        field_name='subscription__plan__plan_type',
        choices=PlanType.choices
    )
    plan_name = django_filters.CharFilter(
        field_name='subscription__plan__name',
        lookup_expr='icontains'
    )
    
    # User filters
    user_id = django_filters.UUIDFilter(field_name='user__id')
    username = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains'
    )
    user_email = django_filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains'
    )
    
    # Payment method filters
    payment_method = django_filters.CharFilter(lookup_expr='icontains')
    currency = django_filters.CharFilter()
    
    # Khalti specific filters
    pidx = django_filters.CharFilter(lookup_expr='icontains')
    khalti_transaction_id = django_filters.CharFilter(lookup_expr='icontains')
    
    # Retry filters
    retry_count_min = django_filters.NumberFilter(
        field_name='retry_count',
        lookup_expr='gte'
    )
    retry_count_max = django_filters.NumberFilter(
        field_name='retry_count',
        lookup_expr='lte'
    )
    
    class Meta:
        model = Payment
        fields = [
            'status', 'payment_method', 'currency', 'retry_count'
        ]
    
    def filter_completed(self, queryset, name, value):
        """Filter for completed payments"""
        if value:
            return queryset.filter(status=PaymentStatus.COMPLETED)
        return queryset
    
    def filter_failed(self, queryset, name, value):
        """Filter for failed payments"""
        if value:
            return queryset.filter(status=PaymentStatus.FAILED)
        return queryset
    
    def filter_pending(self, queryset, name, value):
        """Filter for pending payments"""
        if value:
            return queryset.filter(
                status__in=[PaymentStatus.PENDING, PaymentStatus.INITIATED]
            )
        return queryset
    
    def filter_refunded(self, queryset, name, value):
        """Filter for refunded payments"""
        if value:
            return queryset.filter(status=PaymentStatus.REFUNDED)
        return queryset