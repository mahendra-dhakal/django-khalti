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
