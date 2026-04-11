#!/usr/bin/env python3
"""
Copilot CLI shim for the harness.

Accepts Claude Code CLI flags, translates to Copilot CLI, passes output through.
Usage: set settings.json "command" to the path of this script.
"""

import argparse
import os
import subprocess
import sys

COPILOT_BIN = "/opt/homebrew/bin/copilot"

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-p", "--prompt", dest="prompt", default=None)

    # Claude Code flags we accept and discard
    parser.add_argument("--output-format", dest="output_format", default=None)
    parser.add_argument("--verbose", action="store_true", default=False)
    parser.add_argument("--agent", dest="agent", default=None)
    parser.add_argument("--permission-mode", dest="permission_mode", default=None)
    parser.add_argument("--model", dest="model", default=None)
    parser.add_argument("--max-turns", dest="max_turns", default=None)
    parser.add_argument("--system-prompt", dest="system_prompt", default=None)

    args, _ = parser.parse_known_args()

    if not args.prompt:
        print("[copilot-shim] error: -p/--prompt is required", file=sys.stderr)
        sys.exit(1)

    # Prepend system prompt (agent identity) to main prompt so Copilot gets role context
    if args.system_prompt:
        full_prompt = f"{args.system_prompt}\n\n---\n\n{args.prompt}"
    else:
        full_prompt = args.prompt

    cwd = os.getcwd()
    cmd = [
        COPILOT_BIN,
        "-p", full_prompt,
        "--allow-all-tools",
        "--allow-all-paths",
        "--add-dir", cwd,
    ]

    try:
        result = subprocess.run(cmd, cwd=cwd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"[copilot-shim] error: copilot not found at {COPILOT_BIN}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
