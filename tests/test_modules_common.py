"""Tests for declarative module exporting."""

from __future__ import annotations

from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieApiError


class FakeClient:
    def __init__(self, records=None, error: Exception | None = None) -> None:
        self.records = records or []
        self.error = error
        self.calls = []

    def paginate(self, endpoint, call_name, filters=None, style=None):
        self.calls.append((endpoint, call_name, filters, style))
        if self.error:
            raise self.error
        yield from self.records


def test_export_specs_writes_csv_and_applies_date_filter(tmp_path) -> None:
    """Endpoint specs are exported through the common pipeline."""

    client = FakeClient(records=[{"id": 1, "items": [{"sku": "A"}]}])
    spec = EndpointSpec(
        endpoint="x",
        call="ListarX",
        output_name="x",
        records_key="items",
        date_filter_fields=("data_de",),
        parent_id_field="id",
    )

    result = export_specs("demo", [spec], client, tmp_path, "16/06/2026")

    assert result.status == "ok"
    assert result.records == 1
    assert (tmp_path / "demo" / "x.csv").exists()
    assert client.calls[0][2]["data_de"] == "16/06/2026"


def test_export_specs_returns_error_result_on_api_error(tmp_path) -> None:
    """Endpoint API errors are captured in ModuleResult."""

    client = FakeClient(error=OmieApiError("boom"))
    spec = EndpointSpec(endpoint="x", call="ListarX", output_name="x")

    result = export_specs("demo", [spec], client, tmp_path, None)

    assert result.status == "error"
    assert result.records == 0
    assert result.errors == ["x: boom"]
