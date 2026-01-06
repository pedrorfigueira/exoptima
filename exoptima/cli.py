import argparse
import panel as pn

from exoptima.app import app

def parse_args():
    parser = argparse.ArgumentParser(
        prog="opt",
        description="Astronomical Observation Planning Tool"
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
        default="opt",
        help="URL endpoint name (default: opt)"
    )

    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open a web browser automatically"
    )

    return parser.parse_args()


def main():

    args = parse_args()

    print("\n🔭  Launching EXOPTIMA! \n")

    pn.serve(
        {args.endpoint: app},
        host=args.host,
        port=args.port,
        show=not args.no_show,
        autoreload=False,
        title="EXOPTIMA",
    )
