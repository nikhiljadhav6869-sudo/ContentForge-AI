"""Validate resolved deployment boundaries with synthetic configuration only."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    # Isolate interpolation from operator secrets and any existing .env files.
    environment = os.environ.copy()
    for template in [ROOT / ".env.example", ROOT / "deploy/production.env.example"]:
        for line in template.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                environment.pop(line.split("=", 1)[0], None)
    for key in [
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_FILE",
        "COMPOSE_ENV_FILES",
        "POSTGRES_PORT",
        "REDIS_PORT",
    ]:
        environment.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="contentforge-config-check-") as directory:
        env_file = Path(directory) / "validation.env"
        env_file.write_text(
            "DOMAIN=studio.example.com\nPOSTGRES_PASSWORD=synthetic-validation-only\n"
            "OPENAI_API_KEY=synthetic-provider-key\n"
            "FRONTEND_ORIGIN=http://unsafe.example.com\nDEMO_AUTH=true\nREGISTRATION_ENABLED=true\nSECURE_COOKIES=false\n"
        )
        command = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            "compose.yaml",
        ]

        def render(arguments: list[str]) -> dict:
            result = subprocess.run(
                command + arguments + ["config", "--format", "json"],
                check=False,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            require(
                result.returncode == 0,
                "Compose could not resolve configuration; use Compose 2.24.4 or newer.",
            )
            return json.loads(result.stdout)

        local = render([])
        production = render(["-f", "compose.production.yaml"])
        require(local["name"] == "contentforge", "Local project name changed.")
        require(
            production["name"] == "contentforge-production",
            "Production must have a separate project name.",
        )
        for name in ["postgres", "redis", "api", "web"]:
            require(
                not production["services"][name].get("ports"),
                f"Production {name} publishes a host port.",
            )
            ports = local["services"][name]["ports"]
            require(
                all(port["host_ip"] == "127.0.0.1" for port in ports),
                f"Local {name} lost loopback bindings.",
            )
        for name in ["api", "worker"]:
            settings = production["services"][name]["environment"]
            require(
                settings["FRONTEND_ORIGIN"] == "https://studio.example.com",
                "HTTPS origin was not enforced.",
            )
            require(
                settings["DEMO_AUTH"] == "false",
                "Production guest access was not disabled.",
            )
            require(
                settings["REGISTRATION_ENABLED"] == "false",
                "Production public registration was not closed by default.",
            )
            require(
                settings["SECURE_COOKIES"] == "true",
                "Secure cookies were not enforced.",
            )
            require(
                settings["OPENAI_API_KEY"] == "synthetic-provider-key",
                "Provider settings were lost during merge.",
            )
            for key in ["DATABASE_URL", "CHECKPOINT_URL", "REDIS_URL"]:
                require(
                    settings[key] == local["services"][name]["environment"][key],
                    "Service connection was lost.",
                )
        proxy = production["services"]["proxy"]
        require(
            {"api", "web"}.issubset(set(proxy["environment"]["NO_PROXY"].split(","))),
            "Internal upstreams must bypass outbound HTTP proxies.",
        )
        require(
            {
                (port["published"], port["target"], port["protocol"])
                for port in proxy["ports"]
            }
            == {("80", 80, "tcp"), ("443", 443, "tcp"), ("443", 443, "udp")},
            "Proxy must publish only HTTP and HTTPS.",
        )
        mounts = {mount["target"]: mount for mount in proxy["volumes"]}
        require(
            mounts["/etc/caddy/Caddyfile"]["read_only"],
            "Proxy configuration must be read-only.",
        )
        for path in ["/data", "/config"]:
            require(mounts[path]["type"] == "volume", "Certificate state must persist.")
        for name in ["postgres-data", "redis-data", "backend-data"]:
            require(
                production["volumes"][name]["name"] != local["volumes"][name]["name"],
                "Local storage was reused.",
            )
        with env_file.open("a") as output:
            output.write("PUBLIC_REGISTRATION=true\n")
        opened = render(["-f", "compose.production.yaml"])
        require(
            all(
                opened["services"][name]["environment"]["REGISTRATION_ENABLED"]
                == "true"
                for name in ["api", "worker"]
            ),
            "Explicit production registration opt-in was ignored.",
        )
        print(
            "PASS: production ports, HTTPS/cookies, guest/sign-up restrictions, explicit sign-up opt-in, settings merge, and isolated persistent volumes."
        )
        print(
            "PASS: local project and loopback bindings preserved. No containers started or provider requests made."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        # Never print captured Compose output: an operator environment may contain secrets.
        print(
            str(exc)
            if isinstance(exc, RuntimeError)
            else "Deployment configuration validation could not complete."
        )
        raise SystemExit(1)
