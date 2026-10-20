#!/usr/bin/env python3
"""ACDV-Teams Coder — Entry point (Boot step 1)."""
import os
import sys
import json
import signal
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.engine import CoreEngine


def main():
    parser = argparse.ArgumentParser(description="ACDV-Teams Coder")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    config_path = os.path.join(BASE_DIR, "config.json")
    if not os.path.isfile(config_path):
        print(f"[FATAL] Missing config.json at {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.host:
        config["host"] = args.host
    if args.port:
        config["port"] = args.port

    print(f"[Boot] base_dir = {BASE_DIR}", flush=True)
    print(f"[Boot] importing CoreEngine …", flush=True)

    engine = CoreEngine(BASE_DIR, config)

    def _shutdown(signum, frame):
        engine.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    engine.boot()
    engine.run_forever()


if __name__ == "__main__":
    main()