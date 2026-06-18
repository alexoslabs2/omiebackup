"""Services and NFS-e exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="servicos/os",
        call="ListarOS",
        output_name="ordens_servico",
        records_key="osCadastro",
        date_filter_fields=("dAltDe",),
        parent_id_field="Cabecalho.nCodOS",
    ),
    EndpointSpec(
        endpoint="servicos/nfse",
        call="ListarNFSEs",
        output_name="notas_servico",
        records_key="nfseEncontradas",
        page_field="nPagina",
        per_page_field="nRegPorPagina",
        total_records_field="nTotRegistros",
        total_pages_field="nTotPaginas",
        date_filter_fields=("dEmiInicial",),
        parent_id_field="Cabecalho.nCodNF",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export service and NFS-e data."""

    return export_specs("servicos_nfse", SPECS, client, output_dir, date_filter)
