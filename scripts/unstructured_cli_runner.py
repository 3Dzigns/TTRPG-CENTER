#!/usr/bin/env python3
"""
unstructured_cli_runner.py
--------------------------

Minimal wrapper around the Unstructured CLI. Provides a fixed invocation of
`unstructured partition` plus lightweight `-?` help and `-v` version flags.
"""

import argparse
import importlib.util
import shutil
import subprocess
import sys

_DEFAULT_ARGS = [
    "--filename",
    "/Transfer_Station/sources/manual.pdf",
    "--strategy",
    "hi_res",
    "--languages",
    "eng",
    "--output-dir",
    "/Transfer_Station/Pass_A_Out",
    "--output-format",
    "json",
]

_CLI_BINARY = shutil.which("unstructured")
_CLI_MODULE = "unstructured.ingest.cli.main"


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="unstructured_cli_runner",
        description="Execute the Unstructured CLI with predefined arguments or pass-through flags.",
        add_help=False,
    )
    parser.add_argument("-?", "--help", dest="help_flag", action="store_true")
    parser.add_argument("-v", "--version", dest="version_flag", action="store_true")
    return parser.parse_known_args(argv)


def _print_help() -> None:
    print("Usage: unstructured_cli_runner.py [-?|-v] [unstructured partition args]")
    print("  (no extra args) Run the preset `unstructured partition` command.")
    print("  -?, --help      Show this message.")
    print("  -v, --version   Show Unstructured CLI version.")
    print("\nDefault command:")
    print("  unstructured partition " + " ".join(_DEFAULT_ARGS))


def _build_command(extra_args: list[str]) -> list[str] | None:
    if _CLI_BINARY:
        return ["unstructured", "partition", *extra_args]

    if importlib.util.find_spec(_CLI_MODULE):
        return [sys.executable, "-m", _CLI_MODULE, "partition", *extra_args]

    print(
        "error: Unstructured CLI not available (install `unstructured-ingest`).",
        file=sys.stderr,
    )
    return None


def _print_version() -> int:
    if _CLI_BINARY:
        return subprocess.call(["unstructured", "--version"])

    try:
        from unstructured.__version__ import __version__  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"error: unable to determine Unstructured version ({exc})", file=sys.stderr)
        return 1

    print(__version__)
    return 0


def main(argv: list[str]) -> int:
    args, passthrough = _parse_args(argv)

    if args.help_flag:
        _print_help()
        return 0

    if args.version_flag:
        if passthrough:
            print("error: -v/--version cannot be combined with other arguments", file=sys.stderr)
            return 2
        return _print_version()

    command = _build_command(passthrough if passthrough else _DEFAULT_ARGS)
    if not command:
        return 1
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
