#!/usr/bin/env python3
"""Prospective-only entry point. Default is read-only inspection, not dispatch."""

import argparse
import json
from pathlib import Path

from code_engine.acquisition import prospective_workflow as workflow


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--authorize-live-network", action="store_true",
                        help="Separate explicit authorization; never implied by offline acceptance")
    args = parser.parse_args(argv)
    if not args.execute:
        if not args.resume:
            parser.error("NO_LIVE_NETWORK_DEFAULT: use a frozen existing directory for --resume inspection")
        result = workflow.inspect(args.directory)
    else:
        if not args.authorize_live_network:
            parser.error("LIVE_NETWORK_NOT_AUTHORIZED")
        if args.resume:
            result = workflow.resume(args.directory, authorize_live_network=True)
        else:
            if args.manifest is None:
                parser.error("FROZEN_MANIFEST_REQUIRED")
            manifest = workflow.j.FrozenRequestManifestV2(workflow.j.read_bytes(args.manifest))
            result = workflow.run(args.directory, manifest, authorize_live_network=True)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
