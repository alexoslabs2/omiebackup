"""Purchasing, inventory, and production exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="produtos/pedidocompra",
        call="ListarPedidosCompra",
        output_name="pedidos_compra",
        records_key="pedidos_compra",
        date_filter_fields=("dAltDe",),
        parent_id_field="cabecalho.nCodPed",
    ),
    EndpointSpec(
        endpoint="estoque/consulta",
        call="ListarPosEstoque",
        output_name="posicao_estoque",
        records_key="produtos",
        parent_id_field="codigo_produto",
    ),
    EndpointSpec(
        endpoint="produtos/op",
        call="ListarOrdensProducao",
        output_name="ordens_producao",
        records_key="ordens_producao",
        date_filter_fields=("dAltDe",),
        parent_id_field="nCodOP",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export purchasing, inventory, and production data."""

    return export_specs("compras_estoque_producao", SPECS, client, output_dir, date_filter)
