# omie-backup

Backup diario da plataforma OMIE via API REST.

O projeto extrai dados por modulo, grava CSV em formato compativel com Excel BR,
compacta os arquivos do dia, envia para o storage configurado e opcionalmente
manda um resumo por e-mail SMTP.

## Uso

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Preencha `.env` e execute sempre com modo explicito:

```bash
python backup.py --mode incremental
python backup.py --mode full
```

## Multiplas contas OMIE

Para fazer backup de varias contas OMIE em uma unica execucao agendada, defina
perfis nomeados no `.env`:

```env
OMIE_PROFILES=client_a,client_b

OMIE_PROFILE_CLIENT_A_APP_KEY=
OMIE_PROFILE_CLIENT_A_APP_SECRET=

OMIE_PROFILE_CLIENT_B_APP_KEY=
OMIE_PROFILE_CLIENT_B_APP_SECRET=
```

Cada perfil gera arquivos intermediarios isolados e um pacote compactado com
nome `perfil_data`:

```text
backups/client_a/2026-06-17/
backups/client_b/2026-06-17/
backups/client_a_2026-06-17.tar.gz
backups/client_b_2026-06-17.tar.gz
```

Se `OMIE_PROFILES` nao estiver definido, o modo antigo com `OMIE_APP_KEY` e
`OMIE_APP_SECRET` continua funcionando.

## Testes

```bash
pytest tests/ -v
```
