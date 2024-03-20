#!/usr/bin/env python3

"""Create mapping from metadata describing which channels (if any) to
export from recordings.

This might need to be be edited manually because this information is
not entirely machine-readable.  At present, it doesn't seem to cause
any problems.

"""

import argparse
import json
import logging
from itertools import chain
from os import PathLike
from pathlib import Path

LOGGER = logging.getLogger(Path(__file__).stem)


def make_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recdir", help="Directory containing recordings", type=Path)
    parser.add_argument("annodir", help="Directory containing annotation files")
    parser.add_argument("metadata", help="JSON file with session info")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose debug output"
    )
    return parser


def create_channel_mapping(
    recdir: PathLike, annodir: PathLike, sessions: list[list]
) -> dict:
    all_recordings = {}
    error = False
    for session, session_data in sessions:
        recordings = {}
        for recording in session_data["recordings"]:
            metadata = session_data["metadata"][recording["metadata_id"]]
            export = None
            recording_speaker = recording["speaker_id"]
            channels = recording["tag"]["channels"]
            if channels == 1:
                might_export = "1"
            else:
                # FIXME: mix all channels for now, identify speaker manually later
                might_export = "%d-%d" % (1, channels)

            if len(session_data["recordings"]) == 1:
                # If there is only one recording, take it
                export = might_export
            elif "-for_export" in recording["path"]:
                # If it says to export it, then export it, darnit!
                export = might_export
            elif recording_speaker == metadata["PrimarySpeaker"].strip().lower():
                export = might_export
            recordings[recording["path"]] = dict(export=export, tag=recording["tag"])
        if len(recordings) > 0 and all(
            r["export"] is None for r in recordings.values()
        ):
            error = True
            LOGGER.error(
                "No exportable recordings found for %s, please recheck metadata for:",
                session,
            )
            for r in recordings:
                LOGGER.error("     %s", r)
        all_recordings.update(recordings)
    if error:
        raise RuntimeError("Errors will found, will not produce output")
    return all_recordings


def main():
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    with open(args.metadata) as infh:
        metadata = json.load(infh)
    mapping = create_channel_mapping(args.recdir, args.annodir, metadata)
    print(json.dumps(mapping, indent=2))


if __name__ == "__main__":
    main()
