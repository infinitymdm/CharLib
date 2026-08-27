#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse

from charlib.cli import run


# TODO: consider using click or typer in place of argparse
def main():
    """Run CharLib CLI"""
    # Set up charlib arguments
    parser = argparse.ArgumentParser(prog="charlib", description="Standard cell library characterizer")
    parser.add_argument("--debug", action="store_true", help="Dump extra information to debug_dir")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce the amount of information displayed")

    # Set up run subcommand
    # Other subcommands may be added in the future
    subparser = parser.add_subparsers(title="subcomamands", required=True)
    parser_characterize = subparser.add_parser("run", help="Characterize a standard cell library")

    # Set up charlib run arguments
    parser_characterize.add_argument(
        "library",
        type=str,
        help="A directory containing a valid config YAML file, or the full path such a file",
    )
    parser_characterize.add_argument(
        "-o", "--output", type=str, default="", help="Place the characterization results in the specified file"
    )
    parser_characterize.add_argument("-j", "--jobs", type=int, default=0, help="Specify the number of concurrent jobs")
    parser_characterize.add_argument(
        "-n", "--no-sim", action="store_true", help="Perform all tasks except for running simulations"
    )
    parser_characterize.add_argument(
        "-f",
        "--filters",
        nargs="*",
        help="A list of one or more regex strings. Cell names matching one of the filters will be characterized",
    )
    parser_characterize.set_defaults(func=run.run)

    # Parse args and execute
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
