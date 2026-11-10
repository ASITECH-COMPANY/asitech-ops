"""Command line: asitech-agent {enroll,run,status,facts}."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys

from . import __version__, identity, system
from .client import Agent, EnrollmentError, enroll
from .config import AgentConfig, config_path, key_path, state_dir, validate_url


def _enroll(args: argparse.Namespace) -> int:
    url = validate_url(args.url)
    token = args.token or os.environ.get("ASITECH_ENROLL_TOKEN", "")
    if not token:
        print("An enrollment token is required (--token or ASITECH_ENROLL_TOKEN).", file=sys.stderr)
        return 2
    if config_path().exists() and not args.force:
        print(
            f"Already enrolled ({config_path()}). Use --force to enroll again with a new key.",
            file=sys.stderr,
        )
        return 1
    state_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
    key = identity.generate()
    try:
        result = enroll(url, token, key, system.collect_facts(), ca_file=args.ca_file)
    except EnrollmentError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    # The key is written only after the Control Plane accepted it.
    identity.save(key, key_path())
    AgentConfig(
        control_plane_url=url,
        server_id=str(result["server_id"]),
        server_name=result.get("server_name", ""),
        organization=result.get("organization", ""),
        websocket_path=result.get("websocket_path", "/ws/agent/v1/connect/"),
        ca_file=args.ca_file,
        control_plane_public_key=result.get("control_plane_public_key", ""),
    ).save()
    print(f"Enrolled as '{result.get('server_name')}' in '{result.get('organization')}'.")
    print(f"Key fingerprint: {identity.fingerprint(key)}")
    return 0


def _run(_: argparse.Namespace) -> int:
    try:
        config = AgentConfig.load()
        key = identity.load(key_path())
    except FileNotFoundError:
        logging.error("Not enrolled yet: run 'asitech-agent enroll --url ... --token ...' first.")
        return 1

    async def main() -> None:
        agent = Agent(config, key)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, agent.stopping.set)
        await agent.run_forever()

    asyncio.run(main())
    return 0


def _status(_: argparse.Namespace) -> int:
    try:
        config = AgentConfig.load()
        key = identity.load(key_path())
    except FileNotFoundError:
        print("Not enrolled.")
        return 1
    print(f"Control Plane : {config.control_plane_url}")
    print(f"Server        : {config.server_name} ({config.server_id})")
    print(f"Organization  : {config.organization}")
    print(f"Key           : {identity.fingerprint(key)}")
    print(f"Task key      : {'pinned' if config.control_plane_public_key else 'not pinned yet'}")
    return 0


def _facts(_: argparse.Namespace) -> int:
    collector = system.MetricsCollector()
    print(json.dumps({"facts": system.collect_facts(), "metrics": collector.collect()}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asitech-agent", description="ASITECH OPS agent")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    enroll_cmd = commands.add_parser("enroll", help="Register this server with a one-time token")
    enroll_cmd.add_argument("--url", required=True, help="Control Plane URL, e.g. https://ops.example.com")
    enroll_cmd.add_argument("--token", help="Enrollment token (or set ASITECH_ENROLL_TOKEN)")
    enroll_cmd.add_argument("--ca-file", help="Extra CA bundle for a Control Plane with a private CA")
    enroll_cmd.add_argument("--force", action="store_true", help="Replace an existing enrollment (new key)")
    enroll_cmd.set_defaults(func=_enroll)
    commands.add_parser("run", help="Connect and report (used by systemd)").set_defaults(func=_run)
    commands.add_parser("status", help="Show enrollment details").set_defaults(func=_status)
    commands.add_parser("facts", help="Print collected facts and metrics").set_defaults(func=_facts)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        return args.func(args)
    except (ValueError, PermissionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
