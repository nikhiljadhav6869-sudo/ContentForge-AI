"""Read-only deployment checks; never print configuration values or exception details."""

import argparse
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

LIMITS = [
    "Provider credential validity and live generation are not tested.",
    "Public HTTPS, proxy streaming, backups, and deployment capacity are not tested.",
    "A worker heartbeat does not prove that a workflow can finish; run an end-to-end smoke test.",
]


def check(name, passed, success, failure):
    return {"id": name, "status": "pass" if passed else "fail", "message": success if passed else failure}


def web_url(value, public_origin=False):
    try:
        parsed = urlsplit(value)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return False
        if parsed.port == 0:
            return False
        if any(char.isspace() for char in value):
            return False
        if not public_origin:
            return parsed.scheme in {"http", "https"}
        host = parsed.hostname.lower()
        if parsed.scheme != "https" or parsed.path:
            return False
        try:
            address = ipaddress.ip_address(host)
            valid = address.is_global
            host = f"[{address.compressed}]" if address.version == 6 else address.compressed
        except ValueError:
            # Browsers normalize legacy numeric IPv4 spellings such as 127.1.
            # Do not mistake those for public DNS names when canonical parsing fails.
            if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host):
                return False
            host = host.encode("idna").decode("ascii")
            valid = (
                "." in host
                and len(host) <= 253
                and not host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
                and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split("."))
            )
        port = f":{parsed.port}" if parsed.port not in (None, 443) else ""
        # FRONTEND_ORIGIN is compared verbatim with the browser's Origin header.
        return valid and value == f"https://{host}{port}"
    except (ValueError, TypeError):
        return False


def configuration(settings, provider):
    from sqlalchemy.engine import make_url

    try:
        database = make_url(settings.database_url)
        database_ok = database.drivername == "postgresql+psycopg" and bool(database.host and database.database)
    except Exception:
        database_ok = False
    try:
        checkpoint = urlsplit(settings.checkpoint_url)
        checkpoint_ok = checkpoint.scheme in {"postgres", "postgresql"} and bool(
            checkpoint.hostname and checkpoint.path.strip("/")
        )
        _ = checkpoint.port
    except ValueError:
        checkpoint_ok = False
    try:
        queue = urlsplit(settings.redis_url)
        queue_ok = queue.scheme in {"redis", "rediss"} and bool(queue.hostname)
        _ = queue.port
    except ValueError:
        queue_ok = False
    if provider == "openai":
        provider_ok = bool(settings.openai_api_key.strip() and settings.openai_model.strip()) and web_url(
            settings.openai_base_url
        )
        provider_help = "Set OPENAI_API_KEY, OPENAI_MODEL, and a valid OPENAI_BASE_URL in server configuration."
    elif provider == "gemini":
        provider_ok = bool(settings.gemini_api_key.strip() and settings.gemini_model.strip())
        provider_help = "Set GEMINI_API_KEY and GEMINI_MODEL in server configuration."
    else:
        provider_ok = bool(settings.ollama_model.strip()) and web_url(settings.ollama_base_url)
        provider_help = "Set OLLAMA_MODEL and a valid OLLAMA_BASE_URL reachable by API and workers."
    return [
        check(
            "frontend_origin",
            web_url(settings.frontend_origin, True),
            "HTTPS frontend origin syntax is valid; reachability is not checked.",
            "Set FRONTEND_ORIGIN to the exact public HTTPS origin without a path or trailing slash.",
        ),
        check(
            "secure_cookies",
            settings.secure_cookies,
            "Secure cookies are enabled.",
            "Set SECURE_COOKIES=true for the public HTTPS deployment.",
        ),
        check(
            "guest_access",
            not settings.demo_auth,
            "Guest demo sign-in is disabled.",
            "Set DEMO_AUTH=false before the public deployment.",
        ),
        check(
            "database_config",
            database_ok,
            "PostgreSQL application connection is configured.",
            "Set DATABASE_URL to a postgresql+psycopg connection URI.",
        ),
        check(
            "checkpoint_config",
            checkpoint_ok,
            "PostgreSQL checkpoint connection is configured.",
            "Set CHECKPOINT_URL to a PostgreSQL connection URI with a database name.",
        ),
        check(
            "queue_config",
            queue_ok,
            "Redis queue connection is configured.",
            "Set REDIS_URL to a Redis connection URI.",
        ),
        check(
            "provider_config",
            provider_ok,
            "Selected provider configuration fields are present; access and generation are unverified.",
            provider_help,
        ),
    ]


def database_checks(settings):
    from sqlalchemy import create_engine, text
    from alembic.script import ScriptDirectory

    engine = None
    try:
        engine = create_engine(
            settings.database_url,
            connect_args={
                "connect_timeout": 3,
                "options": "-c statement_timeout=3000 -c default_transaction_read_only=on",
            },
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            reachable = check("database", True, "Application database responded to a read-only query.", "")
            try:
                actual = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
                expected = set(ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads())
                migrated = actual == expected and bool(expected)
            except Exception:
                migrated = False
        return [
            reachable,
            check(
                "migrations",
                migrated,
                "Application migration revision matches this checkout.",
                "Apply this release's Alembic migrations before starting the deployment.",
            ),
        ]
    except Exception:
        return [
            check(
                "database",
                False,
                "",
                "Cannot read the application database. Check server credentials, network access, and TLS configuration.",
            )
        ]
    finally:
        if engine is not None:
            engine.dispose()


def checkpoint_checks(settings):
    import psycopg

    try:
        with psycopg.connect(
            settings.checkpoint_url,
            connect_timeout=3,
            options="-c statement_timeout=3000 -c default_transaction_read_only=on",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('checkpoints'), to_regclass('checkpoint_blobs'), to_regclass('checkpoint_writes')"
                )
                present = all(cursor.fetchone())
        return [
            check(
                "checkpoints",
                present,
                "Checkpoint storage is reachable and its three data tables exist.",
                "Initialize checkpoint storage with python -m app.init_checkpoints before launch.",
            )
        ]
    except Exception:
        return [
            check(
                "checkpoints",
                False,
                "",
                "Cannot inspect checkpoint storage. Check CHECKPOINT_URL, credentials, network access, and TLS configuration.",
            )
        ]


def active_worker(data, ttl, current):
    try:
        heartbeat = datetime.fromisoformat(data.get("last_heartbeat", "").replace("Z", "+00:00"))
        age = (current - heartbeat).total_seconds()
        return (
            ttl > 0
            and 0 <= age <= 450
            and data.get("state") in {"idle", "busy"}
            and "contentforge" in data.get("queues", "").split(",")
        )
    except (ValueError, TypeError):
        return False


def queue_checks(settings):
    from redis import Redis

    connection = None
    try:
        connection = Redis.from_url(
            settings.redis_url, socket_timeout=3, socket_connect_timeout=3, decode_responses=True
        )
        connection.ping()
        reachable = check("redis", True, "Redis responded to a ping.", "")
        try:
            found = any(
                active_worker(connection.hgetall(key), connection.ttl(key), datetime.now(timezone.utc))
                for key in connection.smembers("rq:workers:contentforge")
                if key.startswith("rq:worker:")
            )
            workers = check(
                "worker",
                found,
                "An idle or busy contentforge worker has a heartbeat within 450 seconds and an unexpired registration.",
                "No active contentforge worker found. Start the RQ worker and check its queue and heartbeat.",
            )
        except Exception:
            workers = check(
                "worker",
                False,
                "",
                "Cannot inspect worker registrations. Check Redis read permissions and worker configuration.",
            )
        return [reachable, workers]
    except Exception:
        return [
            check(
                "redis",
                False,
                "",
                "Cannot reach Redis. Check REDIS_URL, credentials, network access, and TLS configuration.",
            )
        ]
    finally:
        if connection is not None:
            connection.close()


def report(settings, provider, offline=False):
    checks = configuration(settings, provider)
    valid = {item["id"]: item["status"] == "pass" for item in checks}
    for required, name, probe in [
        ("database_config", "database", database_checks),
        ("checkpoint_config", "checkpoints", checkpoint_checks),
        ("queue_config", "redis", queue_checks),
    ]:
        if offline or not valid[required]:
            checks.append(
                {
                    "id": name,
                    "status": "skipped",
                    "message": "Service check skipped: offline mode or missing connection configuration.",
                }
            )
        else:
            try:
                checks.extend(probe(settings))
            except Exception:
                checks.append(
                    check(
                        name,
                        False,
                        "",
                        "Service check failed. Inspect server configuration and installed dependencies.",
                    )
                )
    return {
        "scope": "configuration_only" if offline else "configuration_and_services",
        "provider": provider,
        "passed": not any(item["status"] == "fail" for item in checks),
        "checks": checks,
        "not_verified": LIMITS,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check public-deployment configuration and services without changing data or calling AI providers."
    )
    parser.add_argument("--provider", required=True, choices=["openai", "gemini", "ollama"])
    parser.add_argument("--offline", action="store_true", help="Check configuration only; do not contact services.")
    parser.add_argument(
        "--json", action="store_true", help="Print a machine-readable report with no configuration values."
    )
    args = parser.parse_args(argv)
    try:
        from .config import settings

        result = report(settings, args.provider, args.offline)
    except Exception:
        result = {
            "scope": "configuration_only",
            "provider": args.provider,
            "passed": False,
            "checks": [
                check(
                    "configuration",
                    False,
                    "",
                    "Cannot load server configuration. Check environment variable formats and dependency installation.",
                )
            ],
            "not_verified": LIMITS,
        }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("ContentForge deployment preflight (" + result["scope"] + ")")
        for item in result["checks"]:
            print(f"[{item['status'].upper()}] {item['id']}: {item['message']}")
        print("Checks passed." if result["passed"] else "Resolve the failed checks before launch.")
        for limitation in result["not_verified"]:
            print("Not verified: " + limitation)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
