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
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate_runtime_config(require_knowledge_bases: bool = False) -> list[str]:
    """Return missing configuration values without printing secrets."""
    required = ["AWS_REGION", "ORDERS_TABLE", "CUSTOMERS_TABLE",
                "WORKFLOW_STATE_TABLE"]
    if require_knowledge_bases:
        required += ["RETURNS_KB_ID", "SHIPPING_KB_ID", "WARRANTY_KB_ID"]
    values = {name: globals().get(name, "") for name in required}
    return [name for name, value in values.items() if not value]
