"""Tests for environment configuration."""

from __future__ import annotations

from config import load_settings


def _disable_dotenv(monkeypatch) -> None:
    monkeypatch.setattr("config.load_dotenv", lambda: None)
    monkeypatch.delenv("OMIE_PROFILES", raising=False)
    monkeypatch.delenv("OMIE_PROFILE_NAME", raising=False)


def test_load_settings_requires_local_path(monkeypatch) -> None:
    """Local storage requires STORAGE_LOCAL_PATH."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("OMIE_APP_KEY", "key")
    monkeypatch.setenv("OMIE_APP_SECRET", "secret")
    monkeypatch.setenv("BACKUP_MODE", "incremental")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.delenv("STORAGE_LOCAL_PATH", raising=False)

    try:
        load_settings()
    except ValueError as exc:
        assert "STORAGE_LOCAL_PATH" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_load_settings_reads_required_values(monkeypatch, tmp_path) -> None:
    """Settings are loaded from environment variables."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("OMIE_APP_KEY", "key")
    monkeypatch.setenv("OMIE_APP_SECRET", "secret")
    monkeypatch.setenv("BACKUP_MODE", "full")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("SMTP_TO", "a@example.com,b@example.com")

    settings = load_settings()

    assert settings.backup_mode == "full"
    assert settings.storage_local_path == tmp_path
    assert settings.smtp_to == ["a@example.com", "b@example.com"]
    assert settings.omie_profiles[0].name is None


def test_load_settings_supports_plain_smtp_security(monkeypatch, tmp_path) -> None:
    """SMTP_SECURITY=none enables plain SMTP for IP-whitelisted relays."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("OMIE_APP_KEY", "key")
    monkeypatch.setenv("OMIE_APP_SECRET", "secret")
    monkeypatch.setenv("BACKUP_MODE", "full")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.setenv("SMTP_TLS", "true")

    settings = load_settings()

    assert settings.smtp_security == "none"
    assert settings.smtp_tls is True


def test_load_settings_keeps_legacy_smtp_tls_false_as_ssl(monkeypatch, tmp_path) -> None:
    """Without SMTP_SECURITY, SMTP_TLS=false keeps the old SMTP_SSL behavior."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("OMIE_APP_KEY", "key")
    monkeypatch.setenv("OMIE_APP_SECRET", "secret")
    monkeypatch.setenv("BACKUP_MODE", "full")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.delenv("SMTP_SECURITY", raising=False)
    monkeypatch.setenv("SMTP_TLS", "false")

    settings = load_settings()

    assert settings.smtp_security == "ssl"


def test_load_settings_reads_named_omie_profiles(monkeypatch, tmp_path) -> None:
    """Multiple named OMIE credential profiles are loaded from prefixed variables."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("BACKUP_MODE", "incremental")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("OMIE_PROFILES", "client_a,client-b")
    monkeypatch.setenv("OMIE_PROFILE_CLIENT_A_APP_KEY", "key-a")
    monkeypatch.setenv("OMIE_PROFILE_CLIENT_A_APP_SECRET", "secret-a")
    monkeypatch.setenv("OMIE_PROFILE_CLIENT_B_APP_KEY", "key-b")
    monkeypatch.setenv("OMIE_PROFILE_CLIENT_B_APP_SECRET", "secret-b")

    settings = load_settings()

    assert [profile.name for profile in settings.omie_profiles] == ["client_a", "client-b"]
    assert [profile.app_key for profile in settings.omie_profiles] == ["key-a", "key-b"]
    assert settings.omie_app_key == "key-a"


def test_load_settings_requires_named_profile_credentials(monkeypatch, tmp_path) -> None:
    """Every named profile must define its own AppKey and Secret."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("BACKUP_MODE", "incremental")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("OMIE_PROFILES", "client_a")
    monkeypatch.setenv("OMIE_PROFILE_CLIENT_A_APP_KEY", "key-a")
    monkeypatch.delenv("OMIE_PROFILE_CLIENT_A_APP_SECRET", raising=False)

    try:
        load_settings()
    except ValueError as exc:
        assert "OMIE_PROFILE_CLIENT_A_APP_SECRET" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_load_settings_rejects_unsafe_profile_names(monkeypatch, tmp_path) -> None:
    """Profile names cannot contain path separators or shell-sensitive characters."""

    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("OMIE_APP_KEY", "key")
    monkeypatch.setenv("OMIE_APP_SECRET", "secret")
    monkeypatch.setenv("BACKUP_MODE", "incremental")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setenv("OMIE_PROFILE_NAME", "../client")

    try:
        load_settings()
    except ValueError as exc:
        assert "OMIE profile names" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
