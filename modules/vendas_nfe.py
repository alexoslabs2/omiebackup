"""Sales and NF-e exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="produtos/pedido",
        call="ListarPedidos",
        output_name="pedidos_venda",
        records_key="pedido_venda_produto",
        filters={"apenas_importado_api": "N"},
        date_filter_fields=("filtrar_por_data_de",),
        parent_id_field="cabecalho.codigo_pedido",
    ),
    EndpointSpec(
        endpoint="produtos/nfe",
        call="ListarNFes",
        output_name="notas_fiscais_eletronicas",
        records_key="notas",
        date_filter_fields=("dEmiInicial",),
        parent_id_field="nIdNF",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export sales and NF-e data."""

    return export_specs("vendas_nfe", SPECS, client, output_dir, date_filter)
