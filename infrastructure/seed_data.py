"""Seed fictional NovaMart orders and customers into DynamoDB."""
import boto3
from botocore.exceptions import ClientError
import config

dynamodb = boto3.resource("dynamodb", region_name=config.AWS_REGION)

CUSTOMERS = [
    {
        "customer_id": "CUST-1001",
        "name": "Amina Bekele",
        "email": "amina@example.com",
        "tier": "Premium",
    },
    {
        "customer_id": "CUST-1002",
        "name": "Daniel Tesfaye",
        "email": "daniel@example.com",
        "tier": "Standard",
    },
]

ORDERS = [
    {
        "order_id": "ORD-1001",
        "customer_id": "CUST-1001",
        "item": "Wireless Headphones",
        "price": 120.00,
        "currency": "USD",
        "status": "Delivered",
        "days_since_delivery": 12,
        "return_requested": False,
    },
    {
        "order_id": "ORD-1002",
        "customer_id": "CUST-1002",
        "item": "Laptop Stand",
        "price": 45.00,
        "currency": "USD",
        "status": "Delivered",
        "days_since_delivery": 40,
        "return_requested": False,
    },
    {
        "order_id": "ORD-1003",
        "customer_id": "CUST-1001",
        "item": "USB-C Hub",
        "price": 65.00,
        "currency": "USD",
        "status": "Shipped",
        "days_since_delivery": 0,
        "return_requested": False,
    },
]


def seed_table(table_name: str, items: list[dict]) -> None:
    table = dynamodb.Table(table_name)
    for item in items:
        table.put_item(Item=item)
    print(f"Seeded {len(items)} items into {table_name}")


def main() -> None:
    try:
        seed_table(config.CUSTOMERS_TABLE, CUSTOMERS)
        seed_table(config.ORDERS_TABLE, ORDERS)
    except ClientError as exc:
        print("Seeding failed. Confirm the CloudFormation stack and IAM permissions.")
        print(f"AWS error: {exc.response.get('Error', {}).get('Code', 'Unknown')}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
