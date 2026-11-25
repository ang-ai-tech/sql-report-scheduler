from datetime import date
from pathlib import Path

import pytest

from reportsched.config import load_reports
from reportsched.demo import create_demo_db, create_templates

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 18)  # a Wednesday


@pytest.fixture(scope="session")
def demo_url(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "demo_shop.db"
    create_demo_db(path, today=TODAY)
    return f"sqlite:///{path.as_posix()}"


@pytest.fixture(scope="session")
def templates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("templates")
    create_templates(directory)
    return directory


@pytest.fixture(scope="session")
def reports():
    return load_reports(ROOT / "config" / "reports", base_dir=ROOT)


@pytest.fixture
def connections(demo_url):
    return {"demo_shop": demo_url}


class FakeSMTP:
    """Records the messages instead of sending them. Can fail the first N times."""

    sent: list = []
    failures_left = 0

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        if FakeSMTP.failures_left:
            FakeSMTP.failures_left -= 1
            import smtplib

            raise smtplib.SMTPServerDisconnected("mail server not reachable")
        FakeSMTP.sent.append(message)


@pytest.fixture
def fake_smtp():
    FakeSMTP.sent = []
    FakeSMTP.failures_left = 0
    return FakeSMTP
