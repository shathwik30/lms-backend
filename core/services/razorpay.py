"""
Razorpay payment gateway integration (INR only).

Usage:
    from core.services.razorpay import RazorpayService

    # Create order
    order = RazorpayService.create_order(amount=Decimal("999.00"), receipt="purchase_42")

    # Verify payment
    is_valid = RazorpayService.verify_payment(
        order_id="order_xxx",
        payment_id="pay_xxx",
        signature="sig_xxx",
    )
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import razorpay
from django.conf import settings


def _get_client() -> razorpay.Client:
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
    )


def _rupees_to_paise(amount: Decimal | float) -> int:
    """Convert rupees to paise without floating-point loss."""
    return int(Decimal(str(amount)).quantize(Decimal("0.01")) * 100)


class RazorpayService:
    @staticmethod
    def create_order(
        amount: Decimal | float,
        receipt: str,
        currency: str = "INR",
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Razorpay order.

        Args:
            amount: Amount in rupees (e.g. Decimal("999.00"))
            receipt: Unique receipt string (e.g. "purchase_42")
            currency: Currency code (always INR)
            notes: Optional dict of metadata

        Returns:
            dict with order_id, amount, currency, etc.
        """
        client = _get_client()
        data: dict[str, Any] = {
            "amount": _rupees_to_paise(amount),
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
    def initiate_refund(payment_id: str, amount: Decimal | float | None = None) -> dict[str, Any]:
        """
        Initiate a refund.

        Args:
            payment_id: Razorpay payment ID
            amount: Partial refund amount in rupees (None = full refund)
        """
        client = _get_client()
        data: dict[str, Any] = {}
        if amount:
            data["amount"] = _rupees_to_paise(amount)
        return client.payment.refund(payment_id, data)

    @staticmethod
    def get_order_payments(order_id: str) -> list[dict[str, Any]]:
        """List all payments attached to a given order.

        Used by reconciliation to discover captured payments for orders whose
        /verify/ call never arrived.
        """
        client = _get_client()
        resp = client.order.payments(order_id)
        return resp.get("items", []) or []
