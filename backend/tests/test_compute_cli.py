"""The compute entry point refuses bad arguments before it touches any database, and never prints the database URL."""
import pytest

from compute.run import main


def test_unknown_area_boat_class_and_missing_url_exit_with_2(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL_INGEST", raising=False)
    assert main(["--area", "../etc", "--date", "2026-11-26"]) == 2
    assert main(["--area", "th-chonburi-coast", "--date", "2026-11-26", "--boat-class", "huge"]) == 2
    assert main(["--area", "th-chonburi-coast", "--date", "2026-11-26"]) == 2
    err = capsys.readouterr().err
    assert "DATABASE_URL_INGEST is not set" in err and "huge" not in err        # the bad value is not echoed back


def test_a_bad_date_is_refused(monkeypatch):
    monkeypatch.setenv("DATABASE_URL_INGEST", "postgresql://u:secret-value@127.0.0.1:1/db")
    with pytest.raises(SystemExit):
        main(["--area", "th-chonburi-coast", "--date", "2026-13-45"])


def test_an_unreachable_database_does_not_leak_the_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL_INGEST", "postgresql://u:secret-value@127.0.0.1:1/db?connect_timeout=2")
    with pytest.raises(Exception) as e:
        main(["--area", "th-chonburi-coast", "--date", "2026-11-26"])
    out = capsys.readouterr()
    assert "secret-value" not in out.out + out.err + str(e.value)       # the password appears nowhere
