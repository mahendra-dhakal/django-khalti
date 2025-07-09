# subscription/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, F
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import logging
import uuid

from .models import (
    SubscriptionPlan, Subscription, Payment, SubscriptionUsage,
    SubscriptionStatus, PaymentStatus, WebhookEvent
)
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionSerializer, PaymentSerializer,
    SubscriptionCreateSerializer, PaymentInitiateSerializer, PaymentVerifySerializer,
    SubscriptionCancelSerializer, TrialExtendSerializer, RefundInitiateSerializer,
    SubscriptionStatsSerializer, DashboardSerializer, SubscriptionListSerializer,
    PaymentListSerializer, SubscriptionUsageSerializer
)
from .services.khalti_service import KhaltiService, KhaltiException
from .filters import SubscriptionFilter, PaymentFilter
from .permissions import IsOwnerOrAdmin, IsSubscriptionOwner
from .utils import generate_order_id, send_payment_notification, create_usage_record

logger = logging.getLogger(__name__)

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for subscription plans"""
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'plan_type']
    ordering_fields = ['price', 'sort_order', 'created_at']
    ordering = ['sort_order', 'price']
    
    def get_queryset(self):
        """Filter plans based on user permissions"""
        queryset = super().get_queryset()
        
        # Non-admin users only see active plans
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular plans"""
        plans = self.get_queryset().filter(is_popular=True)
        serializer = self.get_serializer(plans, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get plans grouped by type"""
        plan_type = request.query_params.get('type')
        if not plan_type:
            return Response(
                {'error': 'Plan type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        plans = self.get_queryset().filter(plan_type=plan_type)
        serializer = self.get_serializer(plans, many=True)
        return Response(serializer.data)

class SubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for user subscriptions"""
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterFilter, SearchFilter, OrderingFilter]
    filterset_class = SubscriptionFilter
    search_fields = ['plan__name', 'status']
    ordering_fields = ['created_at', 'start_date', 'end_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get subscriptions for the current user"""
        if self.request.user.is_staff:
            return Subscription.objects.all().select_related('user', 'plan')
        return Subscription.objects.filter(
            user=self.request.user
        ).select_related('user', 'plan')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return SubscriptionListSerializer
        elif self.action == 'create':
            return SubscriptionCreateSerializer
        elif self.action == 'cancel':
            return SubscriptionCancelSerializer
        elif self.action == 'extend_trial':
            return TrialExtendSerializer
        return super().get_serializer_class()
    
    def perform_create(self, serializer):
        """Create subscription for current user"""
        plan = SubscriptionPlan.objects.get(id=serializer.validated_data['plan_id'])
        
        with transaction.atomic():
            subscription = Subscription.objects.create(
                user=self.request.user,
                plan=plan,
                auto_renew=serializer.validated_data.get('auto_renew', True)
            )
            
            # Start trial if requested
            if serializer.validated_data.get('start_trial', False):
                subscription.start_trial()
            
            # Create usage record
            create_usage_record(subscription)
            
            # Send notification
            send_payment_notification(
                subscription.user,
                'subscription_created',
                {'subscription': subscription}
            )
    
    @action(detail=True, methods=['post'])
    def start_trial(self, request, pk=None):
        """Start free trial for subscription"""
        subscription = self.get_object()
        
        try:
            subscription.start_trial()
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        except ValidationError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        serializer = SubscriptionCancelSerializer(data=request.data)
        
        if serializer.is_valid():
            immediate = serializer.validated_data.get('immediate', False)
            reason = serializer.validated_data.get('reason', '')
            
            try:
                subscription.cancel(immediate=immediate)
                
                # Log cancellation reason
                logger.info(f"Subscription {subscription.id} cancelled: {reason}")
                
                return Response({
                    'message': 'Subscription cancelled successfully',
                    'immediate': immediate
                })
            except ValidationError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def extend_trial(self, request, pk=None):
        """Extend trial period (admin only)"""
        subscription = self.get_object()
        serializer = TrialExtendSerializer(data=request.data)
        
        if serializer.is_valid():
            days = serializer.validated_data['days']
            reason = serializer.validated_data.get('reason', '')
            
            try:
                subscription.extend_trial(days)
                
                # Log extension
                logger.info(f"Trial extended for {subscription.id}: {days} days - {reason}")
                
                return Response({
                    'message': f'Trial extended by {days} days',
                    'new_trial_end': subscription.trial_end_date
                })
            except ValidationError as e:
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew subscription"""
        subscription = self.get_object()
        
        try:
            subscription.renew()
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        except ValidationError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current user's active subscription"""
        try:
            subscription = Subscription.objects.get(
                user=request.user,
                status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
            )
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        except Subscription.DoesNotExist:
            return Response(
                {'message': 'No active subscription found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get subscription statistics (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cache the stats for 1 hour
        cache_key = 'subscription_stats'
        stats = cache.get(cache_key)
        
        if not stats:
            stats = {
                'total_subscriptions': Subscription.objects.count(),
                'active_subscriptions': Subscription.objects.filter(
                    status=SubscriptionStatus.ACTIVE
                ).count(),
                'trial_subscriptions': Subscription.objects.filter(
                    status=SubscriptionStatus.TRIAL
                ).count(),
                'expired_subscriptions': Subscription.objects.filter(
                    status=SubscriptionStatus.EXPIRED
                ).count(),
                'cancelled_subscriptions': Subscription.objects.filter(
                    status=SubscriptionStatus.CANCELLED
                ).count(),
                'total_revenue': Payment.objects.filter(
                    status=PaymentStatus.COMPLETED
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'monthly_revenue': Payment.objects.filter(
                    status=PaymentStatus.COMPLETED,
                    completed_at__gte=timezone.now() - timedelta(days=30)
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'plan_wise_subscriptions': dict(
                    Subscription.objects.values('plan__name')
                    .annotate(count=Count('id'))
                    .values_list('plan__name', 'count')
                )
            }
            cache.set(cache_key, stats, 3600)  # Cache for 1 hour
        
        serializer = SubscriptionStatsSerializer(stats)
        return Response(serializer.data)

class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for payments"""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterFilter, SearchFilter, OrderingFilter]
    filterset_class = PaymentFilter
    search_fields = ['pidx', 'khalti_transaction_id', 'status']
    ordering_fields = ['created_at', 'completed_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get payments for the current user"""
        if self.request.user.is_staff:
            return Payment.objects.all().select_related('user', 'subscription__plan')
        return Payment.objects.filter(
            user=self.request.user
        ).select_related('user', 'subscription__plan')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PaymentListSerializer
        elif self.action == 'initiate':
            return PaymentInitiateSerializer
        elif self.action == 'verify':
            return PaymentVerifySerializer
        elif self.action == 'initiate_refund':
            return RefundInitiateSerializer
        return super().get_serializer_class()
    
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initiate payment with Khalti"""
        serializer = PaymentInitiateSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if serializer.is_valid():
            subscription = Subscription.objects.get(
                id=serializer.validated_data['subscription_id']
            )
            
            # Create payment record
            payment = Payment.objects.create(
                user=request.user,
                subscription=subscription,
                amount=subscription.plan.price,
                currency=subscription.plan.currency,
                pidx=str(uuid.uuid4()),  # Temporary pidx
                status=PaymentStatus.PENDING
            )
            
            try:
                # Initialize Khalti service
                khalti_service = KhaltiService()
                
                # Prepare customer info
                customer_info = {
                    'name': serializer.validated_data['customer_name'],
                    'email': serializer.validated_data['customer_email'],
                    'phone': serializer.validated_data['customer_phone']
                }
                
                # Generate unique order ID
                order_id = generate_order_id(subscription.id)
                
                # Initiate payment with Khalti
                khalti_response = khalti_service.initiate_payment(
                    amount=subscription.plan.price,
                    purchase_order_id=order_id,
                    purchase_order_name=f"Subscription - {subscription.plan.name}",
                    return_url=serializer.validated_data['return_url'],
                    website_url=serializer.validated_data['website_url'],
                    customer_info=customer_info,
                    custom_data={
                        'subscription_id': str(subscription.id),
                        'user_id': str(request.user.id)
                    }
                )
                
                # Update payment with Khalti response
                payment.pidx = khalti_response['pidx']
                payment.khalti_payment_url = khalti_response['payment_url']
                payment.status = PaymentStatus.INITIATED
                payment.initiated_at = timezone.now()
                payment.payment_gateway_response = khalti_response
                payment.save()
                
                logger.info(f"Payment initiated: {payment.id} - {payment.pidx}")
                
                return Response({
                    'payment_id': payment.id,
                    'pidx': payment.pidx,
                    'payment_url': payment.khalti_payment_url,
                    'amount': payment.amount,
                    'currency': payment.currency
                })
                
            except KhaltiException as e:
                payment.mark_as_failed(
                    reason=e.message,
                    gateway_response=e.response_data
                )
                
                logger.error(f"Payment initiation failed: {e.message}")
                
                return Response(
                    {'error': f'Payment initiation failed: {e.message}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                payment.mark_as_failed(reason=str(e))
                
                logger.error(f"Unexpected error during payment initiation: {str(e)}")
                
                return Response(
                    {'error': 'Payment initiation failed. Please try again.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify payment with Khalti"""
        serializer = PaymentVerifySerializer(data=request.data)
        
        if serializer.is_valid():
            pidx = serializer.validated_data['pidx']
            
            try:
                payment = Payment.objects.get(pidx=pidx, user=request.user)
            except Payment.DoesNotExist:
                return Response(
                    {'error': 'Payment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Don't verify already completed payments
            if payment.status == PaymentStatus.COMPLETED:
                return Response({
                    'message': 'Payment already verified',
                    'payment_id': payment.id,
                    'status': payment.status
                })
            
            try:
                # Verify payment with Khalti
                khalti_service = KhaltiService()
                verification_response = khalti_service.verify_payment(pidx)
                
                if verification_response.get('status') == 'Completed':
                    # Mark payment as completed
                    payment.mark_as_completed(
                        transaction_id=verification_response.get('transaction_id'),
                        gateway_response=verification_response
                    )
                    
                    # Send notification
                    send_payment_notification(
                        payment.user,
                        'payment_completed',
                        {'payment': payment}
                    )
                    
                    logger.info(f"Payment verified successfully: {payment.id}")
                    
                    return Response({
                        'message': 'Payment verified successfully',
                        'payment_id': payment.id,
                        'status': payment.status,
                        'transaction_id': payment.khalti_transaction_id
                    })
                else:
                    # Payment not completed yet
                    return Response({
                        'message': 'Payment verification pending',
                        'payment_id': payment.id,
                        'status': verification_response.get('status'),
                        'can_retry': True
                    })
                    
            except KhaltiException as e:
                payment.mark_as_failed(
                    reason=e.message,
                    gateway_response=e.response_data
                )
                
                logger.error(f"Payment verification failed: {e.message}")
                
                return Response(
                    {'error': f'Payment verification failed: {e.message}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error during payment verification: {str(e)}")
                
                return Response(
                    {'error': 'Payment verification failed. Please try again.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry failed payment"""
        payment = self.get_object()
        
        if not payment.can_retry():
            return Response(
                {'error': 'Payment cannot be retried'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Increment retry count
            payment.retry_count += 1
            payment.status = PaymentStatus.PENDING
            payment.save()
            
            # Re-initiate payment (you might want to implement this logic)
            # For now, just return success
            return Response({
                'message': 'Payment retry initiated',
                'payment_id': payment.id,
                'retry_count': payment.retry_count
            })
            
        except Exception as e:
            logger.error(f"Payment retry failed: {str(e)}")
            return Response(
                {'error': 'Payment retry failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def initiate_refund(self, request, pk=None):
        """Initiate refund for payment (admin only)"""
        payment = self.get_object()
        serializer = RefundInitiateSerializer(data=request.data)
        
        if serializer.is_valid():
            amount = serializer.validated_data.get('amount')
            reason = serializer.validated_data['reason']
            
            try:
                # Initiate refund with Khalti
                khalti_service = KhaltiService()
                refund_response = khalti_service.initiate_refund(
                    pidx=payment.pidx,
                    amount=amount,
                    reason=reason
                )
                
                # Update payment with refund info
                payment.refund_amount = amount or payment.amount
                payment.refund_reason = reason
                payment.refunded_at = timezone.now()
                payment.status = PaymentStatus.REFUNDED
                payment.payment_gateway_response.update({
                    'refund_data': refund_response
                })
                payment.save()
                
                # Send notification
                send_payment_notification(
                    payment.user,
                    'refund_initiated',
                    {'payment': payment}
                )
                
                logger.info(f"Refund initiated: {payment.id} - Amount: {payment.refund_amount}")
                
                return Response({
                    'message': 'Refund initiated successfully',
                    'refund_id': refund_response.get('refund_id'),
                    'amount': payment.refund_amount
                })
                
            except KhaltiException as e:
                logger.error(f"Refund initiation failed: {e.message}")
                
                return Response(
                    {'error': f'Refund initiation failed: {e.message}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error during refund initiation: {str(e)}")
                
                return Response(
                    {'error': 'Refund initiation failed. Please try again.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DashboardViewSet(viewsets.ViewSet):
    """ViewSet for dashboard data"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get dashboard data for current user"""
        user = request.user
        
        # Get user's current subscription
        try:
            current_subscription = Subscription.objects.get(
                user=user,
                status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
            )
        except Subscription.DoesNotExist:
            current_subscription = None
        
        # Get available plans
        available_plans = SubscriptionPlan.objects.filter(
            is_active=True
        ).order_by('sort_order', 'price')
        
        # Get recent payments
        recent_payments = Payment.objects.filter(
            user=user
        ).order_by('-created_at')[:5]
        
        # Get usage summary
        usage_summary = {}
        if current_subscription:
            try:
                usage = current_subscription.usage
                usage_summary = {
                    'users': {
                        'current': usage.users_count,
                        'limit': current_subscription.plan.max_users,
                        'percentage': (usage.users_count / current_subscription.plan.max_users) * 100
                    },
                    'projects': {
                        'current': usage.projects_count,
                        'limit': current_subscription.plan.max_projects,
                        'percentage': (usage.projects_count / current_subscription.plan.max_projects) * 100
                    },
                    'storage': {
                        'current': float(usage.storage_used_gb),
                        'limit': current_subscription.plan.storage_limit_gb,
                        'percentage': (float(usage.storage_used_gb) / current_subscription.plan.storage_limit_gb) * 100
                    }
                }
            except SubscriptionUsage.DoesNotExist:
                usage_summary = {}
        
        # Get notifications
        notifications = []
        if current_subscription:
            # Check for expiring subscription
            if current_subscription.is_trial_active():
                days_left = current_subscription.days_until_expiry()
                if days_left <= 3:
                    notifications.append({
                        'type': 'warning',
                        'message': f'Your trial expires in {days_left} days',
                        'action': 'upgrade'
                    })
            elif current_subscription.status == SubscriptionStatus.ACTIVE:
                days_left = current_subscription.days_until_expiry()
                if days_left <= 7:
                    notifications.append({
                        'type': 'info',
                        'message': f'Your subscription expires in {days_left} days',
                        'action': 'renew'
                    })
            
            # Check for usage limits
            if current_subscription.usage:
                usage = current_subscription.usage
                if usage.is_over_limit('users'):
                    notifications.append({
                        'type': 'error',
                        'message': 'You have exceeded your user limit',
                        'action': 'upgrade'
                    })
                if usage.is_over_limit('projects'):
                    notifications.append({
                        'type': 'error',
                        'message': 'You have exceeded your project limit',
                        'action': 'upgrade'
                    })
                if usage.is_over_limit('storage'):
                    notifications.append({
                        'type': 'error',
                        'message': 'You have exceeded your storage limit',
                        'action': 'upgrade'
                    })
        
        # Prepare dashboard data
        dashboard_data = {
            'user_subscription': current_subscription,
            'available_plans': available_plans,
            'recent_payments': recent_payments,
            'usage_summary': usage_summary,
            'notifications': notifications
        }
        
        serializer = DashboardSerializer(dashboard_data)
        return Response(serializer.data)

class WebhookViewSet(viewsets.ViewSet):
    """ViewSet for handling Khalti webhooks"""
    permission_classes = []  # No authentication required for webhooks
    
    def create(self, request):
        """Handle Khalti webhook events"""
        try:
            event_data = request.data
            event_type = event_data.get('type')
            
            # Create webhook event record
            webhook_event = WebhookEvent.objects.create(
                event_type=event_type,
                event_data=event_data
            )
            
            logger.info(f"Webhook received: {event_type} - {webhook_event.id}")
            
            # Process webhook based on event type
            if event_type == 'payment.completed':
                self._handle_payment_completed(webhook_event)
            elif event_type == 'payment.failed':
                self._handle_payment_failed(webhook_event)
            elif event_type == 'refund.completed':
                self._handle_refund_completed(webhook_event)
            else:
                logger.warning(f"Unhandled webhook event type: {event_type}")
            
            # Mark webhook as processed
            webhook_event.processed = True
            webhook_event.save()
            
            return Response({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            
            # Mark webhook as failed
            if 'webhook_event' in locals():
                webhook_event.processing_error = str(e)
                webhook_event.save()
            
            return Response(
                {'error': 'Webhook processing failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_payment_completed(self, webhook_event):
        """Handle payment completed webhook"""
        try:
            event_data = webhook_event.event_data
            pidx = event_data.get('pidx')
            
            if not pidx:
                logger.error("No pidx in payment completed webhook")
                return
            
            payment = Payment.objects.get(pidx=pidx)
            
            if payment.status != PaymentStatus.COMPLETED:
                payment.mark_as_completed(
                    transaction_id=event_data.get('transaction_id'),
                    gateway_response=event_data
                )
                
                # Send notification
                send_payment_notification(
                    payment.user,
                    'payment_completed',
                    {'payment': payment}
                )
                
                logger.info(f"Payment completed via webhook: {payment.id}")
            
            webhook_event.payment = payment
            webhook_event.save()
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for pidx: {pidx}")
        except Exception as e:
            logger.error(f"Error handling payment completed webhook: {str(e)}")
            raise
    
    def _handle_payment_failed(self, webhook_event):
        """Handle payment failed webhook"""
        try:
            event_data = webhook_event.event_data
            pidx = event_data.get('pidx')
            
            if not pidx:
                logger.error("No pidx in payment failed webhook")
                return
            
            payment = Payment.objects.get(pidx=pidx)
            
            if payment.status != PaymentStatus.FAILED:
                payment.mark_as_failed(
                    reason=event_data.get('failure_reason', 'Payment failed'),
                    gateway_response=event_data
                )
                
                # Send notification
                send_payment_notification(
                    payment.user,
                    'payment_failed',
                    {'payment': payment}
                )
                
                logger.info(f"Payment failed via webhook: {payment.id}")
            
            webhook_event.payment = payment
            webhook_event.save()
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for pidx: {pidx}")
        except Exception as e:
            logger.error(f"Error handling payment failed webhook: {str(e)}")
            raise
    
    def _handle_refund_completed(self, webhook_event):
        """Handle refund completed webhook"""
        try:
            event_data = webhook_event.event_data
            pidx = event_data.get('pidx')
            
            if not pidx:
                logger.error("No pidx in refund completed webhook")
                return
            
            payment = Payment.objects.get(pidx=pidx)
            
            # Update refund status
            payment.status = PaymentStatus.REFUNDED
            payment.refunded_at = timezone.now()
            payment.payment_gateway_response.update({
                'refund_webhook_data': event_data
            })
            payment.save()
            
            # Send notification
            send_payment_notification(
                payment.user,
                'refund_completed',
                {'payment': payment}
            )
            
            logger.info(f"Refund completed via webhook: {payment.id}")
            
            webhook_event.payment = payment
            webhook_event.save()
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for pidx: {pidx}")
        except Exception as e:
            logger.error(f"Error handling refund completed webhook: {str(e)}")
            raise