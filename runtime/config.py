"""Central configuration for the NovaMart multi-agent application."""
import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PROJECT_NAME = os.getenv("PROJECT_NAME", "udacity-agentcore")
ORDERS_TABLE = os.getenv("ORDERS_TABLE", "udacity-agentcore-orders")
CUSTOMERS_TABLE = os.getenv("CUSTOMERS_TABLE", "udacity-agentcore-customers")
WORKFLOW_STATE_TABLE = os.getenv(
    "WORKFLOW_STATE_TABLE", "udacity-agentcore-workflow-state"
)

RETURNS_KB_ID = os.getenv("RETURNS_KB_ID", "")
SHIPPING_KB_ID = os.getenv("SHIPPING_KB_ID", "")
WARRANTY_KB_ID = os.getenv("WARRANTY_KB_ID", "")

AGENTCORE_RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")
AGENTCORE_ROLE_ARN = os.getenv("AGENTCORE_ROLE_ARN", "")
GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "")

BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
)
ORCHESTRATOR_MODEL_ID = os.getenv(
    "ORCHESTRATOR_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
WORKER_MODEL_ID = os.getenv(
    "WORKER_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
AGENT_LOG_GROUP = os.getenv(
    "AGENT_LOG_GROUP", f"/aws/bedrock-agentcore/{PROJECT_NAME}"
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate_runtime_config(require_knowledge_bases: bool = False) -> list[str]:
    """Return missing configuration values without printing secrets."""
    required = ["AWS_REGION", "ORDERS_TABLE", "CUSTOMERS_TABLE",
                "WORKFLOW_STATE_TABLE"]
    if require_knowledge_bases:
        required += ["RETURNS_KB_ID", "SHIPPING_KB_ID", "WARRANTY_KB_ID"]
    values = {name: globals().get(name, "") for name in required}
    return [name for name, value in values.items() if not value]

# MongoDB persistence
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "novamart")
