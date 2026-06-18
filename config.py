"""Application configuration and shared dataclasses."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

OMIE_BASE_URL = "https://app.omie.com.br/api/v1"

BackupMode = Literal["full", "incremental"]
ResultStatus = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class OmieProfile:
    """Named OMIE credential profile."""

    name: str | None
    app_key: str
    app_secret: str


@dataclass
class ModuleResult:
    """Result emitted by a module export."""

    module: str
    status: ResultStatus
    records: int
    files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    omie_app_key: str
    omie_app_secret: str
    backup_mode: BackupMode
    storage_type: str
    storage_local_path: Path | None
    aws_s3_bucket: str | None
    aws_s3_prefix: str
    aws_region: str | None
    sftp_host: str | None
    sftp_port: int
    sftp_username: str | None
    sftp_key_file: Path | None
    sftp_remote_path: str
    api_delay_ms: int
    api_max_retries: int
    api_timeout_seconds: int
    api_records_per_page: int
    alert_enabled: bool
    alert_on_success: bool
    alert_max_duration_hours: float
    smtp_host: str | None
    smtp_port: int
    smtp_tls: bool
    smtp_username: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_to: list[str]
    log_level: str
    output_dir: Path
    omie_profiles: tuple[OmieProfile, ...] = field(default_factory=tuple)


def load_settings() -> Settings:
    """Load settings from .env and validate required values."""

    load_dotenv()

    required = ["BACKUP_MODE", "STORAGE_TYPE"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    omie_profiles = _omie_profiles()
    backup_mode = _backup_mode(os.environ["BACKUP_MODE"])
    storage_type = os.environ["STORAGE_TYPE"].lower()

    storage_local_path = _optional_path(os.getenv("STORAGE_LOCAL_PATH"))
    aws_s3_bucket = _optional_str(os.getenv("AWS_S3_BUCKET"))

    if storage_type == "local" and storage_local_path is None:
        raise ValueError("STORAGE_LOCAL_PATH is required when STORAGE_TYPE=local")
    if storage_type == "s3" and not aws_s3_bucket:
        raise ValueError("AWS_S3_BUCKET is required when STORAGE_TYPE=s3")
    if storage_type == "sftp":
        for name in ["SFTP_HOST", "SFTP_USERNAME", "SFTP_KEY_FILE"]:
            if not os.getenv(name):
                raise ValueError(f"{name} is required when STORAGE_TYPE=sftp")

    return Settings(
        omie_app_key=omie_profiles[0].app_key,
        omie_app_secret=omie_profiles[0].app_secret,
        backup_mode=backup_mode,
        storage_type=storage_type,
        storage_local_path=storage_local_path,
        aws_s3_bucket=aws_s3_bucket,
        aws_s3_prefix=os.getenv("AWS_S3_PREFIX", "omie-backup").strip("/"),
        aws_region=_optional_str(os.getenv("AWS_REGION")),
        sftp_host=_optional_str(os.getenv("SFTP_HOST")),
        sftp_port=_int_env("SFTP_PORT", 22),
        sftp_username=_optional_str(os.getenv("SFTP_USERNAME")),
        sftp_key_file=_optional_path(os.getenv("SFTP_KEY_FILE")),
        sftp_remote_path=os.getenv("SFTP_REMOTE_PATH", "/omie-backup"),
        api_delay_ms=_int_env("API_DELAY_MS", 300),
        api_max_retries=_int_env("API_MAX_RETRIES", 3),
        api_timeout_seconds=_int_env("API_TIMEOUT_SECONDS", 30),
        api_records_per_page=_int_env("API_RECORDS_PER_PAGE", 50),
        alert_enabled=_bool_env("ALERT_ENABLED", False),
        alert_on_success=_bool_env("ALERT_ON_SUCCESS", False),
        alert_max_duration_hours=_float_env("ALERT_MAX_DURATION_HOURS", 4.0),
        smtp_host=_optional_str(os.getenv("SMTP_HOST")),
        smtp_port=_int_env("SMTP_PORT", 587),
        smtp_tls=_bool_env("SMTP_TLS", True),
        smtp_username=_optional_str(os.getenv("SMTP_USERNAME")),
        smtp_password=_optional_str(os.getenv("SMTP_PASSWORD")),
        smtp_from=_optional_str(os.getenv("SMTP_FROM")),
        smtp_to=_list_env("SMTP_TO"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        output_dir=Path(os.getenv("OUTPUT_DIR", "backups")),
        omie_profiles=omie_profiles,
    )


def get_storage(settings: Settings):
    """Create the storage backend configured by STORAGE_TYPE."""

    from utils.storage import LocalStorage, S3Storage, SftpStorage

    if settings.storage_type == "local":
        if settings.storage_local_path is None:
            raise ValueError("STORAGE_LOCAL_PATH is required")
        return LocalStorage(settings.storage_local_path)
    if settings.storage_type == "s3":
        if settings.aws_s3_bucket is None:
            raise ValueError("AWS_S3_BUCKET is required")
        return S3Storage(settings.aws_s3_bucket, settings.aws_s3_prefix, settings.aws_region)
    if settings.storage_type == "sftp":
        return SftpStorage(
            host=_required(settings.sftp_host, "SFTP_HOST"),
            port=settings.sftp_port,
            username=_required(settings.sftp_username, "SFTP_USERNAME"),
            key_file=_required(settings.sftp_key_file, "SFTP_KEY_FILE"),
            remote_path=settings.sftp_remote_path,
        )
    raise ValueError(f"Unsupported STORAGE_TYPE: {settings.storage_type}")


def _backup_mode(value: str) -> BackupMode:
    if value not in {"full", "incremental"}:
        raise ValueError("BACKUP_MODE must be full or incremental")
    return value  # type: ignore[return-value]


def _omie_profiles() -> tuple[OmieProfile, ...]:
    profile_names = _list_env("OMIE_PROFILES")
    if not profile_names:
        missing = [name for name in ["OMIE_APP_KEY", "OMIE_APP_SECRET"] if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        profile_name = _optional_str(os.getenv("OMIE_PROFILE_NAME"))
        if profile_name:
            _validate_profile_name(profile_name)
        return (
            OmieProfile(
                name=profile_name,
                app_key=os.environ["OMIE_APP_KEY"],
                app_secret=os.environ["OMIE_APP_SECRET"],
            ),
        )

    profiles: list[OmieProfile] = []
    env_suffixes: set[str] = set()
    for name in profile_names:
        _validate_profile_name(name)
        env_suffix = name.upper().replace("-", "_")
        if env_suffix in env_suffixes:
            raise ValueError(f"Duplicate OMIE profile environment suffix: {env_suffix}")
        env_suffixes.add(env_suffix)

        app_key_name = f"OMIE_PROFILE_{env_suffix}_APP_KEY"
        app_secret_name = f"OMIE_PROFILE_{env_suffix}_APP_SECRET"
        missing = [
            env_name for env_name in [app_key_name, app_secret_name] if not os.getenv(env_name)
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        profiles.append(
            OmieProfile(
                name=name,
                app_key=os.environ[app_key_name],
                app_secret=os.environ[app_secret_name],
            )
        )

    return tuple(profiles)


def _validate_profile_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError(
            "OMIE profile names may contain only letters, numbers, underscores, and hyphens"
        )


def _optional_str(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _optional_path(value: str | None) -> Path | None:
    cleaned = _optional_str(value)
    return Path(cleaned) if cleaned else None


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "s", "sim"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _list_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _required(value, name: str):
    if value is None:
        raise ValueError(f"{name} is required")
    return value
