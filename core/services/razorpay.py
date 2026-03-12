"""
Razorpay payment gateway integration.

Usage:
    from core.services.razorpay import RazorpayService

    # Create order
    order = RazorpayService.create_order(amount=999.00, receipt="purchase_42")

    # Verify payment
    is_valid = RazorpayService.verify_payment(
        order_id="order_xxx",
        payment_id="pay_xxx",
        signature="sig_xxx",
    )
"""

from __future__ import annotations

from typing import Any

import razorpay
from django.conf import settings


def _get_client() -> razorpay.Client:
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
    )


class RazorpayService:
    @staticmethod
    def create_order(
        amount: float,
        receipt: str,
        currency: str = "INR",
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Razorpay order.

        Args:
            amount: Amount in rupees (e.g. 999.00)
            receipt: Unique receipt string (e.g. "purchase_42")
            currency: Currency code (default INR)
            notes: Optional dict of metadata

        Returns:
            dict with order_id, amount, currency, etc.
        """
        client = _get_client()
        data = {
            "amount": int(amount * 100),  # Razorpay expects paise
            "currency": currency,
            "receipt": receipt,
        }
        if notes:
            data["notes"] = notes

        order = client.order.create(data=data)
        return {
            "order_id": order["id"],
            "amount": amount,
            "currency": currency,
            "razorpay_key": settings.RAZORPAY_KEY_ID,
        }

    @staticmethod
    def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
        """
        Verify Razorpay payment signature.

        Returns True if signature is valid, False otherwise.
        """
        client = _get_client()
        try:
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            return True
        except razorpay.errors.SignatureVerificationError:
            return False

    @staticmethod
    def fetch_payment(payment_id: str) -> dict[str, Any]:
        """Fetch payment details from Razorpay."""
        client = _get_client()
        return client.payment.fetch(payment_id)

    @staticmethod
    def initiate_refund(payment_id: str, amount: float | None = None) -> dict[str, Any]:
        """
        Initiate a refund.

        Args:
            payment_id: Razorpay payment ID
            amount: Partial refund amount in rupees (None = full refund)
        """
        client = _get_client()
        data = {}
        if amount:
            data["amount"] = int(amount * 100)
        return client.payment.refund(payment_id, data)
