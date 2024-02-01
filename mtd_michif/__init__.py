"""
Package for building the Turtle Mountain Dictionary of Michif.
"""

import argparse
import logging
from pathlib import Path


def make_argparse() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations",
                        type=Path, help="Path to mtd-michif-annotations",
                        default=Path.cwd().parent / "mtd-michif-annotations")
    parser.add_argument("--recordings",
                        type=Path, help="Path to mtd-michif-recordings",
                        default=Path.cwd().parent / "mtd-michif-recordings")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging output")
    return parser


def main() -> None:
    """Entry-point for dictionary build."""
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    
