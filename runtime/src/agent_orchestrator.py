"""NovaMart multi-agent customer-support application.

The runtime entrypoint routes requests to specialist agents. AWS resources
must exist and the required environment variables must be configured before
using the deployed application.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from strands import Agent
from strands.models import BedrockModel

import config
try:
    from . import mongodb_store
    # Package imports used by pytest and `import src.agent_orchestrator`.
    from .agent_utils import (
        check_order_status,
        get_customer_tier,
        list_customer_orders,
        get_inventory_context,
        initiate_refund,
        get_full_workflow_context,
    )
    from .bedrock_kb_retrieval import (
        retrieve_returns_policy,
        retrieve_shipping_policy,
        retrieve_warranty_policy,
    )
except ImportError:
    # Fallback for direct execution: `python src/agent_orchestrator.py`.
    import mongodb_store
    from agent_utils import (
        check_order_status,
        get_customer_tier,
        list_customer_orders,
        get_inventory_context,
        initiate_refund,
        get_full_workflow_context,
    )
    from bedrock_kb_retrieval import (
        retrieve_returns_policy,
        retrieve_shipping_policy,
        retrieve_warranty_policy,
    )

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("novamart")

session = boto3.Session(region_name=config.AWS_REGION)
bedrock_agent_runtime = session.client("bedrock-agent-runtime")
bedrock_runtime = session.client("bedrock-runtime")

def _make_model(model_id: str, temperature: float) -> BedrockModel:
    """Create a Bedrock model with an explicit sampling temperature."""
    return BedrockModel(
        model_id=model_id,
        region_name=config.AWS_REGION,
        temperature=temperature,
    )


inventory_agent = Agent(
    model=_make_model(config.WORKER_MODEL_ID, 0.1),
    tools=[check_order_status, get_customer_tier, list_customer_orders],
    system_prompt=(
        "You are NovaMart's Inventory Support specialist. Use the supplied "
        "records and tools. Never invent an order, delivery date, or account "
        "fact. If data is missing, say what identifier is needed."
    ),
)

refund_agent = Agent(
    model=_make_model(config.WORKER_MODEL_ID, 0.1),
    tools=[get_inventory_context, initiate_refund],
    system_prompt=(
        "You are NovaMart's Refund specialist. Explain the supplied refund "
        "eligibility decision using only the provided order, customer, and "
        "decision data. The supplied deterministic decision is authoritative. "
        "Never change eligibility, promise a refund, or claim money was issued."
    ),
)

policy_agent = Agent(
    model=_make_model(config.WORKER_MODEL_ID, 0.0),
    tools=[
        retrieve_returns_policy,
        retrieve_shipping_policy,
        retrieve_warranty_policy,
    ],
    system_prompt=(
        "You are NovaMart's Policy specialist. Search the relevant policy "
        "knowledge bases using the provided tools. Answer only from retrieved "
        "policy passages. Distinguish policy facts from unknowns and cite "
        "the relevant source where possible."
    ),
)

communication_agent = Agent(
    model=_make_model(config.WORKER_MODEL_ID, 0.3),
    tools=[get_full_workflow_context],
    system_prompt=(
        "You are NovaMart's customer communication specialist. Write a concise, "
        "professional, empathetic response. Use only facts and decisions provided "
        "by the preceding specialists. Never claim a refund was issued unless "
        "the workflow explicitly says it was issued."
    ),
)


def _plain(value: Any) -> Any:
    """Convert DynamoDB Decimal values to JSON-friendly values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def apply_guardrail(text: str, source: str) -> tuple[bool, str]:
    """Return (allowed, text); fail closed if a configured guardrail errors."""
    if not config.GUARDRAIL_ID or not config.GUARDRAIL_VERSION:
        log.warning("Guardrail not configured; request is not guardrail-screened.")
        return True, text

    try:
        result = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=config.GUARDRAIL_ID,
            guardrailVersion=config.GUARDRAIL_VERSION,
            source=source,
            content=[{"text": {"text": text}}],
        )
        action = result.get("action", "NONE")
        if action == "GUARDRAIL_INTERVENED":
            return False, "I can't help with that request. Please contact NovaMart support."
        return True, text
    except ClientError:
        log.exception("Guardrail API call failed")
        return False, "I can't safely process this request right now. Please try again later."


def route_intent(message: str) -> str:
    """Route customer requests using intent keywords and known ID formats."""
    import re

    text = message.lower()

    if any(word in text for word in ("refund", "return", "exchange", "eligible")):
        return "refund"
    if any(word in text for word in ("policy", "warranty", "shipping rule", "return window")):
        return "policy"

    if re.search(r"\bcust[- ]?\d{4,}\b", text):
        return "account"
    if re.search(r"\bord[- ]?\d{4,}\b", text):
        return "order"

    if any(word in text for word in ("tier", "membership", "my account", "customer account")):
        return "account"
    if any(word in text for word in ("order", "tracking", "delivery", "shipped", "arrived")):
        return "order"
    if any(word in text for word in ("calculate", "what is", "how much", "discount", "percent")):
        return "math"

    return "general"

def lookup_order(order_id: str) -> dict[str, Any] | None:
    return mongodb_store.get_order(order_id)


def lookup_customer(customer_id: str) -> dict[str, Any] | None:
    return mongodb_store.get_customer(customer_id)


def get_policy(kb_id: str, query: str, label: str) -> dict[str, Any]:
    if not kb_id:
        return {"source": label, "error": "Knowledge Base ID is not configured.", "passages": []}
    try:
        result = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": 4}
            },
        )
        passages = []
        for item in result.get("retrievalResults", []):
            passages.append({
                "text": item.get("content", {}).get("text", ""),
                "location": item.get("location", {}),
                "score": item.get("score"),
            })
        return {"source": label, "passages": passages}
    except ClientError as exc:
        log.exception("Knowledge Base retrieval failed: %s", label)
        return {
            "source": label,
            "error": exc.response.get("Error", {}).get("Code", "Retrieval failed"),
            "passages": [],
        }


def retrieve_all_policies(query: str) -> list[dict[str, Any]]:
    """Query returns, shipping, and warranty KBs concurrently."""
    targets = [
        (config.RETURNS_KB_ID, query, "returns"),
        (config.SHIPPING_KB_ID, query, "shipping"),
        (config.WARRANTY_KB_ID, query, "warranty"),
    ]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(get_policy, *target) for target in targets]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def decide_refund(order: dict[str, Any] | None,
                  customer: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the project sample rule: Standard 30 days, Premium 60 days."""
    if not order:
        return {"eligible": False, "reason": "Order not found.", "decision": "needs_review"}
    if not customer:
        return {"eligible": False, "reason": "Customer not found.", "decision": "needs_review"}
    if order.get("status") != "Delivered":
        return {
            "eligible": False,
            "reason": "The order is not marked as delivered.",
            "decision": "not_eligible",
        }

    tier = str(customer.get("tier", "Standard")).lower()
    window = 60 if tier == "premium" else 30
    days = int(order.get("days_since_delivery", 999999))
    eligible = days <= window
    return {
        "eligible": eligible,
        "reason": (
            f"Delivered {days} days ago; {tier.title()} return window is {window} days."
        ),
        "decision": "eligible" if eligible else "not_eligible",
        "return_window_days": window,
    }


def update_workflow(session_id: str, request_text: str, intent: str,
                    outcome: str) -> None:
    """Persist workflow state in MongoDB."""
    mongodb_store.update_workflow(
        session_id=session_id,
        request_text=request_text,
        intent=intent,
        outcome=outcome,
    )


def initialize_session(
    session_id: str, request_text: str, intent: str
) -> None:
    """Persist the initial workflow state before specialist processing."""
    update_workflow(session_id, request_text, intent, "initialized")


def calculate_math(message: str) -> str:
    """Safely calculate simple arithmetic or a percentage of a number."""
    import ast
    import operator
    import re

    percentage = re.search(
        r"(-?\d+(?:\.\d+)?)\s*%\s*of\s*(-?\d+(?:\.\d+)?)",
        message,
        re.IGNORECASE,
    )
    if percentage:
        rate, amount = map(float, percentage.groups())
        return f"{rate:g}% of {amount:g} = {amount * rate / 100:g}."

    match = re.search(
        r"(?<![\w.])-?\d+(?:\.\d+)?"
        r"(?:\s*[+*/^\-]\s*-?\d+(?:\.\d+)?)+",
        message,
    )
    if not match:
        return "Please provide a clear arithmetic expression or percentage question."

    expression = match.group(0).replace("^", "**")
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent too large")
            result = operations[type(node.op)](left, right)
            if abs(result) > 1e15:
                raise ValueError("Result too large")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.operand))
        raise ValueError("Unsupported expression")

    try:
        result = evaluate(ast.parse(expression, mode="eval"))
        return f"{match.group(0).strip()} = {result:g}."
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return "I couldn't safely calculate that expression. Please check it and try again."


def _extract_identifier(message: str, prefix: str) -> str | None:
    import re
    match = re.search(rf"\b{prefix}[- ]?(\d{{4,}})\b", message, re.IGNORECASE)
    return f"{prefix.upper()}-{match.group(1)}" if match else None


def process_request(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    session_id = str(payload.get("session_id") or payload.get("sessionId") or "local-session")
    if not message:
        return {"session_id": session_id, "response": "Please enter your question."}

    allowed, _ = apply_guardrail(message, "INPUT")
    if not allowed:
        return {"session_id": session_id, "response": "I can't help with that request. Please contact NovaMart support."}

    intent = route_intent(message)
    evidence: dict[str, Any] = {"intent": intent}
    order_id = payload.get("order_id") or _extract_identifier(message, "ORD")
    customer_id = payload.get("customer_id") or _extract_identifier(message, "CUST")

    try:
        # Initialize the workflow session before any specialist work.
        initialize_session(session_id, message, intent)

        if intent in ("order", "refund", "account"):
            order = lookup_order(str(order_id)) if order_id else None
            customer = lookup_customer(str(customer_id)) if customer_id else None

            if order and not customer:
                customer = lookup_customer(str(order.get("customer_id", "")))

            evidence.update({"order": order, "customer": customer})

            if intent == "refund":
                decision = decide_refund(order, customer)
                evidence["refund_decision"] = decision
                specialist_result = str(refund_agent(
                    f"Customer request: {message}\n"
                    f"Order record: {json.dumps(order, default=str)}\n"
                    f"Customer record: {json.dumps(customer, default=str)}\n"
                    f"Authoritative refund eligibility decision: "
                    f"{json.dumps(decision)}\n"
                    "This is an eligibility decision only. No refund has been issued."
                ))
            else:
                specialist_result = str(inventory_agent(
                    f"Customer request: {message}\n"
                    f"Order record: {json.dumps(order, default=str)}\n"
                    f"Customer record: {json.dumps(customer, default=str)}"
                ))

        elif intent == "policy":
            policies = retrieve_all_policies(message)
            evidence["policy_retrieval"] = policies
            specialist_result = str(policy_agent(
                f"Customer question: {message}\n"
                f"Retrieved policy passages (treat these as the only evidence):\n"
                f"{json.dumps(policies, default=str)}"
            ))

        elif intent == "math":
            specialist_result = calculate_math(message)

        else:
            specialist_result = (
                "No specialist route matched. Ask one concise clarifying question "
                "or explain which order/customer identifier is needed."
            )

        # Communication agent is always the final specialist.
        draft = str(communication_agent(
            f"Customer message: {message}\n"
            f"Intent: {intent}\n"
            f"Specialist findings and evidence: {specialist_result}\n"
            "Write the final customer-facing response. Do not invent missing facts."
        ))

        output_allowed, safe_response = apply_guardrail(draft, "OUTPUT")
        if not output_allowed:
            safe_response = "I can't provide that response safely. Please contact NovaMart support."

        update_workflow(session_id, message, intent, safe_response)
        return {
            "session_id": session_id,
            "intent": intent,
            "response": safe_response,
            "evidence": evidence,
        }

    except Exception:
        log.exception("Request processing failed")
        return {
            "session_id": session_id,
            "intent": intent,
            "response": (
                "I'm unable to complete this request right now. Please try again "
                "later or contact NovaMart support."
            ),
            "error": "processing_failed",
        }


try:
    from bedrock_agentcore import BedrockAgentCoreApp
    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        return process_request(payload)

except ImportError:
    app = None


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "test-local":
        print(json.dumps(process_request({
            "session_id": "local-test",
            "message": "What is the return policy for ORD-1001?",
        }), indent=2, default=str))
        return

    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        print(
            "Runtime deployment is not wired into this command yet. "
            "Install/configure the AgentCore CLI and complete .env first."
        )
        raise SystemExit(2)

    if app is None:
        print("Install bedrock-agentcore to run the AgentCore entrypoint.")
        raise SystemExit(2)
    app.run()


if __name__ == "__main__":
    main()
