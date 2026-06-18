"""Tests for backup orchestration helpers."""

from __future__ import annotations

import tarfile
from datetime import datetime

from backup import _create_archive, _profile_output_dir
from config import OmieProfile, Settings


def test_profile_output_dir_uses_profile_and_date(tmp_path) -> None:
    """Named profiles write intermediate CSV files under profile/date folders."""

    settings = _settings(tmp_path)
    profile = OmieProfile(name="client_a", app_key="key", app_secret="secret")

    output_dir = _profile_output_dir(settings, profile, datetime(2026, 6, 17, 8, 0))

    assert output_dir == tmp_path / "client_a" / "2026-06-17"


def test_create_archive_prefixes_named_profile(tmp_path) -> None:
    """Named profile archives use profile_date naming and preserve profile paths."""

    output_dir = tmp_path / "client_a" / "2026-06-17"
    module_dir = output_dir / "gerais"
    module_dir.mkdir(parents=True)
    (module_dir / "clientes.csv").write_text("id;nome\n1;Acme\n", encoding="utf-8")

    archive_path = _create_archive(output_dir, "client_a")

    assert archive_path == tmp_path / "client_a_2026-06-17.tar.gz"
    with tarfile.open(archive_path, "r:gz") as archive:
        assert archive.getnames() == ["client_a/2026-06-17/gerais/clientes.csv"]


def _settings(output_dir) -> Settings:
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
        api_max_retries=3,
        api_timeout_seconds=30,
        api_records_per_page=50,
        alert_enabled=False,
        alert_on_success=False,
        alert_max_duration_hours=4,
        smtp_host=None,
        smtp_port=587,
        smtp_tls=True,
        smtp_username=None,
        smtp_password=None,
        smtp_from=None,
        smtp_to=[],
        log_level="INFO",
        output_dir=output_dir,
    )
