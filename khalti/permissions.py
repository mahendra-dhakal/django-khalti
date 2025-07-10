# subscription/permissions.py
from rest_framework import permissions
from .models import Subscription, Payment, SubscriptionStatus

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admin users to access it.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user is owner or admin"""
        # Admin users can access anything
        if request.user.is_staff:
            return True

        # Check ownership based on the 'user' attribute of the object
        if hasattr(obj, 'user'):
            return obj.user == request.user

        return False

class IsSubscriptionOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a subscription or related payment to access it.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user owns the subscription or payment"""
        # Admin users can access anything
        if request.user.is_staff:
            return True

        # Check ownership for both Subscription and Payment objects
        if isinstance(obj, (Subscription, Payment)):
            return obj.user == request.user

        return False

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to only allow admin users to edit, but allow read access to authenticated users.
    """

    def has_permission(self, request, view):
        """Check permissions based on request method"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Read permissions are granted for safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only for admin users
        return request.user.is_staff

class CanManageSubscription(permissions.BasePermission):
    """
    Permission to check if a user can manage subscription-specific operations like cancellation.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check if user can manage the subscription"""
        # Admins can manage any subscription
        if request.user.is_staff:
            return True

        # Users can only manage their own subscriptions
        if isinstance(obj, Subscription):
            return obj.user == request.user

        return False

class CanInitiatePayment(permissions.BasePermission):
    """
    Permission to check if a user can initiate a payment for a specific subscription.
    """

    def has_permission(self, request, view):
        """Check if the user can initiate a payment"""
        if not request.user or not request.user.is_authenticated:
            return False

        # For admins, always allow
        if request.user.is_staff:
            return True

        # Check if the subscription_id in the request body belongs to the user
        subscription_id = request.data.get('subscription_id')
        if subscription_id:
            try:
                subscription = Subscription.objects.get(id=subscription_id)
                return subscription.user == request.user
            except Subscription.DoesNotExist:
                return False

        return True

class CanVerifyPayment(permissions.BasePermission):
    """
    Permission to check if a user can verify a payment.
    """

    def has_permission(self, request, view):
        """Check if the user can verify the payment"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admins can verify any payment
        if request.user.is_staff:
            return True

        # Check if the pidx in the request body corresponds to a payment owned by the user
        pidx = request.data.get('pidx')
        if pidx:
            try:
                payment = Payment.objects.get(pidx=pidx)
                return payment.user == request.user
            except Payment.DoesNotExist:
                return False

        return False # Deny by default if pidx is not provided

class HasActiveSubscription(permissions.BasePermission):
    """
    Permission to only allow users with an active or trial subscription to access an endpoint.
    """
    message = 'You do not have an active subscription.'

    def has_permission(self, request, view):
        """Check if the user has an active or trial subscription"""
        if not request.user or not request.user.is_authenticated:
            return False

        # Admins are exempt from this check
        if request.user.is_staff:
            return True

        # Check for a subscription with 'active' or 'trial' status
        return Subscription.objects.filter(
            user=request.user,
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
        ).exists()