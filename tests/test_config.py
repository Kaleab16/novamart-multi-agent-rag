import config


def test_default_region():
    assert config.AWS_REGION


def test_table_names_are_configured():
    assert config.ORDERS_TABLE
    assert config.CUSTOMERS_TABLE
    assert config.WORKFLOW_STATE_TABLE
