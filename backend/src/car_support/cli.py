"""Command line: `car-support ingest [--full]`."""

import argparse
import json
import logging
from dataclasses import asdict

from car_support.config import get_settings
from car_support.db.session import get_session
from car_support.ingest.index import index_corpus
from car_support.observability import setup_logging

log = logging.getLogger("car_support.cli")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="car-support")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser(
        "ingest", help="index data/ into Postgres (only changed chunks are embedded)"
    )
    ingest.add_argument("--full", action="store_true", help="drop the index and re-embed everything")
    serve = commands.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    token = commands.add_parser("agent-token", help="print a signed agent token (development)")
    token.add_argument("email")
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)
    if args.command == "ingest":
        with get_session() as session:
            report = index_corpus(session, settings.data_dir, full=args.full)
        log.info("ingest finished", extra={"fields": asdict(report)})
        print(json.dumps(asdict(report), indent=2))

    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "car_support.api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=args.reload,
            # The client IP comes from X-Forwarded-For when the web app forwards a customer's request.
            proxy_headers=True,
            forwarded_allow_ips=settings.forwarded_allow_ips,
        )
    elif args.command == "agent-token":
        from car_support.api.auth import issue_token

        print(issue_token(args.email))


if __name__ == "__main__":
    main()
