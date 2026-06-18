"""Finance exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="financas/contapagar",
        call="ListarContasPagar",
        output_name="contas_pagar",
        records_key="conta_pagar_cadastro",
        filters={"apenas_importado_api": "N"},
        date_filter_fields=("filtrar_por_data_de",),
        parent_id_field="codigo_lancamento_omie",
    ),
    EndpointSpec(
        endpoint="financas/contareceber",
        call="ListarContasReceber",
        output_name="contas_receber",
        records_key="conta_receber_cadastro",
        filters={"apenas_importado_api": "N"},
        date_filter_fields=("filtrar_por_data_de",),
        parent_id_field="codigo_lancamento_omie",
    ),
    EndpointSpec(
        endpoint="financas/mf",
        call="ListarMovimentos",
        output_name="movimentos_financeiros",
        records_key="movimentos",
        date_filter_fields=("dDtIncDe",),
        parent_id_field="nCodLanc",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export finance data."""

    return export_specs("financas", SPECS, client, output_dir, date_filter)
