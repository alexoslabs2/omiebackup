"""Backup modules."""

from modules import compras_estoque_producao, crm, financas, gerais, servicos_nfse, vendas_nfe

EXPORT_MODULES = [
    gerais,
    crm,
    vendas_nfe,
    servicos_nfse,
    compras_estoque_producao,
    financas,
]
