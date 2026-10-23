"""Mocked tests for the NovaMart request-processing flow."""
import src.agent_orchestrator as orchestrator


def test_empty_request_returns_prompt_without_workflow(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("No processing should occur for an empty message.")

    monkeypatch.setattr(orchestrator, "update_workflow", unexpected_call)

    result = orchestrator.process_request({"message": "   "})

    assert result["response"] == "Please enter your question."
    assert result["session_id"] == "local-session"


def test_blocked_input_does_not_reach_specialists(monkeypatch):
    events = []

    monkeypatch.setattr(
        orchestrator,
        "apply_guardrail",
        lambda text, source: (False, "Blocked"),
    )
    monkeypatch.setattr(
        orchestrator,
        "update_workflow",
        lambda *args, **kwargs: events.append("workflow"),
    )
    monkeypatch.setattr(
        orchestrator,
        "inventory_agent",
        lambda *args, **kwargs: events.append("inventory"),
    )
    monkeypatch.setattr(
        orchestrator,
        "communication_agent",
        lambda *args, **kwargs: events.append("communication"),
    )

    result = orchestrator.process_request({"message": "Help me with my order"})

    assert "contact NovaMart support" in result["response"]
    assert events == []


def test_workflow_initializes_before_specialists_and_communication_runs_last(
    monkeypatch,
):
    events = []

    def fake_update_workflow(session_id, request_text, intent, outcome):
        events.append(("workflow", outcome))

    def fake_lookup_order(order_id):
        events.append(("lookup_order", order_id))
        return {
            "order_id": order_id,
            "customer_id": "CUST-1001",
            "status": "Delivered",
        }

    def fake_lookup_customer(customer_id):
        events.append(("lookup_customer", customer_id))
        return {"customer_id": customer_id, "tier": "Standard"}

    def fake_inventory_agent(prompt):
        events.append(("inventory", None))
        return "Order record found."

    def fake_communication_agent(prompt):
        events.append(("communication", None))
        return "Your order information is available."

    monkeypatch.setattr(orchestrator, "update_workflow", fake_update_workflow)
    monkeypatch.setattr(orchestrator, "lookup_order", fake_lookup_order)
    monkeypatch.setattr(orchestrator, "lookup_customer", fake_lookup_customer)
    monkeypatch.setattr(orchestrator, "inventory_agent", fake_inventory_agent)
    monkeypatch.setattr(
        orchestrator, "communication_agent", fake_communication_agent
    )
    monkeypatch.setattr(
        orchestrator, "apply_guardrail", lambda text, source: (True, text)
    )

    result = orchestrator.process_request(
        {"session_id": "flow-test", "message": "Where is my order ORD-1001?"}
    )

    event_names = [event[0] for event in events]

    assert result["response"] == "Your order information is available."
    assert events[0] == ("workflow", "initialized")
    assert event_names.index("workflow") < event_names.index("inventory")
    assert event_names.index("inventory") < event_names.index("communication")
    assert events[-1] == ("workflow", result["response"])


def test_processing_failure_returns_safe_error(monkeypatch):
    def fail_workflow(*args, **kwargs):
        raise RuntimeError("Simulated workflow storage failure")

    monkeypatch.setattr(orchestrator, "update_workflow", fail_workflow)
    monkeypatch.setattr(
        orchestrator, "apply_guardrail", lambda text, source: (True, text)
    )

    result = orchestrator.process_request(
        {"session_id": "failure-test", "message": "Where is my order ORD-1001?"}
    )

    assert result["error"] == "processing_failed"
    assert "try again later" in result["response"]
    assert "Simulated workflow storage failure" not in result["response"]


def test_refund_agent_receives_decision_and_communication_runs_last(monkeypatch):
    events = []
    captured = {}

    def fake_update_workflow(session_id, request_text, intent, outcome):
        events.append(("workflow", outcome))

    def fake_lookup_order(order_id):
        events.append(("lookup_order", order_id))
        return {
            "order_id": order_id,
            "customer_id": "CUST-1001",
            "status": "Delivered",
            "days_since_delivery": 10,
        }

    def fake_lookup_customer(customer_id):
        events.append(("lookup_customer", customer_id))
        return {"customer_id": customer_id, "tier": "Standard"}

    def fake_decide_refund(order, customer):
        events.append(("decide_refund", None))
        return {
            "eligible": True,
            "decision": "eligible",
            "reason": "Delivered 10 days ago; Standard return window is 30 days.",
        }

    def fake_refund_agent(prompt):
        events.append(("refund_agent", None))
        captured["refund_prompt"] = prompt
        return "The order is eligible for a refund review."

    def fake_communication_agent(prompt):
        events.append(("communication", None))
        captured["communication_prompt"] = prompt
        return "Your order is eligible for a refund review."

    monkeypatch.setattr(orchestrator, "update_workflow", fake_update_workflow)
    monkeypatch.setattr(orchestrator, "lookup_order", fake_lookup_order)
    monkeypatch.setattr(orchestrator, "lookup_customer", fake_lookup_customer)
    monkeypatch.setattr(orchestrator, "decide_refund", fake_decide_refund)
    monkeypatch.setattr(orchestrator, "refund_agent", fake_refund_agent)
    monkeypatch.setattr(
        orchestrator, "communication_agent", fake_communication_agent
    )
    monkeypatch.setattr(
        orchestrator, "apply_guardrail", lambda text, source: (True, text)
    )

    result = orchestrator.process_request({
        "session_id": "refund-flow-test",
        "message": "Can I get a refund for order ORD-1001?",
    })

    event_names = [event[0] for event in events]

    assert result["intent"] == "refund"
    assert result["response"] == "Your order is eligible for a refund review."
    assert '"eligible": true' in captured["refund_prompt"]
    assert event_names.index("decide_refund") < event_names.index("refund_agent")
    assert event_names.index("refund_agent") < event_names.index("communication")
    assert events[-1] == ("workflow", result["response"])
