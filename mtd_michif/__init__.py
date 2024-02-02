"""
Package for building the Turtle Mountain Dictionary of Michif.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Iterator

from tqdm import tqdm  # type: ignore

from mtd.languages import LanguageConfig
from mtd.languages.suites import LanguageSuite

from click.testing import CliRunner

from .add_clarifications import add_clarifications
from .create_channel_mapping import create_channel_mapping
from .create_file_mapping import ElanUntangler
from .create_session_mapping import find_sessions
from .dictionary import Dictionary
from .elan_to_json import AudioExtractor
from .force_align import force_align
from .read_metadata import read_metadata

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
    parser.add_argument(
        "-o",
        "--assets-dir",
        help="Output directory for dictionary assets",
        type=Path,
        default=Path.cwd() / "projects" / "mtd" / "src" / "assets",
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


def find_annotations(
    args, session_data, channel_mapping
) -> Iterator[tuple[Path, dict, dict]]:
    """Determine the annotation and audio files to use for a given
    session."""
    seen_eafs = set()
    for session, info in session_data:
        LOGGER.info("Processing session %s", session)
        if len(info["annotations"]) == 0:
            LOGGER.warning("Session %s has no EAFs, skipping", session)
        elif len(info["annotations"]) > 1:
            LOGGER.warning(
                "Session %s has multiple distinct EAFs, using best one", session
            )
        eaf = info["annotations"][0]
        elan_file = args.annotations / eaf["path"]
        if eaf["md5"] in seen_eafs:
            LOGGER.warning("Skipping duplicate EAF %s (%s)", elan_file, eaf["md5"])
            return None
        seen_eafs.add(eaf["md5"])
        # The metadata in the EAF files is often wrong, so we will not use it
        audio = None
        # Get the best recording
        for recording in info["recordings"]:
            channels = channel_mapping[recording["path"]]
            if channels["export"]:
                # Use its metadata, adding in the export spec and fixing path
                audio = recording.copy()
                path = args.recordings / recording["path"]
                LOGGER.info(
                    "Looking for audio file %s in %s",
                    recording["path"],
                    args.recordings,
                )
                if not path.exists():
                    LOGGER.info(
                        "Looking for audio file %s in %s",
                        recording["path"],
                        args.annotations,
                    )
                    path = args.annotations / recording["path"]
                if not path.exists():
                    LOGGER.warning(
                        "Audio file %s does not exist, skipping", recording["path"]
                    )
                    continue
                audio["path"] = path
                audio["export"] = channels["export"]
                LOGGER.debug(
                    "Using audio from channels %s of %s",
                    audio["export"],
                    audio["path"],
                )
                break
        if audio is None:
            raise RuntimeError("Missing audio for session %s", session)
        if "metadata_id" not in audio:
            raise RuntimeError("Missing metadata for audio file %s", audio["path"])
        audio["metadata"] = info["metadata"][audio["metadata_id"]]
        if "speaker_id" not in audio:
            # Not a fatal error though...
            LOGGER.error("Missing speaker for audio file %s", audio["path"])
        else:
            audio["speaker"] = info["speakers"][audio["speaker_id"]]
        yield elan_file, audio, eaf


def dictionary_stats(dictionary: Dictionary) -> None:
    n_examples = 0
    missing_audio = 0
    missing_example_audio = 0
    entries = dictionary.entries.values()
    for entry in tqdm(entries):
        if not entry.audio:
            missing_audio += 1
        if entry.examples:
            n_examples += 1
            if all(not example.audio for example in entry.examples):
                missing_example_audio += 1
    LOGGER.info(
        "Dictionary has %d entries and %d entries with examples:",
        len(entries),
        n_examples,
    )
    LOGGER.info(
        "\t%d entries are missing audio (%.2f%%)",
        missing_audio,
        missing_audio / len(entries) * 100,
    )
    LOGGER.info(
        "\t%d entries are missing examples (%.2f%%)",
        len(entries) - n_examples,
        (len(entries) - n_examples) / len(entries) * 100,
    )
    LOGGER.info(
        "\t%d examples are missing audio (%.2f%%)",
        missing_example_audio,
        missing_example_audio / n_examples * 100,
    )


def fix_dictionary(dictionary: Dictionary, relpath: str) -> None:
    for entry in dictionary.entries.values():
        for audio in entry.audio:
            audio.path = "/".join((relpath, Path(audio.path).name))
        entry.audio.sort(key=lambda x: (x.speaker, x.path), reverse=True)
        for example in entry.examples:
            for audio in example.audio:
                audio.path = "/".join((relpath, Path(audio.path).name))
            example.audio.sort(key=lambda x: (x.speaker, x.path), reverse=True)
        entry.examples.sort(key=lambda x: (x.score, x.english, x.michif))


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
        args.annotations / DICT_TXT,
        uncorrectables=Dictionary.load_json(UNCORRECTABLES),
    )
    dictionary.save_json(args.build / "laverdure.json")

    LOGGER.info("Matching annotated audio to dictionary entries...")
    matcher = AudioExtractor(
        dictionary,
        output_audio_dir=args.assets_dir / "data" / "audio",
    )
    elan_files = list(find_annotations(args, session_data, channel_mapping))
    for elan_file, audio, eaf in tqdm(elan_files):
        LOGGER.info("Processing ELAN file %s", elan_file)
        updated_entries = matcher.extract_audio(
            eaf_path=elan_file, audio_info=audio
        )
        LOGGER.info("Updated %d entries", len(updated_entries))

    LOGGER.info("Finding fallback audio...")
    updated_entries = matcher.find_fallback_audio()
    LOGGER.info("Updated %d entries", len(updated_entries))
    for entry in dictionary.entries.values():
        entry.audio.sort(key=lambda x: (x.speaker, x.path), reverse=True)
        for example in entry.examples:
            if example.audio:
                example.audio.sort(key=lambda x: (x.speaker, x.path), reverse=True)
        entry.examples.sort(key=lambda x: (x.score, x.english, x.michif))
    dictionary.save_json(args.build / "laverdure_matched.json")
    dictionary_stats(dictionary)

    LOGGER.info("Force-aligning for read-alongs...")
    force_align(dictionary)
    dictionary.save_json(args.build / "laverdure_aligned.json")

    LOGGER.info("Moving clarifications onto headwords...")
    add_clarifications(dictionary)
    dictionary.save_json(args.build / "laverdure_clarified.json")

    LOGGER.info("Final dictionary preprocessing for MotherTongues...")
    fix_dictionary(dictionary, "data/audio")
    dictionary.save_json(args.build / "laverdure_final.json")

    LOGGER.info("Exporting dictionary for MotherTongues...")
    config_json = Path(__file__).parent.parent / "config" / "config.json"
    config = LanguageConfig(str(config_json))
    ls = LanguageSuite([config])
    # There should be only one dictionary
    d = ls.dictionaries[0]
    # FIXME: MTD reallly should indent these... currently doesn't...
    with open(args.assets_dir / "js" / "config-michif.js", "wt") as outfh:
        outfh.write(d.return_formatted_config(form="js"))
    with open(args.assets_dir / "js" / "dict_cached-michif.js", "wt") as outfh:
        outfh.write(d.return_formatted_data(form="js"))
    LOGGER.info("Done!  You may test the dictionary with `npm start`.")
