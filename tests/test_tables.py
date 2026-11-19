import pytest
from deltalake import DeltaTable

from riad_data.generate import generate
from riad_data.tables import SCHEMA_OF, onelake_uri, to_arrow, user_region_rows, write_tables

USERS = "north.mgr:N,center.mgr:C,south.mgr:S,pricing.director:*"


@pytest.fixture(scope="module")
def tables():
    return to_arrow(generate(), user_region_rows("example.onmicrosoft.com", USERS))


def test_user_region_rows_come_from_config():
    assert user_region_rows("Example.onmicrosoft.com", "North.Mgr:N, pricing.director:*") == [
        {"upn": "north.mgr@example.onmicrosoft.com", "region_id": "N"},
        {"upn": "pricing.director@example.onmicrosoft.com", "region_id": "*"},
    ]


@pytest.mark.parametrize(
    ("domain", "users"),
    [
        ("example.onmicrosoft.com", "north.mgr:X"),
        ("example.onmicrosoft.com", "north mgr:N"),
        ("example.onmicrosoft.com", "north.mgr]:N"),
        ("not a domain", "north.mgr:N"),
    ],
)
def test_bad_user_regions_are_rejected(domain, users):
    with pytest.raises(ValueError):
        user_region_rows(domain, users)


def test_every_table_converts_with_its_schema(tables):
    assert tables["fact_sales"].num_rows == 98_460
    assert str(tables["fact_sales"].schema.field("net_sales_mad").type) == "decimal128(12, 2)"
    assert str(tables["fact_sales"].schema.field("sale_date").type) == "date32[day]"
    assert tables["user_region"].num_rows == 4
    assert SCHEMA_OF["user_region"] == "rls" and SCHEMA_OF["fact_sales"] == "dbo"


def test_delta_tables_round_trip_with_a_protocol_fabric_reads(tmp_path, tables):
    written = write_tables(str(tmp_path), tables)
    assert "rls.user_region" in written and "dbo.fact_sales" in written
    sales = DeltaTable(str(tmp_path / "Tables" / "dbo" / "fact_sales"))
    assert sales.to_pyarrow_table().num_rows == 98_460
    protocol = sales.protocol()
    assert (protocol.min_reader_version, protocol.min_writer_version) == (1, 2)
    assert not protocol.writer_features  # no timestampNtz or other features the endpoint can't read


def test_overwrite_replaces_rather_than_appends(tmp_path, tables):
    write_tables(str(tmp_path), {"dim_region": tables["dim_region"]})
    write_tables(str(tmp_path), {"dim_region": tables["dim_region"]})
    assert (
        DeltaTable(str(tmp_path / "Tables" / "dbo" / "dim_region")).to_pyarrow_table().num_rows == 3
    )


def test_onelake_uri_uses_ids():
    assert onelake_uri("ws-id", "lh-id") == "abfss://ws-id@onelake.dfs.fabric.microsoft.com/lh-id"
