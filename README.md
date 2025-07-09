# django-khalti
integrating khalti payment into django restframework

A Comprehensive Guide to Integrating Khalti Payments and Subscriptions in Django REST FrameworkPart I: Foundational Concepts of Payment Gateway IntegrationBefore embarking on the technical implementation of a payment gateway, it is imperative to establish a solid conceptual understanding of the systems and principles at play. Integrating payments is not merely about writing code; it is about securely orchestrating a complex sequence of events involving multiple financial institutions, all while safeguarding sensitive user data. This section demystifies the online transaction process, analyzes the specific architectural model employed by Khalti, and establishes the single most important principle for a secure integration: authoritative server-side verification.Section 1.1: The Anatomy of an Online TransactionAn online payment transaction, which appears instantaneous to a user, is in reality a sophisticated dialogue between several distinct entities. A payment gateway serves as the critical bridge, or intermediary, connecting the merchant's application to this complex financial network.1 Understanding the role of each participant is fundamental to grasping the logic of the integration process.The primary actors in a typical online card transaction include:The Customer (or Cardholder): The individual initiating the purchase on the merchant's website or application.3The Merchant: The business providing the goods or services. In this context, the merchant is your Django REST Framework application.3The Payment Gateway: A technology service that captures and securely transmits payment data from the customer to the payment processor. It encrypts sensitive information, such as credit card details, and facilitates the authorization request.1 Khalti serves this role in our implementation.The Payment Processor: A company that handles the transaction processing. It communicates transaction information between the merchant, the issuing bank, and the acquiring bank.5The Acquiring Bank: The merchant's bank, which is responsible for receiving payment on behalf of the merchant. It requests transaction authorization from the customer's bank via the card networks (e.g., Visa, Mastercard).4The Issuing Bank: The customer's bank, which issued the credit or debit card. This bank is responsible for verifying the customer's identity, checking for sufficient funds, and approving or declining the transaction request.4The general workflow of a transaction unfolds in a series of steps, as illustrated below:Transaction Initiation: A customer selects a product on your Django application's frontend and proceeds to checkout, where they enter their payment information.1Encryption: The payment gateway securely encrypts this sensitive data using protocols like SSL/TLS. This is a crucial step to protect the information from interception or theft as it travels across the internet.1Authorization Request: The gateway forwards the encrypted transaction details to the payment processor, which then routes the request through the appropriate card network to the customer's issuing bank.4Verification and Authorization: The issuing bank performs fraud checks and verifies if the customer has sufficient funds. It then sends an approval or decline response back through the same chain: to the card network, the processor, and finally to the payment gateway.1Communication of Status: The payment gateway communicates the final transaction status (e.g., "Approved" or "Declined") back to the merchant's application. The application then displays an appropriate message to the customer and, if approved, proceeds with order fulfillment.1Settlement: Later, typically in a batch process, the funds are transferred from the issuing bank to the acquiring bank, which then deposits the money into the merchant's account. This part of the process is handled by the processor and banks and is generally abstracted away from the developer's immediate concern during integration.6The core value proposition of using a payment gateway API is that it abstracts this immense complexity.8 As a developer, you do not need to build direct, secure integrations with dozens of different banks or manage raw credit card data, a task that carries a heavy burden of security and regulatory compliance (such as PCI DSS).2 Instead, your responsibility shifts from handling sensitive financial data to securely communicating with the gateway's API, which handles the intricacies of the financial network on your behalf.Section 1.2: Integration Architecture: The Khalti Web Checkout ModelPayment gateways offer various integration models, each with different implications for user experience and developer responsibility.10 Khalti's primary method for web applications, known as "Web Checkout," is best classified as a redirect-based or hosted payment gateway model.11In this model, the customer is redirected away from the merchant's website to a secure page hosted by the payment gateway itself to enter their payment details. After the transaction is complete, the user is redirected back to a pre-specified URL on the merchant's site.10 The official Khalti documentation outlines this precise flow 12:Initiation: The merchant's backend server makes a secure API request to Khalti to initiate a payment.Redirection URL: Khalti's system responds with a unique payment identifier (pidx) and a payment_url.User Redirect: The merchant's application must redirect the user's browser to this payment_url. The user is now on a page controlled and secured by Khalti.Payment Completion: The user enters their payment details (Khalti wallet, eBanking credentials, etc.) and completes the payment on Khalti's platform.Callback Redirect: After payment, Khalti redirects the user back to the return_url that the merchant specified during the initiation step. This URL will have several query parameters appended to it, including the pidx and a preliminary transaction status.This redirect model offers a significant security advantage: your application's servers never see, handle, or store the user's sensitive payment credentials (like their Khalti MPIN or bank password). This greatly reduces your application's PCI compliance scope.10However, a critical nuance in Khalti's architecture distinguishes it from simpler hosted gateways. The process is not complete when the user returns to your site. The Khalti documentation explicitly states: "Merchant side must hit the lookup API to get the status of the transaction".12 This requirement creates a hybrid architectural model. It combines the user-facing simplicity and security of a redirect for data collection with the backend robustness of a direct API integration for confirmation. This two-part interaction—one API call to start the process and a second, separate API call to definitively confirm it—is a crucial architectural pattern that must be correctly implemented for a secure and reliable system. The potential for confusion around this two-step process is high and is a likely reason why developers find the documentation challenging.Section 1.3: The Principle of Authoritative Server-Side VerificationThis brings us to the single most important principle in any payment gateway integration: the client-side can never be trusted as the final authority on a transaction's status.When Khalti redirects the user back to your application's return_url, it includes query parameters like status=Completed.13 A naive or inexperienced developer might be tempted to parse this URL parameter in the browser and, upon seeing "Completed," immediately grant the user their purchased subscription or mark an order as paid. This would be a critical security vulnerability. A malicious user could easily manipulate the URL, or a simple network error could prevent the user from being redirected correctly even after a successful payment.The only reliable way to confirm a transaction's true state is for your backend server to make a direct, authenticated API call to the payment gateway. This is known as server-side verification or a lookup. Khalti's documentation strongly recommends this practice: "It's recommended that during implementation, payment lookup API is checked for confirmation after the redirect callback is received".13This principle is rooted in the fact that the definitive record of the transaction—the "source of truth"—resides on the secure servers of the payment gateway and the associated financial institutions.6 This truth is only accessible via a secure, authenticated channel, which is the server-to-server API call using your secret key.14Therefore, the result of this server-side verification call is the only trigger that should ever be allowed to alter your application's state. It is the only event that should cause your application to perform actions such as:Creating a UserSubscription record in the database.Marking an e-commerce order's status as 'Paid'.Granting a user access to premium features.Initiating a product delivery workflow.The user's return to the client-side return_url should be treated as nothing more than a signal that a transaction attempt has concluded. The frontend's role at this stage is to display a temporary message (e.g., "Thank you, we are verifying your payment...") and to pass the pidx received in the URL to the backend, which will then perform the authoritative verification. This decoupling of the user's browser experience from the application's state change logic is the cornerstone of a robust, secure, and reliable payment system.Part II: Environment and Project ConfigurationA professional and secure application begins with a well-structured and properly configured development environment. This section provides a step-by-step guide to setting up the Django project, creating the necessary subscriptions app, navigating the Khalti sandbox environment to obtain API keys, and, most importantly, implementing the industry-standard practice of managing secret credentials using environment variables.Section 2.1: Structuring the Django Project and Subscription AppWe will begin by creating the foundational structure for our project. This involves initializing a Python virtual environment to isolate our project's dependencies, installing the required packages, and creating the Django project and app.Create Project Directory and Virtual Environment:Open your terminal, navigate to where you store your projects, and run the following commands:Bashmkdir khalti_project_tutorial
cd khalti_project_tutorial
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
Install Dependencies:With the virtual environment active, install Django, Django REST Framework, and the requests library, which we will use for making server-to-server API calls to Khalti.Bashpip install django djangorestframework requests python-dotenv
The python-dotenv package will be used for securely managing our API keys, as detailed in Section 2.3.Create Django Project and App:Now, create the main Django project and the subscriptions app that will house our payment and subscription logic.Bashdjango-admin startproject core.
python manage.py startapp subscriptions
The . at the end of the startproject command creates the project in the current directory, which is a common convention.Configure settings.py:Open core/settings.py and add rest_framework and our new subscriptions app to the INSTALLED_APPS list.15Python# core/settings.py

INSTALLED_APPS =
Configure Project URLs:Next, we need to include the URLs from our subscriptions app into the main project's URL configuration. Open core/urls.py and modify it as follows 16:Python# core/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/subscriptions/', include('subscriptions.urls')), # New
]
Then, create a new file subscriptions/urls.py to hold the app-specific URL patterns. We will populate this file later.Python# subscriptions/urls.py

from django.urls import path
from. import views

urlpatterns = [
    # We will add our API endpoints here later
]
Section 2.2: The Khalti Sandbox EnvironmentKhalti provides a fully-featured sandbox (or test) environment that allows developers to integrate and test the entire payment flow without using real money or requiring official business registration documents.12 This is an essential tool for development.Sign Up for a Test Merchant Account:Navigate to the Khalti sandbox signup page: https://dev.khalti.com/ (or the specific merchant signup link provided in their docs 12). You can use placeholder information for the signup process as it's for testing purposes only.17Locate Your API Keys:Once you have created your test merchant account and logged in to the sandbox dashboard, navigate to the "Keys" section. Here you will find two critical pieces of information: your Public Key and your Secret Key.18These two keys serve distinct and separate purposes. Understanding their roles is crucial to avoid security vulnerabilities.Key NameAlso Known AsPurposeWhere to Use ItSecurity LevelPublic KeyClient-Side Authorization Key 12Identifies your merchant account in client-side requests. It is used by the Khalti frontend components.This key is used in the frontend JavaScript that initiates the payment process. For mobile SDKs, it's the client-side key.Public. It is safe to expose this key in your frontend code (HTML/JavaScript).Secret KeyServer-Side Authorization Key, API Key 12Authenticates your application's backend server for secure, server-to-server API calls (like initiation and verification).This key is used in the Authorization header of API requests made from your Django backend to Khalti's servers.Secret. This key must NEVER be exposed in frontend code or committed to version control. It is equivalent to a password.Test Credentials:For testing payments in the sandbox environment, Khalti provides a set of test credentials that can be used on the payment page 12:Test Khalti ID (Mobile Number): 9800000000 (and several others listed in the docs)Test MPIN: 1111Test OTP (One-Time Password): 987654Section 2.3: Secure Credential Management with Environment VariablesHardcoding sensitive information like your Khalti Secret Key directly into your settings.py file is a severe security risk. If your code is ever committed to a public repository (even accidentally), your secret key will be exposed, allowing attackers to make API calls on behalf of your merchant account.21The industry-standard best practice is to store such secrets in environment variables. These are variables that exist outside of your application's code and are loaded into the application at runtime.21 This practice ensures a clean separation between code and configuration.We will use the python-dotenv library to facilitate this process for local development.23Create the .env file:In the root directory of your project (the same level as manage.py), create a file named .env.khalti_project_tutorial/
├── core/
├── subscriptions/
├── venv/
├──.env         <-- Create this file
└── manage.py
Add Secrets to .env:Open the .env file and add your Khalti Secret Key and the API URLs. Do not use quotes around the values.22Code snippet#.env

KHALTI_SECRET_KEY=your_test_secret_key_from_the_dashboard
KHALTI_INITIATE_URL=https://dev.khalti.com/api/v2/epayment/initiate/
KHALTI_VERIFY_URL=https://dev.khalti.com/api/v2/epayment/verify/
Note: For a live application, the URLs would change to https://khalti.com/....12Ignore the .env file in Version Control:This is a critical step. To prevent Git from ever tracking your .env file, create a .gitignore file in your project's root directory and add .env to it.Bashecho ".env" >>.gitignore
echo "venv/" >>.gitignore
This ensures your secret credentials will not be uploaded to GitHub or any other version control system.21Load Environment Variables in settings.py:Now, modify core/settings.py to load these variables from the .env file. Add the following lines near the top of the file.23Python# core/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv # Add this import

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from.env file
load_dotenv(os.path.join(BASE_DIR, '.env')) # Add this line

#... other settings...

# Khalti Configuration
KHALTI_SECRET_KEY = os.getenv('KHALTI_SECRET_KEY')
KHALTI_INITIATE_URL = os.getenv('KHALTI_INITIATE_URL')
KHALTI_VERIFY_URL = os.getenv('KHALTI_VERIFY_URL')
By adopting this approach from the very beginning, you are not just completing a tutorial step; you are establishing a fundamental professional habit. Securely managing secrets is a non-negotiable requirement for any real-world application, and treating it as a foundational part of the project setup will prevent critical security flaws in all your future work.Part III: Developing the Subscription Backend with DRFWith the project environment configured, we now turn to the core of the application: the Django backend. This part will guide you through creating the data models to represent subscriptions, the serializers to translate that data into API-friendly formats, and the crucial API endpoints that will orchestrate the payment initiation and verification processes with Khalti.Section 3.1: Data Modeling for SubscriptionsFirst, we need to define the database structure that will store information about our subscription plans and the status of each user's subscription. We will create two primary models in subscriptions/models.py.A key architectural consideration is that Khalti's API, as described in the available documentation, provides a mechanism for one-time payments, not a native, automated recurring billing system like those offered by providers such as Stripe.12 This means our application must manage the subscription lifecycle itself. A payment will grant a user access for a fixed duration (e.g., 30 days). The UserSubscription model must be designed to reflect this "manual" subscription management.Open subscriptions/models.py and add the following code:Python# subscriptions/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class SubscriptionPlan(models.Model):
    """
    Model to store different subscription plans available (e.g., Basic, Premium).
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Price in NPR
    duration_days = models.PositiveIntegerField(default=30, help_text="Duration of the subscription in days.")

    def __str__(self):
        return f"{self.name} - Rs. {self.price} for {self.duration_days} days"

class Transaction(models.Model):
    """
    Model to store details of each Khalti transaction.
    This helps in tracking and ensuring idempotency.
    """
    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    khalti_pidx = models.CharField(max_length=255, unique=True, help_text="Khalti Payment ID (pidx)")
    khalti_transaction_id = models.CharField(max_length=255, null=True, blank=True, help_text="Khalti Transaction ID (tidx)")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in NPR")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_response = models.JSONField(null=True, blank=True, help_text="Raw response from Khalti verification")

    def __str__(self):
        return f"Transaction {self.khalti_pidx} for {self.user.username if self.user else 'Anonymous'}"

class UserSubscription(models.Model):
    """
    Model to track a user's subscription status.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='user_subscription')

    def __str__(self):
        return f"{self.user.username}'s subscription to {self.plan.name}"

    @property
    def is_active(self):
        """
        A property to check if the subscription is currently active.
        The source of truth is the current time being between start and end dates.
        """
        return self.end_date > timezone.now()
Model Breakdown:SubscriptionPlan: This is a simple model to define the products you are selling. It stores the name, price (in Nepalese Rupees, NPR), and duration.Transaction: This model is crucial for robust integration. It stores a record for every payment attempt initiated with Khalti. Storing the khalti_pidx and the final khalti_transaction_id allows us to track payments and, critically, to implement idempotency (preventing a single payment from being processed twice). We also store the final verification response from Khalti for auditing and debugging purposes.UserSubscription: This model represents an active subscription for a user. It links a User to a SubscriptionPlan and has a defined start_date and end_date. The is_active property provides a clean, calculated way to check if the subscription is valid at any given moment. This logic—calculating is_active based on a fixed duration—is a direct consequence of Khalti not having a native recurring billing system that would manage this state externally.10After defining your models, create and apply the database migrations:Bashpython manage.py makemigrations
python manage.py migrate
Section 3.2: Serializing Data for the APIDjango REST Framework uses serializers to control how complex data types, like Django model instances, are converted to and from native Python datatypes that can then be easily rendered into JSON.15Create a new file subscriptions/serializers.py and add the following code:Python# subscriptions/serializers.py

from rest_framework import serializers
from.models import SubscriptionPlan, UserSubscription

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'description', 'price', 'duration_days']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = ['plan', 'start_date', 'end_date', 'is_active']
SubscriptionPlanSerializer: This will be used to provide a list of available plans to the frontend.UserSubscriptionSerializer: This will be used to show a user their current subscription details. It includes the nested plan details and the is_active property for convenience.Section 3.3: The Payment Initiation API EndpointThis is the first of our two critical API endpoints. Its job is to receive a request from the frontend indicating which plan the user wants to buy, and then to communicate with Khalti's server to generate a payment URL.We will build this using DRF's APIView class, which gives us fine-grained control over the request-response cycle.25Open subscriptions/views.py and add the following code:Python# subscriptions/views.py

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from.models import SubscriptionPlan, Transaction
from.serializers import SubscriptionPlanSerializer
import requests
import uuid

class SubscriptionPlanListView(APIView):
    """
    API view to list all available subscription plans.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class InitiatePaymentView(APIView):
    """
    API view to initiate a payment with Khalti.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"error": "plan_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        # A unique ID for our internal purchase record
        purchase_order_id = str(uuid.uuid4())
        amount_paisa = int(plan.price * 100) # Convert NPR to Paisa

        # Create a transaction record in our database
        transaction = Transaction.objects.create(
            user=request.user,
            plan=plan,
            khalti_pidx=purchase_order_id, # Initially use our ID, will be updated with Khalti's pidx
            amount=plan.price,
            status='initiated'
        )

        # The payload required by Khalti's initiation API
        payload = {
            "return_url": "http://localhost:8000/payment-success/", # Replace with your frontend success URL
            "website_url": "http://localhost:8000/", # Replace with your site's URL
            "amount": amount_paisa,
            "purchase_order_id": purchase_order_id,
            "purchase_order_name": f"Subscription to {plan.name}",
            "customer_info": {
                "name": request.user.get_full_name() or request.user.username,
                "email": request.user.email,
            }
        }

        # The headers for the Khalti API request
        headers = {
            "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            # Make the server-to-server request to Khalti
            response = requests.post(settings.KHALTI_INITIATE_URL, json=payload, headers=headers)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            
            khalti_response = response.json()
            
            # Update our transaction record with the pidx from Khalti
            transaction.khalti_pidx = khalti_response.get('pidx')
            transaction.save()

            return Response(khalti_response, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            transaction.status = 'failed'
            transaction.save()
            # Log the error e
            return Response({"error": "Could not connect to payment gateway."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            transaction.status = 'failed'
            transaction.save()
            # Log the error e
            return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

View Breakdown:SubscriptionPlanListView: A simple read-only endpoint that returns a list of all available plans. This will populate our frontend selection page.InitiatePaymentView:It requires the user to be authenticated (permission_classes).It expects a plan_id in the POST request body.It retrieves the corresponding SubscriptionPlan from the database.Crucially, it converts the price from NPR to paisa (plan.price * 100), as required by the Khalti API.13It creates an initial Transaction record in our database with a status of 'initiated'. This gives us an audit trail from the very start.It constructs the payload dictionary and headers exactly as specified by the Khalti documentation.13It uses the requests library to make a POST request to the Khalti initiation URL.Upon a successful response from Khalti, it updates our local Transaction record with the pidx returned by Khalti and forwards Khalti's response (containing the payment_url) to our frontend.It includes error handling for network issues or unexpected errors.To make these views accessible, update subscriptions/urls.py:Python# subscriptions/urls.py

from django.urls import path
from.views import SubscriptionPlanListView, InitiatePaymentView

urlpatterns =
The table below summarizes the fields for the Khalti initiation payload for quick reference.Field NameRequired?Data TypeDescriptionExample Valuereturn_urlYesString (URL)The URL where the user is redirected after payment completion."http://localhost:8000/payment-success/"website_urlYesString (URL)The root URL of your website."http://localhost:8000/"amountYesIntegerTotal amount to be paid. Crucial: Must be in paisa (NPR * 100).1350000 (for Rs. 500.00)purchase_order_idYesStringA unique identifier for the purchase from the merchant's system."sub-plan-1-user-5-timestamp"purchase_order_nameYesStringA descriptive name for the purchase."Premium Plan - Monthly"customer_infoNoObjectAn object containing customer details like name, email, and phone.{"name": "Test User", "email": "test@example.com"}amount_breakdownNoArray of ObjectsAn array to show a breakdown of the total amount.``Section 3.4: The Payment Verification API EndpointThis is the most security-critical part of the backend. This endpoint will be called by our frontend after the user returns from the Khalti payment page. It will receive the pidx and use it to perform the authoritative server-side verification.Add the following VerifyPaymentView to subscriptions/views.py:Python# subscriptions/views.py (add to existing file)

from django.utils import timezone
from datetime import timedelta
from.models import SubscriptionPlan, Transaction, UserSubscription
#... other imports

class VerifyPaymentView(APIView):
    """
    API view to verify a Khalti payment and activate a subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        pidx = request.data.get('pidx')
        if not pidx:
            return Response({"error": "pidx is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(khalti_pidx=pidx, user=request.user)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        # Idempotency Check: If transaction is already completed, don't process again.
        if transaction.status == 'completed':
            return Response({"status": "success", "message": "Payment has already been verified."}, status=status.HTTP_200_OK)

        # Payload for Khalti's verification API
        payload = {
            "pidx": pidx,
        }
        
        headers = {
            "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            # Make the server-to-server verification request to Khalti
            response = requests.post(settings.KHALTI_VERIFY_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            khalti_response = response.json()
            
            # Store the raw verification response for auditing
            transaction.raw_response = khalti_response
            
            # Handle different statuses from Khalti
            khalti_status = khalti_response.get('status', '').lower()
            
            if khalti_status == 'completed':
                transaction.status = 'completed'
                transaction.khalti_transaction_id = khalti_response.get('transaction_id')
                transaction.save()

                # Activate the user's subscription
                self.activate_subscription(transaction)
                
                return Response({
                    "status": "success", 
                    "message": "Payment verified successfully and subscription activated."
                }, status=status.HTTP_200_OK)
            
            else:
                # Handle other statuses like 'pending', 'refunded', 'user canceled', etc.
                transaction.status = khalti_status if khalti_status in [c for c in Transaction.STATUS_CHOICES] else 'failed'
                transaction.save()
                return Response({
                    "status": "failed", 
                    "message": f"Payment status is '{khalti_status}'. Please contact support."
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            # Log the error e
            return Response({"error": "Could not connect to payment gateway for verification."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            # Log the error e
            return Response({"error": "An unexpected error occurred during verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def activate_subscription(self, transaction):
        """
        Activates or updates the user's subscription based on the successful transaction.
        """
        user = transaction.user
        plan = transaction.plan
        
        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)

        # Use update_or_create to handle both new and renewing subscribers
        UserSubscription.objects.update_or_create(
            user=user,
            defaults={
                'plan': plan,
                'start_date': start_date,
                'end_date': end_date,
                'transaction': transaction
            }
        )
View Breakdown:It receives the pidx from the frontend.It retrieves our corresponding Transaction record.Idempotency Check: It checks if this transaction has already been marked as 'completed'. If so, it returns a success message without processing again, preventing duplicate subscription grants.28It constructs the payload and headers for the verification request, including the crucial Authorization: Key <secret_key> header.14It makes the requests.post call to Khalti's verification endpoint.It carefully checks the status field in Khalti's JSON response. This is where we implement the logic from our "Source of Truth" principle.If the status is 'Completed', it updates our local transaction record, saves the final khalti_transaction_id, and calls a helper method activate_subscription.The activate_subscription method creates or updates the UserSubscription record, setting the start_date and calculating the end_date based on the plan's duration.If the status from Khalti is anything other than 'Completed', it updates our local record with the failure status and returns an appropriate error message to the frontend.A robust application must be prepared to handle all possible states returned by the verification API. The following table outlines a clear action plan for each status.Khalti Status 13MeaningDjango ActionFrontend ActionCompletedThe payment was successful and has been confirmed by Khalti.Update Transaction.status to 'completed'. Create/update UserSubscription record. Return HTTP 200.Display a success message and redirect the user to their dashboard.PendingThe transaction is in progress but not yet confirmed.Update Transaction.status to 'pending'. Do NOT grant subscription. Return HTTP 400.Display "Your payment is pending. We will notify you upon completion."InitiatedThe transaction was started but not completed by the user.Update Transaction.status to 'failed'. Do NOT grant subscription. Return HTTP 400.Display "Your payment was not completed. Please try again."RefundedThe transaction was successfully refunded.Update Transaction.status to 'refunded'. Ensure UserSubscription is inactive. Return HTTP 400.Display "This transaction has been refunded."User canceledThe user explicitly canceled the payment process.Update Transaction.status to 'failed'. Do NOT grant subscription. Return HTTP 400.Display "You have canceled the payment."ExpiredThe payment session expired before completion.Update Transaction.status to 'failed'. Do NOT grant subscription. Return HTTP 400.Display "Your payment session has expired. Please try again."Finally, add the URL for this new view in subscriptions/urls.py:Python# subscriptions/urls.py (add to existing file)

from.views import SubscriptionPlanListView, InitiatePaymentView, VerifyPaymentView

urlpatterns =
Section 3.5: Managing the User-Facing CallbackThe return_url we specified in the initiation call needs to point to an actual page in our application. This page's primary role is to host the JavaScript that will call our verification API. We will create a simple Django template view for this.First, create a new view in subscriptions/views.py:Python# subscriptions/views.py (add to existing file)
from django.shortcuts import render

def payment_success_view(request):
    """
    A simple view to render the page the user is redirected to after Khalti.
    This page will contain the JavaScript to call our verification API.
    """
    return render(request, 'subscriptions/payment_success.html')
Now, create the corresponding URL for it. Since this is a user-facing page and not a DRF API endpoint, we will add it to the main core/urls.py file.Python# core/urls.py (add to existing file)

from django.contrib import admin
from django.urls import path, include
from subscriptions.views import payment_success_view # Import the view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('payment-success/', payment_success_view, name='payment-success'), # New
]
Finally, create the template file. Create a directory structure subscriptions/templates/subscriptions/ and inside it, create payment_success.html. We will add the content for this file in the next part.Part IV: Implementing the Client-Side InterfaceA backend API is only useful if there is a client to interact with it. This section provides the necessary HTML and JavaScript to create a minimal but fully functional frontend. This client-side implementation will allow users to select a subscription, initiate the payment flow, and have their payment verified, thus enabling a complete end-to-end test of the system we have built.Section 4.1: Building the Subscription Selection PageWe need a page where authenticated users can see the available subscription plans and choose one to purchase. We will create a simple Django template view and an HTML file for this purpose.First, add a view to subscriptions/views.py to render the page.Python# subscriptions/views.py (add to existing file)

from django.contrib.auth.decorators import login_required

@login_required
def subscription_page_view(request):
    """
    Renders the main subscription selection page.
    """
    # Pass the Khalti public key to the template context
    context = {
        'khalti_public_key': settings.KHALTI_PUBLIC_KEY 
        # Note: You need to add KHALTI_PUBLIC_KEY to your.env and settings.py
    }
    return render(request, 'subscriptions/subscription_page.html', context)
Important: Go back to your .env file and core/settings.py to add your Khalti Public Key, just as you did for the Secret Key.Code snippet#.env
KHALTI_PUBLIC_KEY=your_test_public_key_from_dashboard
Python# core/settings.py
KHALTI_PUBLIC_KEY = os.getenv('KHALTI_PUBLIC_KEY')
Next, add a URL for this page in core/urls.py.Python# core/urls.py (add to existing file)

from subscriptions.views import payment_success_view, subscription_page_view # Add subscription_page_view

urlpatterns = [
    #... other urls
    path('subscribe/', subscription_page_view, name='subscribe-page'), # New
    path('payment-success/', payment_success_view, name='payment-success'),
]
Now, create the HTML template at subscriptions/templates/subscriptions/subscription_page.html. This page will fetch the plans from our API and display them.HTML<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Choose a Subscription</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
       .plan { border: 1px solid #ccc; padding: 1em; margin-bottom: 1em; border-radius: 8px; }
       .plan h3 { margin-top: 0; }
        button { padding: 0.8em 1.5em; background-color: #5C2D91; color: white; border: none; border-radius: 5px; cursor: pointer; }
        #message-area { margin-top: 1em; padding: 1em; border-radius: 5px; display: none; }
       .success { background-color: #d4edda; color: #155724; }
       .error { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>Our Subscription Plans</h1>
    <div id="plans-container">
        <p>Loading plans...</p>
    </div>
    <div id="message-area"></div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const plansContainer = document.getElementById('plans-container');
            const messageArea = document.getElementById('message-area');

            // Fetch available plans from our DRF API
            fetch('/api/subscriptions/plans/', {
                headers: {
                    'Content-Type': 'application/json',
                    // Note: In a real app with token auth, you'd include the Authorization header
                }
            })
           .then(response => response.json())
           .then(plans => {
                plansContainer.innerHTML = ''; // Clear loading message
                plans.forEach(plan => {
                    const planElement = document.createElement('div');
                    planElement.classList.add('plan');
                    planElement.innerHTML = `
                        <h3>${plan.name}</h3>
                        <p>${plan.description}</p>
                        <p><strong>Price:</strong> Rs. ${plan.price}</p>
                        <p><strong>Duration:</strong> ${plan.duration_days} days</p>
                        <button class="subscribe-btn" data-plan-id="${plan.id}">Subscribe Now</button>
                    `;
                    plansContainer.appendChild(planElement);
                });

                // Add event listeners to the new buttons
                document.querySelectorAll('.subscribe-btn').forEach(button => {
                    button.addEventListener('click', handleSubscription);
                });
            })
           .catch(error => {
                console.error('Error fetching plans:', error);
                plansContainer.innerHTML = '<p>Could not load subscription plans. Please try again later.</p>';
            });

            function handleSubscription(event) {
                const planId = event.target.dataset.planId;
                showMessage('info', 'Initiating payment...');

                fetch('/api/subscriptions/initiate/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // IMPORTANT: Add CSRF token for security
                        'X-CSRFToken': getCookie('csrftoken'), 
                    },
                    body: JSON.stringify({ plan_id: planId })
                })
               .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to initiate payment.');
                    }
                    return response.json();
                })
               .then(data => {
                    if (data.payment_url) {
                        // Redirect user to Khalti's payment page
                        window.location.href = data.payment_url;
                    } else {
                        throw new Error('Payment URL not received.');
                    }
                })
               .catch(error => {
                    console.error('Error initiating payment:', error);
                    showMessage('error', 'Failed to start payment process. Please try again.');
                });
            }

            function showMessage(type, text) {
                messageArea.textContent = text;
                messageArea.className = type;
                messageArea.style.display = 'block';
            }

            // Helper function to get CSRF token from cookies
            function getCookie(name) {
                let cookieValue = null;
                if (document.cookie && document.cookie!== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            }
        });
    </script>
</body>
</html>
Section 4.2: Orchestrating the Full Payment Flow with JavaScriptThe JavaScript logic is split into two parts: the initiation on the subscription page (which we just created) and the verification on the return_url page.Part 1: Initiation Logic (on subscription_page.html)The script in the HTML file above performs the following actions:Fetches Plans: On page load, it makes a GET request to our /api/subscriptions/plans/ endpoint to retrieve the list of available subscription plans.Renders Plans: It dynamically creates HTML elements for each plan and displays them to the user, including a "Subscribe Now" button for each.Handles Clicks: It attaches a click event listener to each "Subscribe" button.Initiates Payment: When a button is clicked, it sends a POST request to our /api/subscriptions/initiate/ endpoint, including the selected plan_id in the request body. For security, it also includes Django's CSRF token, which it retrieves from the browser's cookies.Redirects to Khalti: Upon receiving a successful response from our backend (which contains the payment_url from Khalti), it redirects the user's browser to that URL, taking them to the secure Khalti payment page.Part 2: Verification Logic (on the return_url page)Now we need to create the content for subscriptions/templates/subscriptions/payment_success.html. This page will be loaded when the user is redirected back from Khalti. Its script will extract the pidx from the URL and send it to our backend for the final, authoritative verification.HTML<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verifying Payment</title>
    <style>
        body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
       .container { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1 id="status-heading">Verifying your payment, please wait...</h1>
        <p id="status-message"></p>
        <a id="dashboard-link" href="/subscribe/" style="display: none;">Go to Dashboard</a>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const pidx = urlParams.get('pidx');
            
            const statusHeading = document.getElementById('status-heading');
            const statusMessage = document.getElementById('status-message');
            const dashboardLink = document.getElementById('dashboard-link');

            if (!pidx) {
                statusHeading.textContent = 'Verification Failed';
                statusMessage.textContent = 'Payment identifier not found in the URL. Please contact support.';
                return;
            }

            // Send the pidx to our backend for verification
            fetch('/api/subscriptions/verify/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ pidx: pidx })
            })
           .then(response => response.json().then(data => ({ status: response.status, body: data })))
           .then(({ status, body }) => {
                if (status === 200) {
                    statusHeading.textContent = 'Payment Successful!';
                    statusMessage.textContent = body.message |

| 'Your subscription is now active.';
                    dashboardLink.style.display = 'inline-block';
                } else {
                    statusHeading.textContent = 'Payment Verification Failed';
                    statusMessage.textContent = body.error |

| body.message |
| 'An error occurred. Please contact support.';
                }
            })
           .catch(error => {
                console.error('Verification error:', error);
                statusHeading.textContent = 'Verification Error';
                statusMessage.textContent = 'Could not communicate with the server to verify your payment. Please contact support.';
            });

            // Helper function to get CSRF token
            function getCookie(name) {
                let cookieValue = null;
                if (document.cookie && document.cookie!== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            }
        });
    </script>
</body>
</html>
This script completes the loop:It extracts the pidx from the URL's query parameters.It makes a POST request to our /api/subscriptions/verify/ endpoint with the pidx.It waits for the definitive response from our server.Based on the server's response (which was determined by the authoritative call to Khalti), it displays a final "Success" or "Failure" message to the user.With this client-side code in place, you now have a complete, testable payment integration workflow.Part V: Production Readiness and Advanced PracticesBuilding a functional demo is one thing; deploying a robust, secure, and reliable application to production is another. This final section covers essential practices that elevate your project from a proof-of-concept to production-grade software. We will discuss comprehensive error handling, ensuring transaction idempotency to prevent duplicate processing, and a final checklist for going live.Section 5.1: Architecting for Robust Error HandlingIn a production environment where DEBUG is set to False, unhandled exceptions will not display detailed tracebacks to the user. Instead, they will show a generic server error page, and you, the developer, might not even be aware that an error occurred.29 It is crucial to implement strategies to gracefully handle expected errors and to be notified of unexpected ones.1. Handling Expected Exceptions in Views:Our views already include try...except blocks for network errors (requests.exceptions.RequestException). This is good practice. You should expand this to handle other potential issues. For example, what if Khalti returns an invalid JSON response?Python# subscriptions/views.py (example refinement)
import json

#... inside VerifyPaymentView's post method...
try:
    response = requests.post(settings.KHALTI_VERIFY_URL, json=payload, headers=headers)
    response.raise_for_status()
    
    try:
        khalti_response = response.json()
    except json.JSONDecodeError:
        # Handle cases where Khalti's response is not valid JSON
        return Response({"error": "Invalid response from payment gateway."}, status=status.HTTP_502_BAD_GATEWAY)
    
    #... rest of the logic
except requests.exceptions.RequestException as e:
    #...
2. Django REST Framework Custom Exception Handling:For a consistent error response format across your entire API, DRF allows you to define a custom exception handler.30 Create a new file, for example, subscriptions/exceptions.py:Python# subscriptions/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if response is not None:
        # Use a consistent error format
        response.data = {
            'error': {
                'status_code': response.status_code,
                'detail': response.data.get('detail', str(exc))
            }
        }
        
    # Handle specific unhandled exceptions if needed
    # For example, a generic 500 error
    if response is None:
        # You can log the exception `exc` here
        return Response({
            'error': {
                'status_code': 500,
                'detail': 'An unexpected server error occurred.'
            }
        }, status=500)

    return response
Then, register this handler in core/settings.py:Python# core/settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'subscriptions.exceptions.custom_exception_handler',
    #... other DRF settings
}
This ensures all API errors, whether a ValidationError or a PermissionDenied error, will be returned in a predictable JSON structure, which is invaluable for frontend clients.313. Django's Error Reporting:For unexpected server errors (HTTP 500), Django can automatically email you the full traceback. In core/settings.py, configure the ADMINS setting when DEBUG is False:Python# core/settings.py
ADMINS = [('Your Name', 'your-email@example.com')]
You will also need to configure your email backend settings (e.g., for SMTP) for this to work. This provides immediate notification of critical failures in your production environment.29Section 5.2: Ensuring Idempotency to Prevent Duplicate ChargesIdempotency is the property of certain operations in computing whereby they can be applied multiple times without changing the result beyond the initial application. In the context of payments, this is a critical concept. A user might double-click a "Pay" button, or a network timeout might cause their browser to resend a verification request. If your verification logic is not idempotent, you might accidentally grant the user two subscriptions for a single payment.28While some gateway APIs are designed to be idempotent themselves, it is a crucial best practice to build idempotency checks into your own application layer as a failsafe.Our VerifyPaymentView already contains a basic idempotency check:Python# from subscriptions/views.py
# Idempotency Check: If transaction is already completed, don't process again.
if transaction.status == 'completed':
    return Response({"status": "success", "message": "Payment has already been verified."}, status=status.HTTP_200_OK)
This simple check is highly effective. Before performing any action, it queries the database to see if the transaction associated with the given pidx has already been successfully processed. If it has, it simply returns a success response without re-running the subscription activation logic. This makes your system resilient to repeated requests for the same transaction and is a hallmark of professional-grade backend development. We also designed the Transaction model with a unique=True constraint on khalti_pidx, which provides a database-level guarantee against duplicate records for the same payment initiation.Section 5.3: The Go-Live ChecklistTransitioning from the sandbox to a live, production environment involves several critical steps. Missing any of these can result in failed payments or security issues.Create a Live Khalti Merchant Account: The sandbox account is only for testing. You must sign up for a production merchant account on the main Khalti website: https://khalti.com/merchant/.18Complete Merchant KYC: For a live account, you will need to submit required business documents (e.g., Company Registration, PAN/VAT certificate) to complete the Know Your Customer (KYC) process. This is mandatory to remove transaction limits. Initially, live accounts may be restricted to small transaction amounts (e.g., NPR 1000 or 200) until KYC is verified.12Update API Keys and URLs:Log in to your live Khalti merchant dashboard and retrieve your live Public and Secret keys.Update your production environment variables (or your production .env file) with these new live keys.Update the Khalti API URLs in your environment variables to point to the production endpoints (remove the dev. subdomain) 12:KHALTI_INITIATE_URL=https://khalti.com/api/v2/epayment/initiate/KHALTI_VERIFY_URL=https://khalti.com/api/v2/payment/verify/Update Application URLs:In your backend code (InitiatePaymentView) and frontend JavaScript, ensure that the return_url and website_url point to your live domain, not localhost. This should also be managed via environment variables.Set DEBUG = False:In your production settings.py, you must set DEBUG = False. Running with DEBUG = True in production is a major security risk as it can expose sensitive configuration details in error pages.29Configure ALLOWED_HOSTS:In settings.py, add your production domain name to the ALLOWED_HOSTS list to prevent HTTP Host header attacks.ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']Use HTTPS:All communication involving payments must be encrypted. Ensure your production site is served over HTTPS by obtaining and installing an SSL/TLS certificate.32Conclusion: Recapitulation and Future DirectionsThis report has provided a comprehensive, step-by-step guide to integrating the Khalti payment gateway into a Django REST Framework application, with a specific focus on building a subscription-based system. We have journeyed from the foundational theories of how online payments work to the practical, line-by-line implementation of a secure and robust backend.Key principles and skills covered include:The roles of various actors in the financial transaction chain and the value of a payment gateway in abstracting this complexity.The specific redirect-based architectural model of Khalti's Web Checkout.The non-negotiable security principle of authoritative server-side verification, treating the backend API lookup as the single source of truth for a transaction's status.The professional best practice of secure credential management using environment variables to separate configuration from code.The complete implementation of a payment lifecycle in Django REST Framework, including data modeling, serialization, and the creation of two critical API endpoints for payment initiation and payment verification.The importance of idempotency in payment processing and how to implement checks to prevent duplicate transactions.A practical checklist for transitioning the application from a sandbox environment to a live, production-ready state.While we have successfully built a system for fixed-duration subscriptions, it is important to acknowledge a limitation in Khalti's documented API: the absence of a native, automated recurring billing feature, which is a common offering in many modern payment gateways.10 Our current UserSubscription model correctly reflects this by being self-managed within our application; a subscription is active for a fixed period following a one-time payment.To evolve this project into a true recurring subscription service, the next logical step would be to implement a system for managing subscription renewals and expirations. This cannot be done by Khalti automatically. Instead, it would require a custom solution within your Django application, most effectively implemented using a periodic task scheduler. A tool like Celery with Celery Beat is the industry standard for this in the Django ecosystem.A potential future architecture would involve:A daily scheduled task (managed by Celery Beat) that queries the UserSubscription model for any subscriptions where the end_date has passed.For expired subscriptions, the task would update their status accordingly (e.g., by setting a flag or simply relying on the is_active property).The task could also trigger reminder emails to users a few days before their subscription is set to expire, prompting them to return to the site and make another payment to renew their access.By building upon the secure and robust foundation laid out in this guide and integrating a task scheduling system, you can develop a fully-featured, custom subscription management platform tailored to your application's specific needs.
