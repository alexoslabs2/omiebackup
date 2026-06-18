"""General master data exports."""

from __future__ import annotations

from pathlib import Path

from config import ModuleResult
from modules.common import EndpointSpec, export_specs
from utils.omie_client import OmieClient

SPECS = [
    EndpointSpec(
        endpoint="geral/clientes",
        call="ListarClientes",
        output_name="clientes",
        records_key="clientes_cadastro",
        filters={"apenas_importado_api": "N"},
        parent_id_field="codigo_cliente_omie",
    ),
    EndpointSpec(
        endpoint="geral/produtos",
        call="ListarProdutos",
        output_name="produtos",
        records_key="produto_servico_cadastro",
        filters={"apenas_importado_api": "N"},
        parent_id_field="codigo_produto",
    ),
    EndpointSpec(
        endpoint="geral/categorias",
        call="ListarCategorias",
        output_name="categorias",
        records_key="categoria_cadastro",
        parent_id_field="codigo",
    ),
    EndpointSpec(
        endpoint="geral/contacorrente",
        call="ListarContasCorrentes",
        output_name="contas_correntes",
        records_key="ListarContasCorrentes",
        parent_id_field="nCodCC",
    ),
]


def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    """Export general OMIE data."""

    return export_specs("gerais", SPECS, client, output_dir, date_filter)
