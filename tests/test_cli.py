"""CLI behaviour: cat / count / detect / recent, clean error paths."""

from plaintexteditor import __main__ as cli
from plaintexteditor import guiconfig


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "cat" in out and "detect" in out


def test_cat_prints_decoded_text(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes("\ufeffcafé\r\nline 2\r\n".encode("utf-16-le"))
    assert cli.main(["cat", str(p)]) == 0
    assert capsys.readouterr().out == "café\nline 2\n"


def test_cat_adds_final_newline_when_missing(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes(b"no newline")
    assert cli.main(["cat", str(p)]) == 0
    assert capsys.readouterr().out == "no newline\n"


def test_cat_numbered(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes(b"a\nb\n")
    assert cli.main(["cat", "-n", str(p)]) == 0
    out = capsys.readouterr().out
    assert "1\ta" in out and "2\tb" in out


def test_count(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes(b"one two\nthree\n")
    assert cli.main(["count", str(p)]) == 0
    out = capsys.readouterr().out
    assert "lines=2" in out and "words=3" in out and "chars=14" in out


def test_count_multiple_files(tmp_path, capsys):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"x\n")
    b.write_bytes(b"y z\n")
    assert cli.main(["count", str(a), str(b)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2


def test_detect_reports_encoding_and_eol(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes(b"\xef\xbb\xbfhello\r\n")
    assert cli.main(["detect", str(p)]) == 0
    out = capsys.readouterr().out
    assert "UTF-8 BOM" in out and "CRLF" in out


def test_detect_ansi(tmp_path, capsys):
    p = tmp_path / "f.txt"
    p.write_bytes(b"\x93hi\x94\n")
    assert cli.main(["detect", str(p)]) == 0
    out = capsys.readouterr().out
    assert "ANSI" in out and "LF" in out


def test_missing_file_is_clean_error(capsys):
    assert cli.main(["cat", "/no/such/file.txt"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err


def test_recent_empty_then_lists(home, tmp_path, capsys):
    assert cli.main(["recent"]) == 0
    assert "(no recent files)" in capsys.readouterr().out
    guiconfig.add_recent(str(tmp_path / "seen.txt"))
    assert cli.main(["recent"]) == 0
    assert "seen.txt" in capsys.readouterr().out


def test_recent_clear(home, tmp_path, capsys):
    guiconfig.add_recent(str(tmp_path / "seen.txt"))
    assert cli.main(["recent", "--clear"]) == 0
    assert guiconfig.get_recent() == []
