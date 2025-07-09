# subscription/permissions.py
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from .models import Subscription, Payment

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
        
        # Check ownership based on object type
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False

class IsSubscriptionOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a subscription to access it.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the subscription"""
        # Admin users can access anything
        if request.user.is_staff:
            return True
        
        # For subscription objects
        if isinstance(obj, Subscription):
            return obj.user == request.user
        
        # For payment objects
        if isinstance(obj, Payment):
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
        
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for admin users
        return request.user.is_staff

class CanManageSubscription(permissions.BasePermission):
    """
    Permission to check if user can manage subscription operations.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can manage the subscription"""
        # Admin users can manage anything
        if request.user.is_staff:
            return True
        
        # Users can only manage their own subscriptions
        if isinstance(obj, Subscription):
            return obj.user == request.user
        
        return False

class CanInitiatePayment(permissions.BasePermission):
    """
    Permission to check if user can initiate payments.
    """
    
    def has_permission(self, request, view):
        """Check if user can initiate payment"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has active subscription or is creating new one
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
    Permission to check if user can verify payments.
    """
    
    def has_permission(self, request, view):
        """Check if user can verify payment"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user owns the payment
        pidx = request.data.get('pidx')
        if pidx:
            pass