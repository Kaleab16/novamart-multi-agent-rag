"""Unit tests for NovaMart routing, identifiers, and refund rules."""

from src.agent_orchestrator import (
    _extract_identifier,
    decide_refund,
    route_intent,
)


def test_routes_refund_request():
    assert route_intent("I want a refund for my order") == "refund"


def test_routes_policy_request():
    assert route_intent("What is the warranty policy?") == "policy"


def test_routes_order_request():
    assert route_intent("Where is my order?") == "order"


def test_routes_account_request():
    assert route_intent("What is my membership tier?") == "account"


def test_routes_math_request():
    assert route_intent("Calculate a 10 percent discount") == "math"


def test_unknown_request_routes_to_general():
    assert route_intent("Hello there") == "general"


def test_extracts_order_identifier():
    assert _extract_identifier("Please check ORD-1001", "ORD") == "ORD-1001"


def test_extracts_customer_identifier():
    assert _extract_identifier("My customer ID is CUST-2001", "CUST") == "CUST-2001"


def test_missing_identifier_returns_none():
    assert _extract_identifier("Where is my package?", "ORD") is None


def test_standard_customer_eligible_at_30_days():
    order = {"status": "Delivered", "days_since_delivery": 30}
    customer = {"tier": "Standard"}

    result = decide_refund(order, customer)

    assert result["eligible"] is True
    assert result["decision"] == "eligible"
    assert result["return_window_days"] == 30


def test_standard_customer_not_eligible_after_30_days():
    order = {"status": "Delivered", "days_since_delivery": 31}
    customer = {"tier": "Standard"}

    result = decide_refund(order, customer)

    assert result["eligible"] is False
    assert result["decision"] == "not_eligible"


def test_premium_customer_eligible_at_60_days():
    order = {"status": "Delivered", "days_since_delivery": 60}
    customer = {"tier": "Premium"}

    result = decide_refund(order, customer)

    assert result["eligible"] is True
    assert result["return_window_days"] == 60


def test_premium_customer_not_eligible_after_60_days():
    order = {"status": "Delivered", "days_since_delivery": 61}
    customer = {"tier": "Premium"}

    result = decide_refund(order, customer)

    assert result["eligible"] is False
    assert result["decision"] == "not_eligible"


def test_undelivered_order_is_not_eligible():
    order = {"status": "Shipped", "days_since_delivery": 5}
    customer = {"tier": "Premium"}

    result = decide_refund(order, customer)

    assert result["eligible"] is False
    assert result["decision"] == "not_eligible"


def test_missing_order_needs_review():
    result = decide_refund(None, {"tier": "Standard"})

    assert result["eligible"] is False
    assert result["decision"] == "needs_review"


def test_missing_customer_needs_review():
    order = {"status": "Delivered", "days_since_delivery": 5}

    result = decide_refund(order, None)

    assert result["eligible"] is False
    assert result["decision"] == "needs_review"


def test_order_id_alone_routes_to_order():
    assert route_intent("ORD-1001") == "order"


def test_customer_id_alone_routes_to_account():
    assert route_intent("CUST-2001") == "account"


def test_order_id_with_shipping_question_routes_to_order():
    assert route_intent("Can you check ORD-1001?") == "order"


def test_refund_intent_takes_priority_over_order_id():
    assert route_intent("Can I get a refund for ORD-1001?") == "refund"
