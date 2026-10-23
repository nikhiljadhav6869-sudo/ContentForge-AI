"""The deployment bootstrap must never replace secrets or allow config injection."""

import importlib.util
import os
from pathlib import Path
import re
import stat

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("configure_production", ROOT / "scripts/configure_production.py")
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


@pytest.fixture
def config_root(tmp_path):
    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy/production.env.example").write_text(
        (ROOT / "deploy/production.env.example").read_text(), encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize("domain", ["studio.example.com", "content-forge.co.in", "xn--bcher-kva.de"])
def test_valid_domain(domain):
    assert configure.validate_domain(domain) == domain


@pytest.mark.parametrize(
    "domain",
    [
        "",
        "localhost",
        "app.local",
        "app.internal",
        "app.test",
        "app.invalid",
        "app.example",
        "app.onion",
        "127.0.0.1",
        "127.1",
        "0x7f000001",
        "[::1]",
        "https://studio.example.com",
        "studio.example.com:443",
        "studio.example.com/path",
        "studio.example.com.",
        "Studio.example.com",
        "*.example.com",
        "bad_name.com",
        "-app.example.com",
        "app-.example.com",
        "app..com",
        "a" * 64 + ".com",
        ".".join(["a" * 63] * 4),
        "example.com\nDEMO_AUTH=true",
        "example.com { respond hacked }",
        "${INJECT}.com",
        "bücher.de",
    ],
)
def test_invalid_domain_is_rejected_before_file_creation(config_root, domain):
    with pytest.raises(ValueError):
        configure.create_configuration(config_root, domain)
    assert not (config_root / ".env.production").exists()


def test_creates_private_configuration_without_touching_local_env(config_root):
    local = config_root / ".env"
    local.write_text("existing local settings\n")
    assert configure.create_configuration(config_root, "studio.example.com") is True
    target = config_root / ".env.production"
    content = target.read_text()
    assert "DOMAIN=studio.example.com\n" in content
    assert re.search(r"^POSTGRES_PASSWORD=[A-Za-z0-9_-]{43}$", content, re.MULTILINE)
    assert "OPENAI_API_KEY=\n" in content
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert local.read_text() == "existing local settings\n"


def test_existing_configuration_and_permissions_are_preserved(config_root):
    target = config_root / ".env.production"
    target.write_text("existing secret settings\n")
    os.chmod(target, 0o640)
    assert configure.create_configuration(config_root, "studio.example.com") is False
    assert target.read_text() == "existing secret settings\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_symlink_target_is_not_overwritten(config_root):
    original = config_root / "private-settings"
    original.write_text("private\n")
    (config_root / ".env.production").symlink_to(original)
    assert configure.create_configuration(config_root, "studio.example.com") is False
    assert original.read_text() == "private\n"


def test_new_installations_get_independent_passwords(config_root, tmp_path):
    assert configure.create_configuration(config_root, "studio.example.com")
    first = (config_root / ".env.production").read_text()
    (config_root / ".env.production").unlink()
    assert configure.create_configuration(config_root, "studio.example.com")
    assert first != (config_root / ".env.production").read_text()
