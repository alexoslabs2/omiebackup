"""Tests for CSV export writing."""

from __future__ import annotations

import csv

from utils.csv_writer import write_csv_records


def test_write_csv_records_flattens_nested_data_and_child_lists(tmp_path) -> None:
    """Nested objects are flattened and lists become child CSV files."""

    records = [
        {
            "codigo_pedido": 123,
            "cliente": {"nome": "Acme", "cidade": None},
            "det": [{"produto": {"codigo": "P1"}, "quantidade": 2}],
        }
    ]

    files = write_csv_records(records, tmp_path, "pedidos", parent_id_field="codigo_pedido")

    assert tmp_path / "pedidos.csv" in files
    assert tmp_path / "pedidos_det.csv" in files

    raw = (tmp_path / "pedidos.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    with (tmp_path / "pedidos.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file, delimiter=";"))

    assert rows == [{"codigo_pedido": "123", "cliente_nome": "Acme", "cliente_cidade": ""}]

    with (tmp_path / "pedidos_det.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        child_rows = list(csv.DictReader(csv_file, delimiter=";"))

    assert child_rows == [{"id_pai": "123", "produto_codigo": "P1", "quantidade": "2"}]
