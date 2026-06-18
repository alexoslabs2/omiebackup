"""Storage backends for generated backup archives."""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    def upload(self, archive_path: Path, checksum_path: Path) -> list[str]:
        """Upload archive and checksum, returning destination identifiers."""


class LocalStorage(StorageBackend):
    """Store backup artifacts in a local directory."""

    def __init__(self, destination: Path) -> None:
        self.destination = destination

    def upload(self, archive_path: Path, checksum_path: Path) -> list[str]:
        """Copy archive and checksum into the configured local path."""

        self.destination.mkdir(parents=True, exist_ok=True)
        destinations = []
        for source in [archive_path, checksum_path]:
            target = self.destination / source.name
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
            destinations.append(str(target))
        logger.info("Stored backup artifacts locally at %s", self.destination)
        return destinations


class S3Storage(StorageBackend):
    """Store backup artifacts in Amazon S3."""

    def __init__(self, bucket: str, prefix: str, region: str | None) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region

    def upload(self, archive_path: Path, checksum_path: Path) -> list[str]:
        """Upload archive and checksum into S3."""

        import boto3

        client_kwargs = {"region_name": self.region} if self.region else {}
        s3 = boto3.client("s3", **client_kwargs)
        destinations = []
        for source in [archive_path, checksum_path]:
            key = f"{self.prefix}/{source.name}" if self.prefix else source.name
            s3.upload_file(str(source), self.bucket, key)
            destinations.append(f"s3://{self.bucket}/{key}")
        logger.info("Uploaded backup artifacts to s3://%s/%s", self.bucket, self.prefix)
        return destinations


class SftpStorage(StorageBackend):
    """Store backup artifacts through the system sftp client using key auth."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        key_file: Path,
        remote_path: str,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.key_file = key_file
        self.remote_path = remote_path.rstrip("/")

    def upload(self, archive_path: Path, checksum_path: Path) -> list[str]:
        """Upload archive and checksum with the system sftp command."""

        batch_file = archive_path.parent / "sftp-upload.batch"
        lines = [
            f"mkdir {self.remote_path}",
            f"put {archive_path} {self.remote_path}/{archive_path.name}",
            f"put {checksum_path} {self.remote_path}/{checksum_path.name}",
        ]
        batch_file.write_text("\n".join(lines), encoding="utf-8")
        try:
            subprocess.run(
                [
                    "sftp",
                    "-b",
                    str(batch_file),
                    "-i",
                    str(self.key_file),
                    "-P",
                    str(self.port),
                    f"{self.username}@{self.host}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            batch_file.unlink(missing_ok=True)

        return [
            f"sftp://{self.host}{self.remote_path}/{archive_path.name}",
            f"sftp://{self.host}{self.remote_path}/{checksum_path.name}",
        ]
