"""Reusable Amazon Bedrock Knowledge Bases retrieval helpers."""
from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

import config
from strands import tool

log = logging.getLogger(__name__)

_client = boto3.client(
    "bedrock-agent-runtime",
    region_name=config.AWS_REGION,
)


def retrieve_from_knowledge_base(
    knowledge_base_id: str,
    query: str,
    number_of_results: int = 5,
) -> dict[str, Any]:
    """Retrieve policy passages from a configured Bedrock Knowledge Base.

    Returns a structured error when the KB is not configured or retrieval
    fails. It does not generate answers or fabricate policy evidence.
    """
    if not knowledge_base_id or not knowledge_base_id.strip():
        return {
            "ok": False,
            "error": "knowledge_base_not_configured",
            "results": [],
        }

    if not query or not query.strip():
        return {
            "ok": False,
            "error": "query_required",
            "results": [],
        }

    count = max(1, min(int(number_of_results), 10))

    try:
        response = _client.retrieve(
            knowledgeBaseId=knowledge_base_id.strip(),
            retrievalQuery={"text": query.strip()},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": count,
                }
            },
        )

        results = []
        for item in response.get("retrievalResults", []):
            content = item.get("content", {})
            location = item.get("location", {})
            metadata = item.get("metadata", {})

            results.append({
                "text": content.get("text", ""),
                "score": item.get("score"),
                "location": location,
                "metadata": metadata,
            })

        return {
            "ok": True,
            "knowledge_base_id": knowledge_base_id.strip(),
            "query": query.strip(),
            "count": len(results),
            "results": results,
        }

    except (ClientError, BotoCoreError, ValueError) as exc:
        error_code = "retrieval_failed"
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get(
                "Code", error_code
            )
        log.warning("Knowledge Base retrieval failed: %s", error_code)
        return {
            "ok": False,
            "error": error_code,
            "results": [],
        }


def retrieve_all_policy_knowledge_bases(query: str) -> list[dict[str, Any]]:
    """Retrieve from the configured returns, shipping, and warranty KBs."""
    knowledge_bases = [
        ("returns", config.RETURNS_KB_ID),
        ("shipping", config.SHIPPING_KB_ID),
        ("warranty", config.WARRANTY_KB_ID),
    ]

    return [
        {
            "policy_type": label,
            **retrieve_from_knowledge_base(kb_id, query),
        }
        for label, kb_id in knowledge_bases
    ]


@tool
def retrieve_returns_policy(query: str) -> dict[str, Any]:
    """Search NovaMart's returns and refunds policy knowledge base."""
    return retrieve_from_knowledge_base(config.RETURNS_KB_ID, query)


@tool
def retrieve_shipping_policy(query: str) -> dict[str, Any]:
    """Search NovaMart's shipping policy knowledge base."""
    return retrieve_from_knowledge_base(config.SHIPPING_KB_ID, query)


@tool
def retrieve_warranty_policy(query: str) -> dict[str, Any]:
    """Search NovaMart's warranty policy knowledge base."""
    return retrieve_from_knowledge_base(config.WARRANTY_KB_ID, query)
