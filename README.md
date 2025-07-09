#  A Comprehensive Guide to Integrating Khalti Payments and Subscriptions in Django REST Framework
---
## Integration Architecture: The Khalti Web Checkout Model

Payment gateways offer various integration models, each with different implications for user experience and developer responsibility. Khalti's primary method for web applications, known as "Web Checkout," is best classified as a redirect-based or hosted payment gateway model.
<br> In this model, the customer is redirected away from the merchant's website to a secure page hosted by the payment gateway itself to enter their payment details. After the transaction is complete, the user is redirected back to a pre-specified URL on the merchant's site.

The official Khalti documentation outlines this precise flow :   
1. Initiation: The merchant's backend server makes a secure API request to Khalti to initiate a payment.
2. Redirection URL: Khalti's system responds with a unique payment identifier (pidx) and a payment_url.
3. User Redirect: The merchant's application must redirect the user's browser to this payment_url. The user is now on a page controlled and secured by Khalti.
4. Payment Completion: The user enters their payment details (Khalti wallet, eBanking credentials, etc.) and completes the payment on Khalti's platform.
5. Callback Redirect: After payment, Khalti redirects the user back to the return_url that the merchant specified during the initiation step. This URL will have several query parameters appended to it, including the pidx and a preliminary transaction status.

This redirect model offers a significant security advantage: your application's servers never see, handle, or store the user's sensitive payment credentials (like their Khalti MPIN or bank password). This greatly reduces your application's PCI compliance scope.

However, a critical nuance in Khalti's architecture distinguishes it from simpler hosted gateways. The process is not complete when the user returns to your site. The Khalti documentation explicitly states: "Merchant side must hit the lookup API to get the status of the transaction". This requirement creates a hybrid architectural model. It combines the user-facing simplicity and security of a redirect for data collection with the backend robustness of a direct API integration for confirmation. This two-part interaction one API call to start the process and a second, separate API call to definitively confirm it is a crucial architectural pattern that must be correctly implemented for a secure and reliable system. The potential for confusion around this two-step process is high and is a likely reason why developers find the documentation challenging.
<br>

## The Principle of Authoritative Server-Side Verification

This brings us to the single most important principle in any payment gateway integration: the client-side can never be trusted as the final authority on a transaction's status.

<br>

When Khalti redirects the user back to your application's return_url, it includes query parameters like status=Completed. A naive or inexperienced developer might be tempted to parse this URL parameter in the browser and, upon seeing "Completed," immediately grant the user their purchased subscription or mark an order as paid. This would be a critical security vulnerability. A malicious user could easily manipulate the URL, or a simple network error could prevent the user from being redirected correctly even after a successful payment.  

<br>

The only reliable way to confirm a transaction's true state is for your backend server to make a direct, authenticated API call to the payment gateway. This is known as server-side verification or a lookup. Khalti's documentation strongly recommends this practice: "It's recommended that during implementation, payment lookup API is checked for confirmation after the redirect callback is received". 

<br>

This principle is rooted in the fact that the definitive record of the transaction—the "source of truth"—resides on the secure servers of the payment gateway and the associated financial institutions. This truth is only accessible via a secure, authenticated channel, which is the server-to-server API call using your secret key.

<br>

Therefore, the result of this server-side verification call is the only trigger that should ever be allowed to alter your application's state. It is the only event that should cause your application to perform actions such as:
- Creating a UserSubscription record in the database.
- Marking an e-commerce order's status as 'Paid'.
- Granting a user access to premium features.
- Initiating a product delivery workflow.

The user's return to the client-side return_url should be treated as nothing more than a signal that a transaction attempt has concluded. The frontend's role at this stage is to display a temporary message (e.g., "Thank you, we are verifying your payment...") and to pass the pidx received in the URL to the backend, which will then perform the authoritative verification. This decoupling of the user's browser experience from the application's state change logic is the cornerstone of a robust, secure, and reliable payment system.


## Environment and Project Configuration
- Create Project Directory and Virtual Environment:
<pre><code>
mkdir khalti_project_tutorial <br>
cd khalti_project_tutorial <br>
python -m venv venv <br>
source venv/bin/activate  # On Windows, use venv\Scripts\activate
</code>
</pre>
- Install Dependencies: <br>
  `pip install django djangorestframework requests django-khalti python-dotenv`
- Add “django-khalti” and “djangorestframework “to your INSTALLED_APPS setting like this: <br>
  <pre><code>
    INSTALLED_APPS = [
                     …
                     ‘rest_framework’,
                     ‘khalti’,
                     ]
  </code></pre>

### The Khalti Sandbox Environment
Khalti provides a fully-featured sandbox (or test) environment that allows developers to integrate and test the entire payment flow without using real money or requiring official business registration documents. This is an essential tool for development.
#### 1. Sign Up for a Test Merchant Account:
   Navigate to the Khalti sandbox signup page: https://dev.khalti.com/ (or the specific merchant signup link provided in their docs ). You can use placeholder information       for the signup process as it's for testing purposes only.
#### 2. Locate Your API Keys:
   Once you have created your test merchant account and logged in to the sandbox dashboard, navigate to the "Keys" section. Here you will find two critical pieces of            information: your Public Key and your Secret Key.
   <br>
These two keys serve distinct and separate purposes. Understanding their roles is crucial to avoid security vulnerabilities.

# Khalti API Keys

| Key Name | Also Known As | Purpose | Where to Use It | Security Level |
|----------|---------------|---------|----------------|----------------|
| **Public Key** | Client-Side Authorization Key | Identifies your merchant account in client-side requests. It is used by the Khalti frontend components. | This key is used in the frontend JavaScript that initiates the payment process. For mobile SDKs, it's the client-side key. | **Public**. It is safe to expose this key in your frontend code (HTML/JavaScript). |
| **Secret Key** | Server-Side Authorization Key, API Key | Authenticates your application's backend server for secure, server-to-server API calls (like initiation and verification). | This key is used in the `Authorization` header of API requests made from your Django backend to Khalti's servers. | **Secret**. This key must **NEVER** be exposed in frontend code or committed to version control. It is equivalent to a password. |
---
#### 3. Test Credentials:
   For testing payments in the sandbox environment, Khalti provides a set of test credentials that can be used on the payment page :
   - Test Khalti ID (Mobile Number): 9800000000 (and several others listed in the docs)
   - Test MPIN: 1111
   - Test OTP (One-Time Password): 987654

#### 4. Add Secrets to .env:
   Open the .env file and add your Khalti Secret Key and the API URLs. Do not use quotes around the values.
   <pre><code>
     #.env

     KHALTI_SECRET_KEY=your_test_secret_key_from_the_dashboard
     KHALTI_INITIATE_URL=https://dev.khalti.com/api/v2/epayment/initiate/
     KHALTI_VERIFY_URL=https://dev.khalti.com/api/v2/epayment/verify/
   </code></pre>
   **Note: For a live application, the URLs would change to https://khalti.com/....**

#### 5. The Payment Initiation API Endpoint
The table below summarizes the fields for the Khalti initiation payload for quick reference.
<br>
 # Khalti Payment Request Fields

| Field Name | Required? | Data Type | Description | Example Value |
|------------|-----------|-----------|-------------|---------------|
| `return_url` | Yes | String (URL) | The URL where the user is redirected after payment completion. | `"http://localhost:8000/payment-success/"` |
| `website_url` | Yes | String (URL) | The root URL of your website. | `"http://localhost:8000/"` |
| `amount` | Yes | Integer | Total amount to be paid. **Crucial: Must be in paisa (NPR * 100)**. | `50000` (for Rs. 500.00) |
| `purchase_order_id` | Yes | String | A unique identifier for the purchase from the merchant's system. | `"sub-plan-1-user-5-timestamp"` |
| `purchase_order_name` | Yes | String | A descriptive name for the purchase. | `"Premium Plan - Monthly"` |
| `customer_info` | No | Object | An object containing customer details like name, email, and phone. | `{"name": "Test User", "email": "test@example.com"}` |
| `amount_breakdown` | No | Array of Objects | An array to show a breakdown of the total amount. | `[{"label": "Premium Plan", "amount": 50000}]` |

---
This is the most security-critical part of the backend. This endpoint will be called by our frontend after the user returns from the Khalti payment page. It will receive the pidx and use it to perform the authoritative server-side verification.
<pre><code>
  # views.py

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
</code></pre>
<br>
<br>

  ***Note: Look project directory for models and serializers***
  
#### View Breakdown:
1. It receives the pidx from the frontend.

2. It retrieves our corresponding Transaction record.

3. Idempotency Check: It checks if this transaction has already been marked as 'completed'. If so, it returns a success message without processing again, preventing duplicate subscription grants.   

4. It constructs the payload and headers for the verification request, including the crucial Authorization: Key <secret_key> header.   

5. It makes the requests.post call to Khalti's verification endpoint.

6. It carefully checks the status field in Khalti's JSON response. This is where we implement the logic from our "Source of Truth" principle.

7. If the status is 'Completed', it updates our local transaction record, saves the final khalti_transaction_id, and calls a helper method activate_subscription.

8. The activate_subscription method creates or updates the UserSubscription record, setting the start_date and calculating the end_date based on the plan's duration.

9. If the status from Khalti is anything other than 'Completed', it updates our local record with the failure status and returns an appropriate error message to the frontend.

#### 6. Managing the User-Facing Callback
The return_url we specified in the initiation call needs to point to an actual page in our application. This page's primary role is to host the JavaScript that will call our verification API. We will create a simple Django template view for this.
<br>
First, create a  view in views.py:
<pre><code>
  # subscriptions/views.py (add to existing file)
from django.shortcuts import render

def payment_success_view(request):
    """
    A simple view to render the page the user is redirected to after Khalti.
    This page will contain the JavaScript to call our verification API.
    """
    return render(request, 'subscriptions/payment_success.html')
</code></pre>
<br>

Now we need to create the content for payment_success.html. This page will be loaded when the user is redirected back from Khalti. Its script will extract the pidx from the URL and send it to our backend for the final, authoritative verification.
<pre><code>
      <!DOCTYPE html>
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
</body>
</html>
</code></pre>

Now, create the corresponding URL for it. Since this is a user-facing page and not a DRF API endpoint, we will add it to the main core/urls.py file.
<pre><code>
    # core/urls.py (add to existing file)
  
  from django.contrib import admin
  from django.urls import path, include
  from subscriptions.views import payment_success_view # Import the view
  
  urlpatterns = [
      path('admin/', admin.site.urls),
      path('payment-success/', payment_success_view, name='payment-success'), 
      ......
  ]
</code></pre>
