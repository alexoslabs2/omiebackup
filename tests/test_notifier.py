"""Tests for SMTP notification delivery modes."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from utils.notifier import EmailNotifier


def test_notifier_sends_plain_smtp_without_tls_or_auth(monkeypatch) -> None:
    """SMTP_SECURITY=none uses plain SMTP and skips auth when credentials are empty."""

    class FakeSMTP:
        instances = []

        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port
            self.started_tls = False
            self.logged_in = False
            self.sent = False
            self.__class__.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            self.started_tls = True

        def login(self, username: str, password: str) -> None:
            self.logged_in = True

        def sendmail(self, sender: str, recipients: list[str], message: str) -> None:
            self.sent = True

    class FakeSMTPSSL:
        def __init__(self, host: str, port: int) -> None:
            raise AssertionError("SMTP_SSL should not be used for plain SMTP")

    monkeypatch.setattr("utils.notifier.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("utils.notifier.smtplib.SMTP_SSL", FakeSMTPSSL)

    settings = SimpleNamespace(
        alert_enabled=True,
        alert_on_success=True,
        alert_max_duration_hours=4,
        smtp_host="smtp.internal",
        smtp_port=25,
        smtp_security="none",
        smtp_username=None,
        smtp_password=None,
        smtp_from="backup@example.com",
        smtp_to=["ops@example.com"],
    )

    sent = EmailNotifier(settings).send_summary([], timedelta(seconds=1), ["local"])

    assert sent is True
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.internal"
    assert smtp.port == 25
    assert smtp.started_tls is False
    assert smtp.logged_in is False
    assert smtp.sent is True
