"""OMIE API client with retry, throttling, pagination, and safe logging."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response

from config import OMIE_BASE_URL, Settings

logger = logging.getLogger(__name__)


class OmieApiError(RuntimeError):
    """Raised when the OMIE API returns an unrecoverable error."""


@dataclass(frozen=True)
class PaginationStyle:
    """Pagination request/response field names for an endpoint."""

    page_field: str = "pagina"
    per_page_field: str = "registros_por_pagina"
    total_records_field: str = "total_de_registros"
    total_pages_field: str = "total_de_paginas"
    records_key: str | None = None


class OmieClient:
    """Client for OMIE JSON API calls."""

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        self._last_request_at = 0.0

    def call(self, endpoint: str, call_name: str, params: Mapping[str, Any]) -> dict[str, Any]:
        """Call an OMIE endpoint and return the decoded JSON response."""

        payload = {
            "call": call_name,
            "app_key": self._settings.omie_app_key,
            "app_secret": self._settings.omie_app_secret,
            "param": [dict(params)],
        }
        url = f"{OMIE_BASE_URL}/{endpoint.strip('/')}/"
        return self._request(url, payload)

    def paginate(
        self,
        endpoint: str,
        call_name: str,
        filters: Mapping[str, Any] | None = None,
        style: PaginationStyle | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield records from a paginated OMIE endpoint."""

        pagination = style or PaginationStyle()
        page = 1
        records_per_page = self._settings.api_records_per_page
        total_records: int | None = None
        total_pages: int | None = None

        while True:
            params = dict(filters or {})
            params[pagination.page_field] = page
            params[pagination.per_page_field] = records_per_page

            started = time.monotonic()
            response = self.call(endpoint, call_name, params)
            elapsed = time.monotonic() - started

            records = self._extract_records(response, pagination.records_key)
            total_records = _as_int(response.get(pagination.total_records_field), total_records)
            total_pages = _as_int(response.get(pagination.total_pages_field), total_pages)

            logger.info(
                "OMIE call endpoint=%s call=%s page=%s records=%s elapsed=%.2fs",
                endpoint,
                call_name,
                page,
                len(records),
                elapsed,
            )

            yield from records

            if total_pages is not None and page >= total_pages:
                break
            if total_records is not None and page * records_per_page >= total_records:
                break
            if total_pages is None and total_records is None and len(records) < records_per_page:
                break
            if not records:
                break

            page += 1

    def _request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        safe_payload = _mask_payload(payload)
        last_error: BaseException | None = None

        for attempt in range(1, self._settings.api_max_retries + 1):
            try:
                self._throttle()
                logger.debug("OMIE request url=%s payload=%s", url, safe_payload)
                response = self._session.post(
                    url,
                    json=payload,
                    timeout=self._settings.api_timeout_seconds,
                )
                return self._handle_response(response)
            except (requests.Timeout, requests.ConnectionError, _RetryableHttpError) as exc:
                last_error = exc
                if attempt >= self._settings.api_max_retries:
                    break
                sleep_seconds = min(2 ** (attempt - 1), 4)
                logger.warning(
                    "Retryable OMIE error on attempt %s/%s; retrying in %ss",
                    attempt,
                    self._settings.api_max_retries,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        raise OmieApiError(f"OMIE request failed after retries: {last_error}") from last_error

    @staticmethod
    def _handle_response(response: Response) -> dict[str, Any]:
        if response.status_code in {429, 500, 503}:
            raise _RetryableHttpError(response)
        if response.status_code >= 400:
            raise OmieApiError(f"OMIE HTTP {response.status_code}: {_safe_response_text(response)}")

        data = response.json()
        if isinstance(data, dict) and "faultstring" in data:
            raise OmieApiError(str(data["faultstring"]))
        if not isinstance(data, dict):
            raise OmieApiError("OMIE response is not a JSON object")
        return data

    def _throttle(self) -> None:
        delay_seconds = self._settings.api_delay_ms / 1000
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay_seconds:
            time.sleep(delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _extract_records(data: Mapping[str, Any], records_key: str | None) -> list[dict[str, Any]]:
        if records_key:
            records = data.get(records_key, [])
            return records if isinstance(records, list) else []

        ignored = {
            "pagina",
            "nPagina",
            "total_de_paginas",
            "nTotPaginas",
            "registros",
            "nRegistros",
            "total_de_registros",
            "nTotRegistros",
        }
        for key, value in data.items():
            if key not in ignored and isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []


class _RetryableHttpError(RuntimeError):
    def __init__(self, response: Response) -> None:
        self.response = response
        super().__init__(f"Retryable OMIE HTTP {response.status_code}")


def _mask_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    masked = dict(payload)
    if "app_key" in masked:
        masked["app_key"] = "****"
    if "app_secret" in masked:
        masked["app_secret"] = "****"
    return masked


def _safe_response_text(response: Response) -> str:
    text = response.text
    return text[:500] if text else ""


def _as_int(value: Any, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
