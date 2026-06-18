"""Command-line entrypoint for OMIE backups."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import tarfile
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from config import BackupMode, ModuleResult, OmieProfile, Settings, get_storage, load_settings
from modules import EXPORT_MODULES
from utils.notifier import EmailNotifier
from utils.omie_client import OmieClient


def main(argv: list[str] | None = None) -> int:
    """Run an OMIE backup."""

    args = _parse_args(argv)
    settings = load_settings()
    settings = replace(settings, backup_mode=args.mode)
    _setup_logging(settings.log_level)

    started = datetime.now()
    results: list[ModuleResult] = []
    destinations: list[str] = []
    critical_errors: list[str] = []

    date_filter = _date_filter(settings.backup_mode, started.date())
    for profile in settings.omie_profiles:
        profile_results, profile_destinations, critical_error = _run_profile(
            settings,
            profile,
            started,
            date_filter,
        )
        results.extend(profile_results)
        destinations.extend(profile_destinations)
        if critical_error:
            critical_errors.append(critical_error)

    duration = datetime.now() - started
    critical_error = "\n".join(critical_errors) if critical_errors else None
    try:
        EmailNotifier(settings).send_summary(results, duration, destinations, critical_error)
    except (OSError, ValueError, RuntimeError) as exc:
        logging.exception("Failed to send summary e-mail: %s", exc)

    if critical_errors or any(result.status == "error" for result in results):
        return 1
    logging.info("OMIE backup completed successfully in %s", datetime.now() - started)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OMIE backup")
    parser.add_argument("--mode", choices=["full", "incremental"], required=True)
    return parser.parse_args(argv)


def _setup_logging(level_name: str) -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"backup-{date.today().isoformat()}.log"

    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def _date_filter(mode: BackupMode, today: date) -> str | None:
    if mode == "full":
        return None
    return (today - timedelta(days=1)).strftime("%d/%m/%Y")


def _run_profile(
    settings: Settings,
    profile: OmieProfile,
    started: datetime,
    date_filter: str | None,
) -> tuple[list[ModuleResult], list[str], str | None]:
    profile_label = profile.name or "default"
    output_dir = _profile_output_dir(settings, profile, started)
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(
        "Starting OMIE backup profile=%s mode=%s output_dir=%s",
        profile_label,
        settings.backup_mode,
        output_dir,
    )

    profile_settings = replace(
        settings,
        omie_app_key=profile.app_key,
        omie_app_secret=profile.app_secret,
    )
    client = OmieClient(profile_settings)
    results: list[ModuleResult] = []
    destinations: list[str] = []

    try:
        for module in EXPORT_MODULES:
            result = module.export(client, output_dir, date_filter)
            results.append(_with_profile_name(result, profile.name))

        archive_path = _create_archive(output_dir, profile.name)
        checksum_path = _write_checksum(archive_path)
        storage = get_storage(settings)
        destinations = storage.upload(archive_path, checksum_path)
    except (OSError, ValueError, RuntimeError) as exc:
        message = f"{profile_label}: {exc}"
        logging.exception("Critical backup failure profile=%s", profile_label)
        return results, destinations, message

    logging.info("Completed OMIE backup profile=%s", profile_label)
    return results, destinations, None


def _profile_output_dir(settings: Settings, profile: OmieProfile, started: datetime) -> Path:
    date_dir = started.strftime("%Y-%m-%d")
    if profile.name:
        return settings.output_dir / profile.name / date_dir
    return settings.output_dir / date_dir


def _with_profile_name(result: ModuleResult, profile_name: str | None) -> ModuleResult:
    if not profile_name:
        return result
    return replace(result, module=f"{profile_name}/{result.module}")


def _create_archive(output_dir: Path, profile_name: str | None = None) -> Path:
    if profile_name:
        archive_path = output_dir.parent.parent / f"{profile_name}_{output_dir.name}.tar.gz"
        archive_root = output_dir.parent.parent
    else:
        archive_path = output_dir.with_suffix(".tar.gz")
        archive_root = output_dir.parent

    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(output_dir.rglob("*.csv")):
            archive.add(path, arcname=path.relative_to(archive_root))
    logging.info("Created archive %s", archive_path)
    return archive_path


def _write_checksum(archive_path: Path) -> Path:
    checksum = hashlib.sha256()
    with archive_path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            checksum.update(chunk)

    checksum_path = archive_path.with_suffix(f"{archive_path.suffix}.sha256")
    checksum_path.write_text(f"{checksum.hexdigest()}  {archive_path.name}\n", encoding="utf-8")
    logging.info("Created checksum %s", checksum_path)
    return checksum_path


if __name__ == "__main__":
    raise SystemExit(main())
