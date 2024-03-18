#!/usr/bin/env python3

"""Create much reduced MP3s for ELAN annotation.

It is vitally important that these be at *constant* bit rate because
otherwise ELAN will become unusably slow trying to calculate
timestamps.

Since we don't care much about audio quality we use 16kbit/sec.  This
is nonetheless *way* better than if we made WAV files at this same
bitrate!

It would be nice if ELAN supported OPUS...

"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from tqdm.contrib.concurrent import process_map

LOGGER = logging.getLogger("compress-elan-audio")


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-metadata",
        type=Path,
        help="Session metadata file.",
        default="build/annotation_sessions.json",
    )
    parser.add_argument(
        "--recordings",
        type=Path,
        help="Base directory for recordings",
        default=Path.cwd().parent / "mtd-michif-recordings",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Output directory for MP3 files for annotation",
        default=Path.cwd().parent / "mtd-michif-annotations",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be verbose",
    )
    return parser


def create_elan_audio(
    recordings: Path, annotations: Path, audio_info: dict, eaf_info: dict
):
    """Create ELAN files for annotation."""
    audio_path = Path(audio_info["path"])
    annotation_path = Path(eaf_info["path"])
    flac_path = recordings / audio_path
    mp3_path = annotations / annotation_path.with_name(
        f"{annotation_path.stem}-elan.mp3"
    )
    LOGGER.info("Creating MP3 in %s", mp3_path)
    mp3_path.parent.mkdir(exist_ok=True, parents=True)
    subprocess.run(
        [
            "lame",
            "--silent",
            "-b",
            "16",
            flac_path,
            mp3_path,
        ],
        check=True,
    )


def main(args):
    if not args.recordings.is_dir():
        LOGGER.error(
            "--recordings points to non-existent directory %s", args.recordings
        )
        sys.exit(1)

    audio_infos = []
    eaf_infos = []
    with open(args.session_metadata) as infh:
        for session, session_info in json.load(infh):
            audio_info = session_info["recordings"][0]
            audio_infos.append(audio_info)
            eaf_info = session_info["annotations"][0]
            eaf_infos.append(eaf_info)
    process_map(
        create_elan_audio,
        [args.recordings] * len(audio_infos),
        [args.annotations] * len(eaf_infos),
        audio_infos,
        eaf_infos,
    )


if __name__ == "__main__":
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    main(args)
