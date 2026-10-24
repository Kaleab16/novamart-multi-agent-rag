"""MongoDB persistence for NovaMart."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

import config

_client = None
_database = None


def _db():
    """Connect lazily so imports do not require a live database."""
    global _client, _database

    if _database is not None:
        return _database

    uri = getattr(config, "MONGODB_URI", "")
    database_name = getattr(config, "MONGODB_DATABASE", "novamart")

    if not uri:
        raise RuntimeError("MONGODB_URI is not configured.")

    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")
    _database = _client[database_name]

    _database.orders.create_index("order_id", unique=True)
    _database.customers.create_index("customer_id", unique=True)
    _database.workflow_state.create_index("session_id", unique=True)

    return _database


def _clean(document: dict | None) -> dict | None:
    if document is None:
        return None
    document.pop("_id", None)
    return document


def get_order(order_id: str) -> dict | None:
    if not order_id:
        return None
    return _clean(_db().orders.find_one({"order_id": order_id}))


def get_customer(customer_id: str) -> dict | None:
    if not customer_id:
        return None
    return _clean(_db().customers.find_one({"customer_id": customer_id}))


def list_customer_orders(customer_id: str) -> list[dict]:
    if not customer_id or not customer_id.strip():
        return []

    cursor = _db().orders.find(
        {"customer_id": customer_id.strip()},
        {"_id": 0},
    ).sort("order_id", 1)

    return list(cursor)


def get_workflow(session_id: str) -> dict | None:
    if not session_id:
        return None
    return _clean(_db().workflow_state.find_one({"session_id": session_id}))


def update_workflow(
    session_id: str,
    request_text: str,
    intent: str,
    outcome: str,
) -> None:
    """Update workflow state with optimistic version checking."""
    if not session_id:
        raise ValueError("session_id is required")

    collection = _db().workflow_state
    now = datetime.now(timezone.utc).isoformat()

    for _attempt in range(3):
        current = collection.find_one(
            {"session_id": session_id},
            {"version": 1},
        )

        if current is None:
            try:
                collection.insert_one({
                    "session_id": session_id,
                    "version": 1,
                    "updated_at": now,
                    "last_request": request_text[:2000],
                    "last_intent": intent,
                    "last_outcome": outcome[:4000],
                })
                return
            except DuplicateKeyError:
                continue

        expected = int(current.get("version", 0))
        query: dict[str, Any] = {"session_id": session_id}

        if expected == 0:
            query["$or"] = [
                {"version": 0},
                {"version": {"$exists": False}},
            ]
        else:
            query["version"] = expected

        result = collection.update_one(
            query,
            {
                "$set": {
                    "updated_at": now,
                    "last_request": request_text[:2000],
                    "last_intent": intent,
                    "last_outcome": outcome[:4000],
                    "version": expected + 1,
                }
            },
        )

        if result.modified_count == 1:
            return

    raise RuntimeError("Could not update workflow after version conflicts.")


def ping() -> bool:
    """Verify that the configured MongoDB server is reachable."""
    _db()
    return True
