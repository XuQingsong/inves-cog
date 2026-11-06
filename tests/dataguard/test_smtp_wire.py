"""Offline SMTP integration: actual STARTTLS and MIME over a local Unix socket."""

import smtplib
import socket
import ssl
import subprocess
import tempfile
import threading
from email import message_from_bytes
from pathlib import Path

import pytest

from inves_cog.dataguard.mail import Mailer

pytestmark = pytest.mark.phase1_blocking


@pytest.fixture
def smtp_path():
    with tempfile.TemporaryDirectory(prefix="a032-smtp-", dir="/tmp") as folder:
        yield str(Path(folder) / "smtp.sock")


def test_local_smtp_starttls_delivers_merged_notice_and_conclusion(tmp_path, monkeypatch, smtp_path):
    certificate, key = tmp_path / "certificate.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certificate, key)
    client_context = ssl.create_default_context(cafile=str(certificate))
    monkeypatch.setattr("inves_cog.dataguard.mail.ssl.create_default_context", lambda: client_context)
    path = smtp_path
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(2)
    listener.settimeout(10)
    messages, trace, errors = [], [], []

    def serve():
        try:
            for _ in range(2):
                conn, _ = listener.accept()
                conn.settimeout(5)
                stream = conn.makefile("rb")

                channel = {"socket": conn}

                def reply(text, channel=channel):
                    channel["socket"].sendall(text.encode("ascii") + b"\r\n")

                reply("220 fixture.local SMTP")
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    command = line.decode("ascii").split()[0].upper()
                    trace.append(command)
                    if command == "EHLO":
                        conn.sendall(b"250-fixture.local\r\n250-STARTTLS\r\n250 AUTH PLAIN\r\n")
                    elif command == "STARTTLS":
                        reply("220 Ready for TLS")
                        stream.close()
                        conn = server_context.wrap_socket(conn, server_side=True)
                        channel["socket"] = conn
                        stream = conn.makefile("rb")
                    elif command == "AUTH":
                        reply("235 Authenticated")
                    elif command in {"MAIL", "RCPT"}:
                        reply("250 Accepted")
                    elif command == "DATA":
                        reply("354 Send message")
                        parts = []
                        while True:
                            part = stream.readline()
                            if part == b".\r\n":
                                break
                            if not part:
                                raise RuntimeError("truncated SMTP DATA")
                            parts.append(part)
                        messages.append(message_from_bytes(b"".join(parts)))
                        reply("250 Queued")
                    elif command == "QUIT":
                        reply("221 Bye")
                        break
                    else:
                        reply("500 Unsupported")
                stream.close()
                conn.close()
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    class LocalSMTP(smtplib.SMTP):
        def __init__(self, host, port, timeout):
            super().__init__("localhost", port, local_hostname="fixture.local", timeout=timeout)

        def _get_socket(self, host, port, timeout):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(path)
            return sock

    values = dict(
        INVES_SMTP_HOST="fixture.local",
        INVES_SMTP_PORT="587",
        INVES_SMTP_USER="fixture",
        INVES_SMTP_PASSWORD="fixture-only",
        INVES_SMTP_FROM="sender@example.test",
        INVES_ALERT_TO="owner@example.test",
    )
    mailer = Mailer(values, smtp=LocalSMTP)
    assert mailer.send("merged-fixture", "数据提醒：2项", "波动率、期权成交量缺失") == "sent"
    assert mailer.send("resolved-fixture", "补数结论", "波动率已补齐") == "sent"
    thread.join(10)
    assert not thread.is_alive() and not errors
    assert len(messages) == 2 and trace.count("STARTTLS") == 2
    assert trace.index("STARTTLS") < trace.index("AUTH")
    assert "波动率" in messages[0].get_payload(decode=True).decode("utf-8")
    assert "已补齐" in messages[1].get_payload(decode=True).decode("utf-8")
