"""Start the FAQ chatbot server (API + chat UI).

Usage (from backend/):
    python run.py                       # production server (waitress)
    python run.py --dev                 # Flask development server
    python run.py --host 0.0.0.0 --port 8000

Host and port can also be set with FAQBOT_HOST and FAQBOT_PORT.
"""

import argparse
import logging
import os
import sys

from app import config
from app.factory import StartupError, create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--host", default=os.environ.get("FAQBOT_HOST", config.DEFAULT_HOST)
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FAQBOT_PORT", config.DEFAULT_PORT)),
    )
    parser.add_argument("--dev", action="store_true", help="use Flask's dev server")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        app = create_app(strict=True)
    except StartupError as error:
        print(f"Cannot start the FAQ chatbot: {error}", file=sys.stderr)
        return 1

    print(f"FAQ chatbot running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    if args.dev:
        app.run(host=args.host, port=args.port, debug=False)
    else:
        from waitress import serve

        serve(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
