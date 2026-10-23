# NovaMart Multi-Agent E-commerce RAG

A learning project for a multi-agent customer-support workflow using Amazon
Bedrock, Strands Agents, Bedrock Knowledge Bases, DynamoDB, and AgentCore Runtime.

## Agents

- Orchestrator: routes customer intent.
- Inventory: reads order and customer records from DynamoDB.
- Policy: retrieves from returns, shipping, and warranty Knowledge Bases in parallel.
- Refund: evaluates sample return-window rules (Standard: 30 days; Premium: 60 days).
- Communication: writes the final customer-facing response.

## Local setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with resource IDs after creating AWS resources. Never commit `.env`.

## AWS setup

The AWS account must have permission to create CloudFormation stacks, DynamoDB
tables, S3 resources, IAM roles, and Bedrock resources in `us-east-1`. Deploy the
CloudFormation template only after reviewing it and confirming your lab permissions.

## Seed sample data

```bash
python infrastructure/seed_data.py
```

This inserts fictional example records into the configured DynamoDB tables.

## Tests

```bash
pytest -q
```

## Important

This repository is a scaffold built from the project overview and requirements
available to the learner. It is not represented as the official Udacity starter.
Verify the current AgentCore Runtime and Strands SDK APIs against their official
documentation before deployment. Do not use real customer data in the sample tables.
