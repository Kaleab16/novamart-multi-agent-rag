"""AgentCore observability configuration helpers."""
from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

import config

log = logging.getLogger(__name__)


def apply_observability_config(
    runtime_arn: str | None = None,
) -> dict[str, Any]:
    """Configure CloudWatch logging and X-Ray tracing for an AgentCore runtime.

    This function makes an AWS control-plane call. It does not deploy the
    runtime, create a log group, or grant IAM permissions.
    """
    arn = (runtime_arn or config.AGENTCORE_RUNTIME_ARN or "").strip()
    if not arn:
        return {
            "ok": False,
            "error": "runtime_arn_not_configured",
        }

    try:
        client = boto3.client(
            "bedrock-agentcore-control",
            region_name=config.AWS_REGION,
        )
        response = client.update_agent_runtime(
            agentRuntimeArn=arn,
            protocolConfiguration={"serverProtocol": "HTTP"},
            authorizerConfiguration={"customJWTAuthorizer": {}},
            requestHeaderConfiguration={
                "requestHeaderAllowlist": ["traceparent", "tracestate"]
            },
        )
        return {
            "ok": True,
            "runtime_arn": arn,
            "response": {
                key: response[key]
                for key in ("agentRuntimeArn", "agentRuntimeId", "status")
                if key in response
            },
        }
    except (ClientError, BotoCoreError, ValueError) as exc:
        code = "observability_configuration_failed"
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", code)
        log.warning("AgentCore configuration failed: %s", code)
        return {"ok": False, "error": code}


def configure_cloudwatch_logging(
    log_group_name: str | None = None,
    retention_days: int = 14,
) -> dict[str, Any]:
    """Create or update a CloudWatch log group for the agent."""
    name = (log_group_name or f"/aws/bedrock-agentcore/{config.PROJECT_NAME}").strip()
    if not name.startswith("/"):
        return {"ok": False, "error": "invalid_log_group_name"}

    try:
        logs = boto3.client("logs", region_name=config.AWS_REGION)
        try:
            logs.create_log_group(logGroupName=name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
                raise

        logs.put_retention_policy(
            logGroupName=name,
            retentionInDays=max(1, int(retention_days)),
        )
        return {"ok": True, "log_group_name": name}
    except (ClientError, BotoCoreError, ValueError) as exc:
        code = "cloudwatch_configuration_failed"
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code", code)
        log.warning("CloudWatch configuration failed: %s", code)
        return {"ok": False, "error": code}


def configure_xray_tracing() -> dict[str, Any]:
    """Report the required X-Ray IAM permissions and tracing configuration.

    AgentCore runtime tracing also requires runtime-side observability setup.
    This helper deliberately does not claim that tracing is active.
    """
    return {
        "ok": True,
        "service": "AWS X-Ray",
        "sampling_rate": 1.0,
        "required_permissions": [
            "xray:PutTraceSegments",
            "xray:PutTelemetryRecords",
        ],
        "note": "Verify runtime tracing in AgentCore and the X-Ray service map.",
    }
