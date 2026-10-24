"""Reusable MongoDB tools for the fictional NovaMart learning project."""
from __future__ import annotations

import logging
from pymongo.errors import PyMongoError
from strands import tool

try:
    from . import mongodb_store
except ImportError:
    import mongodb_store

log = logging.getLogger(__name__)


def _failure(operation: str, exc: Exception) -> dict:
    log.warning("%s failed (%s)", operation, type(exc).__name__)
    return {
        "ok": False,
        "error": "data_access_failed",
        "message": "Could not access the requested record. Check MongoDB configuration and connectivity.",
    }


def _order(order_id: str) -> dict | None:
    return mongodb_store.get_order(order_id.strip()) if order_id and order_id.strip() else None


def _customer(customer_id: str) -> dict | None:
    return mongodb_store.get_customer(customer_id.strip()) if customer_id and customer_id.strip() else None


@tool
def check_order_status(order_id: str) -> dict:
    """Look up an order by ID and return its status and details."""
    try:
        item = _order(order_id)
        if not item:
            return {"ok": True, "found": False, "order_id": order_id}
        return {"ok": True, "found": True, "order": item}
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("check_order_status", exc)


@tool
def get_customer_tier(customer_id: str) -> dict:
    """Look up a customer's membership tier by customer ID."""
    try:
        item = _customer(customer_id)
        if not item:
            return {"ok": True, "found": False, "customer_id": customer_id}
        return {
            "ok": True, "found": True,
            "customer_id": customer_id,
            "tier": item.get("tier", "Unknown"),
        }
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("get_customer_tier", exc)


@tool
def list_customer_orders(customer_id: str) -> dict:
    """List all orders for a customer."""
    try:
        if not customer_id or not customer_id.strip():
            return {"ok": False, "error": "customer_id_required"}
        cid = customer_id.strip()
        orders = mongodb_store.list_customer_orders(cid)
        return {
            "ok": True, "customer_id": cid,
            "count": len(orders), "orders": orders,
        }
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("list_customer_orders", exc)


@tool
def get_inventory_context(order_id: str) -> dict:
    """Retrieve an order and its associated customer record."""
    try:
        item = _order(order_id)
        if not item:
            return {"ok": True, "found": False, "order_id": order_id}
        cid = str(item.get("customer_id", ""))
        return {
            "ok": True, "found": True, "order": item,
            "customer": _customer(cid) if cid else None,
        }
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("get_inventory_context", exc)


@tool
def initiate_refund(
    order_id: str,
    reason: str = "Customer requested a return",
) -> dict:
    """Check refund eligibility; this tool does not issue an actual refund."""
    try:
        item = _order(order_id)
        if not item:
            return {
                "ok": True, "eligible": False, "order_id": order_id,
                "reason": "Order not found.", "refund_issued": False,
            }

        cid = str(item.get("customer_id", ""))
        customer = _customer(cid) if cid else None
        if not customer:
            return {
                "ok": True, "eligible": False, "order_id": order_id,
                "reason": "Customer record not found.", "refund_issued": False,
            }

        tier = str(customer.get("tier", "Standard")).strip().lower()
        limit_days = 60 if tier == "premium" else 30

        try:
            days = int(item.get("days_since_delivery", 0))
        except (TypeError, ValueError):
            return {
                "ok": False, "error": "invalid_delivery_age",
                "refund_issued": False,
            }

        delivered = str(item.get("status", "")).lower() == "delivered"
        eligible = delivered and 0 <= days <= limit_days

        if not delivered:
            decision = "Order has not been delivered."
        elif days < 0:
            decision = "Delivery age is invalid."
        elif days > limit_days:
            decision = f"Outside the {limit_days}-day {tier.title()} return window."
        else:
            decision = f"Within the {limit_days}-day {tier.title()} return window."

        return {
            "ok": True, "order_id": order_id, "customer_id": cid,
            "customer_tier": customer.get("tier", "Unknown"),
            "days_since_delivery": days, "return_window_days": limit_days,
            "eligible": eligible, "reason": decision,
            "customer_reason": reason, "refund_issued": False,
            "next_step": "Support must review and process any approved refund.",
        }
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("initiate_refund", exc)


@tool
def get_full_workflow_context(session_id: str) -> dict:
    """Retrieve saved workflow state for a conversation session."""
    try:
        workflow = mongodb_store.get_workflow(session_id)
        if not workflow:
            return {"ok": True, "found": False, "session_id": session_id}
        return {"ok": True, "found": True, "workflow": workflow}
    except (PyMongoError, RuntimeError, ValueError, AttributeError) as exc:
        return _failure("get_full_workflow_context", exc)


AGENT_TOOLS = [
    check_order_status,
    get_customer_tier,
    list_customer_orders,
    get_inventory_context,
    initiate_refund,
    get_full_workflow_context,
]
