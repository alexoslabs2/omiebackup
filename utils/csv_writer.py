"""Streaming CSV writer for OMIE records."""

from __future__ import annotations

import csv
import json
import tempfile
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class _RowSpool:
    def __init__(self, output_dir: Path, name: str) -> None:
        self.path = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=output_dir,
            prefix=f".{name}-",
            suffix=".rows",
        )
        self.fieldnames: OrderedDict[str, None] = OrderedDict()
        self.count = 0

    def write(self, row: dict[str, Any]) -> None:
        for key in row:
            self.fieldnames.setdefault(key, None)
        self.path.write(json.dumps(row, ensure_ascii=False, default=str))
        self.path.write("\n")
        self.count += 1

    def close(self) -> None:
        self.path.close()

    def unlink(self) -> None:
        Path(self.path.name).unlink(missing_ok=True)


class CsvExportWriter:
    """Write parent and child CSV files from streaming records."""

    def __init__(
        self,
        output_dir: Path,
        base_name: str,
        parent_id_field: str | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.base_name = base_name
        self.parent_id_field = parent_id_field
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._parent_spool = _RowSpool(output_dir, base_name)
        self._child_spools: dict[str, _RowSpool] = {}

    def write_records(self, records: Iterable[Mapping[str, Any]]) -> list[Path]:
        """Write records and return generated CSV file paths."""

        for record in records:
            self._add_record(record)
        return self.flush()

    def flush(self) -> list[Path]:
        """Write buffered rows to disk and return generated CSV file paths."""

        files: list[Path] = []
        parent_path = self.output_dir / f"{self.base_name}.csv"
        self._write_spool(parent_path, self._parent_spool)
        files.append(parent_path)

        for child_name, spool in sorted(self._child_spools.items()):
            child_path = self.output_dir / f"{self.base_name}_{child_name}.csv"
            self._write_spool(child_path, spool)
            files.append(child_path)

        return files

    def _add_record(self, record: Mapping[str, Any]) -> None:
        parent_id = self._parent_id(record)
        parent_row, children = _flatten_record(record)
        self._parent_spool.write(parent_row)

        for child_name, values in children:
            for item in values:
                if isinstance(item, Mapping):
                    child_row, grand_children = _flatten_record(item)
                else:
                    child_row, grand_children = {"valor": item}, []
                child_row = {"id_pai": parent_id, **child_row}
                self._child_spool(_csv_name(child_name)).write(child_row)

                for grand_name, grand_values in grand_children:
                    nested_name = _csv_name(f"{child_name}_{grand_name}")
                    for grand_item in grand_values:
                        if isinstance(grand_item, Mapping):
                            grand_row, _ = _flatten_record(grand_item)
                        else:
                            grand_row = {"valor": grand_item}
                        grand_row = {"id_pai": parent_id, **grand_row}
                        self._child_spool(nested_name).write(grand_row)

    def _parent_id(self, record: Mapping[str, Any]) -> str:
        if self.parent_id_field:
            value = _get_nested(record, self.parent_id_field)
            if value is not None:
                return str(value)
        fallback_keys = (
            "codigo_pedido",
            "numero_pedido",
            "codigo_lancamento_omie",
            "codigo_cliente_omie",
        )
        for key in fallback_keys:
            value = _get_nested(record, key)
            if value is not None:
                return str(value)
        return str(self._parent_spool.count + 1)

    def _child_spool(self, name: str) -> _RowSpool:
        if name not in self._child_spools:
            self._child_spools[name] = _RowSpool(self.output_dir, f"{self.base_name}_{name}")
        return self._child_spools[name]

    @staticmethod
    def _write_spool(path: Path, spool: _RowSpool) -> None:
        spool.close()
        fieldnames = list(spool.fieldnames)
        try:
            with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                with Path(spool.path.name).open("r", encoding="utf-8") as rows_file:
                    for line in rows_file:
                        row = json.loads(line)
                        writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})
        finally:
            spool.unlink()


def write_csv_records(
    records: Iterable[Mapping[str, Any]],
    output_dir: Path,
    base_name: str,
    parent_id_field: str | None = None,
) -> list[Path]:
    """Write records to CSV files and return generated paths."""

    return CsvExportWriter(output_dir, base_name, parent_id_field).write_records(records)


def _flatten_record(
    record: Mapping[str, Any],
    prefix: str = "",
) -> tuple[dict[str, Any], list[tuple[str, list[Any]]]]:
    row: dict[str, Any] = {}
    children: list[tuple[str, list[Any]]] = []

    for key, value in record.items():
        column = _csv_name(f"{prefix}_{key}" if prefix else key)
        if isinstance(value, Mapping):
            nested_row, nested_children = _flatten_record(value, column)
            row.update(nested_row)
            children.extend(nested_children)
        elif isinstance(value, list):
            children.append((column, value))
        else:
            row[column] = value

    return row, children


def _csv_name(value: str) -> str:
    return value.replace(".", "_").replace(" ", "_").replace("__", "_")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _get_nested(record: Mapping[str, Any], dotted_key: str) -> Any:
    current: Any = record
    for part in dotted_key.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current
