import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.parametrize("extra_table, expected", [("checkpoints", 0), ("unexpected_app_table", 255)])
def test_migrations_respect_checkpoint_ownership_without_hiding_other_drift(tmp_path, extra_table, expected):
    root = Path(__file__).resolve().parents[1]
    url = "sqlite:///" + str(tmp_path / "migration.db")
    env = dict(os.environ, DATABASE_URL=url)
    command = [sys.executable, "-m", "alembic"]
    upgraded = subprocess.run(command + ["upgrade", "0002"], cwd=root, env=env, capture_output=True, check=False)
    assert upgraded.returncode == 0
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id,email,password_hash,name,created_at) VALUES ('legacy','legacy@example.com','unchanged','Legacy','2026-01-01')"
            )
        )
    upgraded = subprocess.run(command + ["upgrade", "head"], cwd=root, env=env, capture_output=True, check=False)
    assert upgraded.returncode == 0
    with engine.begin() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert db.execute(text("SELECT password_hash,email_verified_at FROM users WHERE id='legacy'")).one() == (
            "unchanged",
            None,
        )
        assert db.scalar(text("SELECT count(*) FROM password_resets")) == 0
        db.execute(text(f'CREATE TABLE "{extra_table}" (id INTEGER PRIMARY KEY)'))
    engine.dispose()
    checked = subprocess.run(command + ["check"], cwd=root, env=env, capture_output=True, check=False)
    assert checked.returncode == expected, checked.stdout.decode()
