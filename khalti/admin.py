# subscription/admin.py
from django.contrib import admin
from .models import (
    SubscriptionPlan, Subscription, Payment,
    SubscriptionUsage, WebhookEvent
)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'duration', 'is_active', 'is_popular', 'sort_order')
    list_filter = ('is_active', 'plan_type', 'duration')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('sort_order', 'price')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date', 'auto_renew')
    list_filter = ('status', 'plan__name', 'auto_renew', 'cancel_at_period_end')
    search_fields = ('user__username', 'user__email', 'plan__name')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at', 'trial_start_date', 'trial_end_date', 'cancelled_at')
    date_hierarchy = 'created_at'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subscription', 'amount', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'currency')
    search_fields = ('user__username', 'pidx', 'khalti_transaction_id')
    raw_id_fields = ('user', 'subscription')
    readonly_fields = ('id', 'created_at', 'updated_at', 'initiated_at', 'completed_at', 'failed_at', 'refunded_at')
    date_hierarchy = 'created_at'

@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'users_count', 'projects_count', 'storage_used_gb', 'last_reset')
    search_fields = ('subscription__user__username',)
    raw_id_fields = ('subscription',)

@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'payment', 'processed', 'created_at')
    list_filter = ('event_type', 'processed')
    search_fields = ('payment__pidx',)
    raw_id_fields = ('payment',)
    readonly_fields = ('id', 'created_at', 'event_data', 'processing_error')
    date_hierarchy = 'created_at'