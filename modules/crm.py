"""CRM exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="crm/contas",
        call="ListarContas",
        output_name="crm_contas",
        records_key="cadastros",
        parent_id_field="nCod",
    ),
    EndpointSpec(
        endpoint="crm/oportunidades",
        call="ListarOportunidades",
        output_name="crm_oportunidades",
        records_key="oportunidades",
        date_filter_fields=("dAltDe",),
        parent_id_field="nCodOportunidade",
    ),
    EndpointSpec(
        endpoint="crm/atividades",
        call="ListarAtividades",
        output_name="crm_atividades",
        records_key="atividades",
        date_filter_fields=("dAltDe",),
        parent_id_field="nCodAtividade",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export CRM data."""

    return export_specs("crm", SPECS, client, output_dir, date_filter)
