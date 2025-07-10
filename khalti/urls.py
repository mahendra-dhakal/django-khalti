# subscription/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
    PaymentViewSet,
    DashboardViewSet,
    WebhookViewSet,
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'webhooks', WebhookViewSet, basename='webhook')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('', include(router.urls)),
]