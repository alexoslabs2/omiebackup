# AGENTS.md — omie-backup

Script Python de backup diário da plataforma OMIE via API REST.
Extrai dados de todos os módulos (Gerais, CRM, Vendas/NF-e, Serviços/NFS-e,
Compras/Estoque/Produção e Finanças), converte para CSV, compacta e envia
para o destino de armazenamento configurado, com alertas por e-mail SMTP.

---

## Ambiente de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # preencher credenciais antes de rodar
```

Versão mínima: **Python 3.10**.

---

## Comandos essenciais

```bash
# Execução manual — modo incremental (padrão diário)
python backup.py --mode incremental

# Execução manual — backup full (primeira vez ou mensal)
python backup.py --mode full

# Rodar todos os testes
pytest tests/ -v

# Rodar testes de um módulo específico
pytest tests/test_financas.py -v

# Checar cobertura
pytest tests/ --cov=. --cov-report=term-missing

# Lint
flake8 . --max-line-length=100
```

Nunca rode `python backup.py` sem o argumento `--mode`. O script rejeita
execução sem modo explícito para evitar backups acidentais de escopo errado.

---

## Dependências

Apenas quatro pacotes externos — mantenha assim:

| Pacote         | Uso                                      |
|----------------|------------------------------------------|
| `requests`     | Chamadas HTTP à API OMIE                 |
| `tenacity`     | Retry com back-off exponencial           |
| `python-dotenv`| Variáveis de ambiente via `.env`         |
| `boto3`        | Upload para S3 (opcional, lazy-import)   |

`csv`, `smtplib`, `tarfile`, `hashlib`, `logging` — todos da stdlib.
**Não adicione dependências novas sem aprovação explícita.**

---

## Cliente da API OMIE (`utils/omie_client.py`)

Toda chamada à API passa por `OmieClient`. Nunca chame `requests` diretamente
nos módulos — use sempre o cliente.

```python
# Padrão correto
from utils.omie_client import OmieClient

client = OmieClient()
records = client.paginate("geral/clientes", "ListarClientes", filters={})
```

### Comportamento obrigatório do cliente

- Delay mínimo de `API_DELAY_MS` ms entre requisições (padrão: 300 ms).
- Retry automático em HTTP 429, 500 e 503 com back-off exponencial:
  1 s → 2 s → 4 s (máximo `API_MAX_RETRIES` tentativas, padrão: 3).
- Timeout de `API_TIMEOUT_SECONDS` segundos por requisição (padrão: 30).
- Log de cada chamada: endpoint, página, registros retornados, tempo de resposta.
- `APP_KEY` e `APP_SECRET` nunca aparecem em logs — mascarar com `****`.

### Paginação

```python
# O método paginate() itera automaticamente até esgotar total_de_registros.
# registros_por_pagina vem de API_RECORDS_PER_PAGE (padrão: 50).
# Não reimplemente paginação nos módulos — use paginate().
```

---

## Módulos (`modules/`)

Cada arquivo de módulo exporta uma função `export(client, output_dir, date_filter)`.
O orquestrador em `backup.py` chama todos em sequência.

```python
# Assinatura obrigatória para todo módulo
def export(client: OmieClient, output_dir: Path, date_filter: str | None) -> ModuleResult:
    ...
```

`ModuleResult` é um dataclass definido em `config.py`:
```python
@dataclass
class ModuleResult:
    module: str
    status: str          # "ok" | "warning" | "error"
    records: int
    files: list[str]
    errors: list[str]
```

---

## Conversão CSV (`utils/csv_writer.py`)

### Regras não-negociáveis

- Encoding: **UTF-8 com BOM** (`utf-8-sig`) — obrigatório para Excel BR.
- Separador: **ponto e vírgula** (`;`).
- Campos nulos → célula vazia (não `None`, não `"null"`).
- Objetos aninhados → achatados com notação de ponto como prefixo de coluna.
  Ex.: `endereco.cidade` → coluna `endereco_cidade`.
- Listas aninhadas (itens de pedido, parcelas) → arquivo CSV separado
  com sufixo `_itens`, contendo coluna `id_pai` para relacionamento.

```python
# Exemplo: pedido com itens
# pedidos_venda.csv       — registro pai
# pedidos_venda_itens.csv — lista det[], com coluna id_pai = numero_pedido
```

- Gravar linha a linha conforme os registros chegam da API (não acumular tudo
  em memória antes de salvar) — tolerância a falhas em volumes grandes.

---

## Armazenamento (`utils/storage.py`)

`StorageBackend` é uma classe abstrata. Implementações: `LocalStorage`,
`S3Storage`, `SftpStorage`. A fábrica `get_storage()` em `config.py` retorna
a implementação correta com base em `STORAGE_TYPE`.

Nunca instancie backends de armazenamento diretamente nos módulos.

---

## Alertas por e-mail (`utils/notifier.py`)

- Usa apenas `smtplib` e `email.mime` da stdlib — sem dependências externas.
- STARTTLS quando `SMTP_TLS=true` (porta 587); SSL direto quando `false` (porta 465).
- Enviar e-mail de resumo ao final de **toda** execução se `ALERT_ENABLED=true`.
- Gatilhos: sucesso (`ALERT_ON_SUCCESS`), warning, falha crítica, falha no storage,
  duração acima de `ALERT_MAX_DURATION_HOURS` (padrão: 4 h).
- Senha SMTP nunca logada — nem mascarada, simplesmente omitida dos logs.
- Corpo do e-mail em HTML; incluir versão texto-puro no `MIMEMultipart("alternative")`.

---

## Variáveis de ambiente

Todas as configurações vêm de `.env` (via `python-dotenv`).
Consulte `.env.example` para a lista completa.

Variáveis obrigatórias na inicialização — o script deve falhar imediatamente
se alguma estiver ausente:

```
BACKUP_MODE        # full | incremental
STORAGE_TYPE       # local | s3 | sftp
```

Credenciais OMIE podem ser configuradas de duas formas:

```
# Conta unica
OMIE_APP_KEY
OMIE_APP_SECRET
OMIE_PROFILE_NAME  # opcional; prefixa o nome do arquivo compactado

# Multiplas contas em uma execucao agendada
OMIE_PROFILES=cliente_a,cliente_b
OMIE_PROFILE_CLIENTE_A_APP_KEY
OMIE_PROFILE_CLIENTE_A_APP_SECRET
OMIE_PROFILE_CLIENTE_B_APP_KEY
OMIE_PROFILE_CLIENTE_B_APP_SECRET
```

Quando `OMIE_PROFILES` estiver definido, cada perfil roda isoladamente em
`OUTPUT_DIR/<perfil>/<data>/` e gera arquivo compactado `<perfil>_<data>.tar.gz`.
Falha em um perfil não deve impedir a tentativa dos demais; a execução retorna
código de erro se qualquer perfil falhar.

`STORAGE_LOCAL_PATH` é obrigatório quando `STORAGE_TYPE=local`.
`AWS_S3_BUCKET` é obrigatório quando `STORAGE_TYPE=s3`.

---

## Logging

- Usar o módulo `logging` da stdlib — não `print()`.
- Logger raiz configurado em `backup.py`; módulos usam `logging.getLogger(__name__)`.
- Nível padrão: `INFO`. Definir `LOG_LEVEL=DEBUG` no `.env` para troubleshooting.
- Formato: `%(asctime)s [%(levelname)s] %(name)s — %(message)s`
- Todo log vai para stdout **e** para `logs/backup-YYYY-MM-DD.log`.
- `APP_KEY`, `APP_SECRET` e `SMTP_PASSWORD` nunca aparecem em nenhum log.

---

## Segurança — regras absolutas

- **Nunca** commitar `.env`, `.env.local` ou qualquer arquivo com credenciais.
- **Nunca** logar valores de `APP_KEY`, `APP_SECRET` ou `SMTP_PASSWORD`.
- **Nunca** desabilitar verificação de certificado SSL (`verify=False` no requests).
- **Nunca** usar `shell=True` em `subprocess`.
- Credenciais chegam exclusivamente via variáveis de ambiente.

---

## Testes

- Framework: `pytest`.
- Mocks da API OMIE via `pytest-responses` ou `unittest.mock` — nunca chamar
  a API real em testes.
- Todo novo endpoint adicionado a um módulo exige ao menos um teste unitário
  cobrindo: paginação, conversão CSV e tratamento de erro da API.
- Testes de integração (que requerem credenciais reais) ficam em `tests/integration/`
  e são excluídos do CI padrão com `pytest -m "not integration"`.
- Cobertura mínima aceitável: **80%** nas linhas de `utils/`.

---

## Convenções de código

- Type hints obrigatórios em todas as funções públicas.
- Docstrings em funções públicas — uma linha de sumário é suficiente.
- Linha máxima: **100 caracteres**.
- F-strings para formatação de strings — não `.format()` nem `%`.
- Comparações com `None`: usar `is None` / `is not None`, nunca `== None`.
- Não usar `except Exception` sem re-raise ou log explícito do erro.

---

## O que NÃO fazer

- Não reimplementar paginação fora de `OmieClient.paginate()`.
- Não acumular todos os registros em memória antes de gravar — streaming obrigatório.
- Não usar `json.dumps` para salvar saída final — o formato de saída é CSV.
- Não criar arquivos temporários fora do diretório de saída do dia.
- Não alterar o separador CSV de `;` para `,` — quebra Excel BR.
- Não adicionar campos calculados nos CSVs — exportar apenas o que a API retorna.
- Não hardcodar URLs da API — usar a constante `OMIE_BASE_URL` de `config.py`.
