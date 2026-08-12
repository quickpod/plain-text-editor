"""Shared fixtures: an isolated config home in a tmp dir.

Setting ``PLAINTEXTEDITOR_HOME`` redirects the config dir (recent files,
theme, wrap/font settings) into the test's tmp dir, so nothing touches the
real user config and every test is hermetic.  Runs headless on Linux.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("PLAINTEXTEDITOR_HOME", str(h))
    return h
