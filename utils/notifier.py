"""SMTP summary notifier."""

from __future__ import annotations

import logging
import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import ModuleResult, Settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send execution summaries through SMTP."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_summary(
        self,
        results: list[ModuleResult],
        duration: timedelta,
        destinations: list[str],
        critical_error: str | None = None,
    ) -> bool:
        """Send a summary e-mail when alert rules require it."""

        if not self._should_send(results, duration, critical_error):
            return False
        self._validate_settings()

        message = MIMEMultipart("alternative")
        message["Subject"] = self._subject(results, critical_error)
        message["From"] = self.settings.smtp_from or ""
        message["To"] = ", ".join(self.settings.smtp_to)

        text_body = _text_body(results, duration, destinations, critical_error)
        html_body = _html_body(results, duration, destinations, critical_error)
        message.attach(MIMEText(text_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))

        if self.settings.smtp_security == "starttls":
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
                smtp.starttls()
                self._login(smtp)
                smtp.sendmail(self.settings.smtp_from, self.settings.smtp_to, message.as_string())
        elif self.settings.smtp_security == "ssl":
            with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port) as smtp:
                self._login(smtp)
                smtp.sendmail(self.settings.smtp_from, self.settings.smtp_to, message.as_string())
        else:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
                self._login(smtp)
                smtp.sendmail(self.settings.smtp_from, self.settings.smtp_to, message.as_string())

        logger.info("Sent backup summary e-mail to %s", ", ".join(self.settings.smtp_to))
        return True

    def _should_send(
        self,
        results: list[ModuleResult],
        duration: timedelta,
        critical_error: str | None,
    ) -> bool:
        if not self.settings.alert_enabled:
            return False
        if critical_error:
            return True
        if any(result.status in {"warning", "error"} for result in results):
            return True
        max_duration = timedelta(hours=self.settings.alert_max_duration_hours)
        if duration > max_duration:
            return True
        return self.settings.alert_on_success

    def _validate_settings(self) -> None:
        required = {
            "SMTP_HOST": self.settings.smtp_host,
            "SMTP_FROM": self.settings.smtp_from,
            "SMTP_TO": self.settings.smtp_to,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing SMTP settings: {', '.join(missing)}")

    def _login(self, smtp: smtplib.SMTP | smtplib.SMTP_SSL) -> None:
        if self.settings.smtp_username and self.settings.smtp_password:
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)

    @staticmethod
    def _subject(results: list[ModuleResult], critical_error: str | None) -> str:
        if critical_error or any(result.status == "error" for result in results):
            return "OMIE backup falhou"
        if any(result.status == "warning" for result in results):
            return "OMIE backup concluido com avisos"
        return "OMIE backup concluido"


def _text_body(
    results: list[ModuleResult],
    duration: timedelta,
    destinations: list[str],
    critical_error: str | None,
) -> str:
    lines = [f"Duracao: {duration}", ""]
    if critical_error:
        lines.extend(["Erro critico:", critical_error, ""])
    for result in results:
        lines.append(f"{result.module}: {result.status} ({result.records} registros)")
        for error in result.errors:
            lines.append(f"- {error}")
    lines.extend(["", "Destinos:"])
    lines.extend(destinations or ["Nenhum destino registrado."])
    return "\n".join(lines)


def _html_body(
    results: list[ModuleResult],
    duration: timedelta,
    destinations: list[str],
    critical_error: str | None,
) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{result.module}</td>"
        f"<td>{result.status}</td>"
        f"<td>{result.records}</td>"
        f"<td>{'<br>'.join(result.errors)}</td>"
        "</tr>"
        for result in results
    )
    destination_items = "".join(f"<li>{destination}</li>" for destination in destinations)
    critical = f"<p><strong>Erro critico:</strong> {critical_error}</p>" if critical_error else ""
    return f"""
    <html>
      <body>
        <p>Duracao: {duration}</p>
        {critical}
        <table border="1" cellspacing="0" cellpadding="4">
          <thead>
            <tr><th>Modulo</th><th>Status</th><th>Registros</th><th>Erros</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p>Destinos:</p>
        <ul>{destination_items}</ul>
      </body>
    </html>
    """
