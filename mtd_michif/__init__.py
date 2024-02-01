"""
Package for building the Turtle Mountain Dictionary of Michif.
"""

import argparse
import json
import logging
from pathlib import Path

from .read_metadata import read_metadata
from .create_file_mapping import ElanUntangler
from .create_session_mapping import find_sessions, prune_eafs
from .create_channel_mapping import create_channel_mapping
from .dictionary import Dictionary

LOGGER = logging.getLogger("mtd-michif")


def make_argparse() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Path to mtd-michif-annotations",
        default=Path.cwd().parent / "mtd-michif-annotations",
    )
    parser.add_argument(
        "--recordings",
        type=Path,
        help="Path to mtd-michif-recordings",
        default=Path.cwd().parent / "mtd-michif-recordings",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging output"
    )
    parser.add_argument(
        "-b",
        "--build",
        help="Directory for intermediate files",
        default=Path.cwd() / "build",
    )
    return parser


DICT_TXT = Path("txt") / "laverdure_allard_1983_revised.txt"
METADATA = Path("metadata") / "TMD Metadata.xlsx"
UNCORRECTABLES = Path(__file__).parent / "models" / "uncorrectables.json"


def check_directories(parser: argparse.ArgumentParser, args: argparse.Namespace):
    """Verify that input directories exist and contain data."""
    if not (args.annotations / DICT_TXT).exists():
        parser.error("Dictionary text not found in %s" % args.annotations)
    if not (args.annotations / METADATA).exists():
        parser.error("Metadata not found in %s" % args.annotations)
    if not (args.annotations / "eaf").exists():
        parser.error("EAF directory not found in %s" % args.annotations)
    if not args.recordings.glob("*.flac"):
        parser.error("No audio found in %s" % args.recordings)


def write_json(data: any, outfile: Path) -> None:
    with open(outfile, "wt") as outfh:
        json.dump(data, outfh, indent=2, ensure_ascii=False)


def main() -> None:
    """Entry-point for dictionary build."""
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    check_directories(parser, args)
    args.build.mkdir(exist_ok=True)

    LOGGER.info("Reading metadata from %s...", args.annotations / METADATA)
    metadata = read_metadata(args.annotations / METADATA)
    write_json(metadata, args.build / "metadata.json")

    LOGGER.info("Matching recordings and annotations...")
    untangler = ElanUntangler(metadata)
    untangler.add_recordings(args.recordings)
    untangler.add_annotations(args.annotations)
    untangler.resolve_annotations()
    annotation_data = sorted(untangler.annodirs.items())
    write_json(annotation_data, args.build / "annotation_dirs.json")

    LOGGER.info("Finding recording sessions...")
    sessions = find_sessions(args.annotations, annotation_data)
    session_data = sorted(sessions.items())
    write_json(session_data, args.build / "annotation_sessions.json")

    LOGGER.info("Creating channel mapping...")
    channel_mapping = create_channel_mapping(
        args.recordings, args.annotations, session_data
    )
    write_json(channel_mapping, args.build / "channel_mapping.json")

    LOGGER.info("Processing text dictionary...")
    dictionary = Dictionary.from_text(
        args.annotations / DICT_TXT, uncorrectables=Dictionary.load_json(UNCORRECTABLES)
    )
    dictionary.save_json(args.build / "laverdure.json")
