# Command line interface for EXOPTIMA

import argparse
import panel as pn
from pathlib import Path

from exoptima import __version__

def parse_args():
    parser = argparse.ArgumentParser(
        prog="exoptima",
        description="Exoplanet Observation and Planning Tool for Instrument and Mission Analysis"
    )

    parser.add_argument(
        "-m", "--mode",
        choices=["planning", "scheduling", "sched"],
        default="planning",
        help="Application mode (planning or scheduling; alias: sched)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5006,
        help="Port to run the web interface on (default: 5006)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--endpoint",
        type=str,
        default="exoptima",
        help="URL endpoint name (default: exoptima)"
    )

    return parser.parse_args()


def main():

    args = parse_args()

    favicon = Path(__file__).parent / "assets" / "exoptima-favicon.png"

    if args.mode in ["scheduling", "sched"]:
        display_mode = "scheduling"
    elif args.mode == "planning":
        display_mode = "planning"
    else:
        raise ValueError(f"Invalid mode: {args.mode}")

    print(f"\n🔭  Launching EXOPTIMA, v{__version__}")
    print(f"    Mode: {display_mode}\n")

    if args.mode == "planning":
        from exoptima.planning.app import app
    else:
        from exoptima.scheduling.app import app

    pn.serve(
        {args.endpoint: app},
        host=args.host,
        port=args.port,
        show=True,
        autoreload=False,
        title=f"EXOPTIMA - {args.mode.capitalize()}",
        ico_path=str(favicon),
    )