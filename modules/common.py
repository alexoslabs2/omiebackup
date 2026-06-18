"""Common helpers for declarative OMIE module exporters."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import ModuleResult
from utils.csv_writer import write_csv_records
from utils.omie_client import OmieApiError, OmieClient, PaginationStyle


@dataclass(frozen=True)
class EndpointSpec:
    """Declaration for one OMIE list endpoint export."""

    endpoint: str
    call: str
    output_name: str
    records_key: str | None = None
    page_field: str = "pagina"
    per_page_field: str = "registros_por_pagina"
    total_records_field: str = "total_de_registros"
    total_pages_field: str = "total_de_paginas"
    filters: Mapping[str, Any] = field(default_factory=dict)
    date_filter_fields: tuple[str, ...] = ()
    parent_id_field: str | None = None


def export_specs(
    module_name: str,
    specs: list[EndpointSpec],
    client: OmieClient,
    output_dir: Path,
    date_filter: str | None,
) -> ModuleResult:
    """Export all endpoint specs for a module."""

    logger = logging.getLogger(f"modules.{module_name}")
    module_dir = output_dir / module_name
    module_dir.mkdir(parents=True, exist_ok=True)

    total_records = 0
    files: list[str] = []
    errors: list[str] = []

    for spec in specs:
        try:
            filters = dict(spec.filters)
            if date_filter:
                for field_name in spec.date_filter_fields:
                    filters[field_name] = date_filter

            style = PaginationStyle(
                page_field=spec.page_field,
                per_page_field=spec.per_page_field,
                total_records_field=spec.total_records_field,
                total_pages_field=spec.total_pages_field,
                records_key=spec.records_key,
            )
            records = client.paginate(spec.endpoint, spec.call, filters=filters, style=style)
            writer_files = write_csv_records(
                records,
                module_dir,
                spec.output_name,
                parent_id_field=spec.parent_id_field,
            )
            record_count = _count_csv_rows(writer_files[0])
            total_records += record_count
            files.extend(str(path) for path in writer_files)
            logger.info("Exported %s records to %s", record_count, spec.output_name)
        except OmieApiError as exc:
            message = f"{spec.output_name}: {exc}"
            logger.error(message)
            errors.append(message)

    status = "error" if errors else "ok"
    return ModuleResult(
        module=module_name,
        status=status,
        records=total_records,
        files=files,
        errors=errors,
    )


def _count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as csv_file:
        return max(sum(1 for _ in csv_file) - 1, 0)
