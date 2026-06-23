"""Tests for the OMIE API client."""

from __future__ import annotations

from config import Settings
from utils.omie_client import OmieClient, PaginationStyle


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.responses.pop(0)


def test_paginate_yields_all_pages(monkeypatch) -> None:
    """paginate keeps fetching until total records are exhausted."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "pagina": 1,
                    "total_de_registros": 3,
                    "clientes_cadastro": [{"id": 1}, {"id": 2}],
                },
            ),
            FakeResponse(
                200,
                {
                    "pagina": 2,
                    "total_de_registros": 3,
                    "clientes_cadastro": [{"id": 3}],
                },
            ),
        ]
    )
    client = OmieClient(_settings(records_per_page=2), session=session)

    records = list(
        client.paginate(
            "geral/clientes",
            "ListarClientes",
            style=PaginationStyle(records_key="clientes_cadastro"),
        )
    )

    assert records == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert session.calls[0]["json"]["app_key"] == "key"
    assert session.calls[1]["json"]["param"][0]["pagina"] == 2


def test_call_retries_retryable_http(monkeypatch) -> None:
    """HTTP 429 is retried according to retry settings."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    session = FakeSession(
        [
            FakeResponse(429, {"fault": "slow down"}),
            FakeResponse(200, {"data": [{"ok": True}]}),
        ]
    )
    client = OmieClient(_settings(max_retries=2), session=session)

    response = client.call("geral/clientes", "ListarClientes", {})

    assert response == {"data": [{"ok": True}]}
    assert len(session.calls) == 2


def test_paginate_supports_nfse_pagination_style(monkeypatch) -> None:
    """NFSe-style pagination names are supported."""

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "nPagina": 1,
                    "nTotRegistros": 1,
                    "nfseEncontradas": [{"nCodNF": 10}],
                },
            )
        ]
    )
    client = OmieClient(_settings(), session=session)

    records = list(
        client.paginate(
            "servicos/nfse",
            "ListarNFSEs",
            style=PaginationStyle(
                page_field="nPagina",
                per_page_field="nRegPorPagina",
                total_records_field="nTotRegistros",
                total_pages_field="nTotPaginas",
                records_key="nfseEncontradas",
            ),
        )
    )

    assert records == [{"nCodNF": 10}]
    assert session.calls[0]["json"]["param"][0]["nPagina"] == 1
    assert session.calls[0]["json"]["param"][0]["nRegPorPagina"] == 50


def _settings(records_per_page: int = 50, max_retries: int = 3) -> Settings:
    return Settings(
        omie_app_key="key",
        omie_app_secret="secret",
        backup_mode="incremental",
        storage_type="local",
        storage_local_path=None,
        aws_s3_bucket=None,
        aws_s3_prefix="omie-backup",
        aws_region=None,
        sftp_host=None,
        sftp_port=22,
        sftp_username=None,
        sftp_key_file=None,
        sftp_remote_path="/omie-backup",
        api_delay_ms=0,
        api_max_retries=max_retries,
        api_timeout_seconds=30,
        api_records_per_page=records_per_page,
        alert_enabled=False,
        alert_on_success=False,
        alert_max_duration_hours=4,
        smtp_host=None,
        smtp_port=587,
        smtp_security="starttls",
        smtp_tls=True,
        smtp_username=None,
        smtp_password=None,
        smtp_from=None,
        smtp_to=[],
        log_level="INFO",
        output_dir=None,
    )
