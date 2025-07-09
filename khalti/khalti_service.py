# subscription/services/khalti_service.py
import httpx
import asyncio
import logging
from typing import Dict, Optional, Any
from decimal import Decimal
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from asgiref.sync import sync_to_async
import json
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class KhaltiConfig:
    """Khalti configuration dataclass"""
    secret_key: str
    public_key: str
    live_mode: bool = False
    timeout: int = 30
    max_retries: int = 3
    
    @property
    def base_url(self) -> str:
        return "https://khalti.com/api/v2" if self.live_mode else "https://a.khalti.com/api/v2"

class KhaltiException(Exception):
    """Custom exception for Khalti API errors"""
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)

class KhaltiService:
    """Modern Khalti service with async support and better error handling"""
    
    def __init__(self, config: KhaltiConfig = None):
        self.config = config or KhaltiConfig(
            secret_key=getattr(settings, 'KHALTI_SECRET_KEY', ''),
            public_key=getattr(settings, 'KHALTI_PUBLIC_KEY', ''),
            live_mode=getattr(settings, 'KHALTI_LIVE_MODE', False)
        )
        self._client = None
        self._validate_config()
    
    def _validate_config(self):
        """Validate Khalti configuration"""
        if not self.config.secret_key:
            raise ValidationError("Khalti secret key is required")
        if not self.config.public_key:
            raise ValidationError("Khalti public key is required")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers=self._get_headers()
            )
        return self._client
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            'Authorization': f'Key {self.config.secret_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Django-Khalti-Service/1.0'
        }
    
    def _convert_to_paisa(self, amount: Decimal) -> int:
        """Convert rupees to paisa (Khalti uses paisa)"""
        return int(amount * 100)
    
    def _convert_to_rupees(self, amount: int) -> Decimal:
        """Convert paisa to rupees"""
        return Decimal(amount) / 100
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Dict = None, 
        params: Dict = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params
                )
                
                if response.status_code == 200:
                    return response.json()
                
                # Handle specific error codes
                if response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    raise KhaltiException(
                        f"Bad request: {error_data.get('message', 'Invalid request')}",
                        response.status_code,
                        error_data
                    )
                elif response.status_code == 401:
                    raise KhaltiException("Unauthorized: Invalid API key", response.status_code)
                elif response.status_code == 429:
                    # Rate limiting - wait before retry
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise KhaltiException(
                        f"HTTP {response.status_code}: {response.text}",
                        response.status_code
                    )
                    
            except httpx.RequestError as e:
                if attempt == self.config.max_retries - 1:
                    raise KhaltiException(f"Network error: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        
        raise KhaltiException("Max retries exceeded")
    
    async def initiate_payment(
        self,
        amount: Decimal,
        purchase_order_id: str,
        purchase_order_name: str,
        return_url: str,
        website_url: str,
        customer_info: Dict[str, str],
        custom_data: Dict = None
    ) -> Dict[str, Any]:
        """
        Initiate payment with Khalti
        
        Args:
            amount: Payment amount in NPR
            purchase_order_id: Unique order identifier
            purchase_order_name: Human readable order name
            return_url: URL to return after payment
            website_url: Your website URL
            customer_info: Customer information dict
            custom_data: Additional custom data
        
        Returns:
            Dict containing payment URL and pidx
        """
        cache_key = f"khalti_payment_{purchase_order_id}"
        
        # Check cache to prevent duplicate requests
        if cache.get(cache_key):
            raise KhaltiException("Payment already initiated for this order")
        
        payload = {
            'return_url': return_url,
            'website_url': website_url,
            'amount': self._convert_to_paisa(amount),
            'purchase_order_id': purchase_order_id,
            'purchase_order_name': purchase_order_name,
            'customer_info': {
                'name': customer_info.get('name', ''),
                'email': customer_info.get('email', ''),
                'phone': customer_info.get('phone', '9800000000')
            }
        }
        
        if custom_data:
            payload['custom_data'] = custom_data
        
        logger.info(f"Initiating payment for order {purchase_order_id}")
        
        try:
            response = await self._make_request('POST', '/epayment/initiate/', payload)
            
            # Cache the response to prevent duplicates
            cache.set(cache_key, response, timeout=300)  # 5 minutes
            
            logger.info(f"Payment initiated successfully: {response.get('pidx')}")
            return response
            
        except KhaltiException as e:
            logger.error(f"Payment initiation failed: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during payment initiation: {str(e)}")
            raise KhaltiException(f"Payment initiation failed: {str(e)}")
    
    async def verify_payment(self, pidx: str) -> Dict[str, Any]:
        """
        Verify payment status with Khalti
        
        Args:
            pidx: Payment identifier from Khalti
            
        Returns:
            Dict containing payment verification details
        """
        cache_key = f"khalti_verify_{pidx}"
        
        # Check cache first
        cached_response = cache.get(cache_key)
        if cached_response:
            return cached_response
        
        payload = {'pidx': pidx}
        
        logger.info(f"Verifying payment: {pidx}")
        
        try:
            response = await self._make_request('POST', '/epayment/lookup/', payload)
            
            # Cache successful verification for 1 hour
            if response.get('status') == 'Completed':
                cache.set(cache_key, response, timeout=3600)
            
            logger.info(f"Payment verification result: {response.get('status')}")
            return response
            
        except KhaltiException as e:
            logger.error(f"Payment verification failed: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during payment verification: {str(e)}")
            raise KhaltiException(f"Payment verification failed: {str(e)}")
    
    async def get_payment_details(self, pidx: str) -> Dict[str, Any]:
        """
        Get detailed payment information
        
        Args:
            pidx: Payment identifier
            
        Returns:
            Dict containing detailed payment information
        """
        verification_data = await self.verify_payment(pidx)
        
        return {
            'pidx': pidx,
            'status': verification_data.get('status'),
            'amount': self._convert_to_rupees(verification_data.get('amount', 0)),
            'fee': self._convert_to_rupees(verification_data.get('fee', 0)),
            'refunded': verification_data.get('refunded', False),
            'purchase_order_id': verification_data.get('purchase_order_id'),
            'purchase_order_name': verification_data.get('purchase_order_name'),
            'transaction_id': verification_data.get('transaction_id'),
            'created_on': verification_data.get('created_on'),
            'payment_method': verification_data.get('payment_method'),
            'customer_info': verification_data.get('customer_info', {})
        }
    
    async def initiate_refund(self, pidx: str, amount: Decimal = None, reason: str = None) -> Dict[str, Any]:
        """
        Initiate refund for a payment
        
        Args:
            pidx: Payment identifier
            amount: Refund amount (if partial refund)
            reason: Refund reason
            
        Returns:
            Dict containing refund details
        """
        payload = {'pidx': pidx}
        
        if amount:
            payload['amount'] = self._convert_to_paisa(amount)
        
        if reason:
            payload['reason'] = reason
        
        logger.info(f"Initiating refund for payment: {pidx}")
        
        try:
            response = await self._make_request('POST', '/epayment/refund/', payload)
            logger.info(f"Refund initiated successfully: {response.get('refund_id')}")
            return response
            
        except KhaltiException as e:
            logger.error(f"Refund initiation failed: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during refund initiation: {str(e)}")
            raise KhaltiException(f"Refund initiation failed: {str(e)}")
    
    async def get_refund_status(self, refund_id: str) -> Dict[str, Any]:
        """
        Get refund status
        
        Args:
            refund_id: Refund identifier
            
        Returns:
            Dict containing refund status
        """
        payload = {'refund_id': refund_id}
        
        try:
            response = await self._make_request('POST', '/epayment/refund/lookup/', payload)
            return response
            
        except KhaltiException as e:
            logger.error(f"Refund status check failed: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during refund status check: {str(e)}")
            raise KhaltiException(f"Refund status check failed: {str(e)}")
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Synchronous wrapper for backward compatibility
class SyncKhaltiService:
    """Synchronous wrapper for KhaltiService"""
    
    def __init__(self, config: KhaltiConfig = None):
        self.async_service = KhaltiService(config)
    
    def initiate_payment(self, *args, **kwargs):
        return asyncio.run(self.async_service.initiate_payment(*args, **kwargs))
    
    def verify_payment(self, pidx: str):
        return asyncio.run(self.async_service.verify_payment(pidx))
    
    def get_payment_details(self, pidx: str):
        return asyncio.run(self.async_service.get_payment_details(pidx))
    
    def initiate_refund(self, *args, **kwargs):
        return asyncio.run(self.async_service.initiate_refund(*args, **kwargs))
    
    def get_refund_status(self, refund_id: str):
        return asyncio.run(self.async_service.get_refund_status(refund_id))

# Utility functions
def get_khalti_service(async_mode: bool = False) -> KhaltiService:
    """Get Khalti service instance"""
    if async_mode:
        return KhaltiService()
    return SyncKhaltiService()