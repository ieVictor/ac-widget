import json
import stat

import pytest

from midea_desktop.journal import Journal, public


def test_redaction_is_recursive():
    source = {
        "ip": "192.168.1.50",
        "token": "SECRET",
        "sn": "SERIAL",
        "nested": [{"accessToken": "SECRET2", "key": "SECRET3", "power": True}],
    }
    assert public(source) == {"ip": "192.168.1.50", "nested": [{"power": True}]}
    assert public(source, anonymize=True) == {"nested": [{"power": True}]}


def test_journal_private_and_anonymous(tmp_path):
    path = tmp_path / "calls.jsonl"
    journal = Journal(path)
    journal.record("test", state={"id": 123, "name": "quarto", "token": "SECRET", "power": False})
    event = json.loads(path.read_text())
    assert event["state"] == {"power": False}
    assert event["operation"] == "test"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    journal.record("second")
    assert len(path.read_text().splitlines()) == 2


def test_does_not_follow_symlink(tmp_path):
    target = tmp_path / "other"
    target.write_text("original")
    link = tmp_path / "calls.jsonl"
    link.symlink_to(target)
    with pytest.raises(OSError):
        Journal(link).record("test")
    assert target.read_text() == "original"
