#!/usr/bin/env python3

"""Match EAF files to recording sessions.

Reads the JSON output by create_file_mapping.py and finds unique
recording sessions and all associated annotations.

Attempts to determine the status of these annotations, removes
duplicate annotation files, and sorts them in order of (marked done,
most recent, largest file, shortest name).

Links annotations to recordings, sorting in order of (marked as
edited, highest sampling rate).

Writes JSON which can then be used to construct the dictionary (or
manually pruned/edited if need be).

As with create_file_mapping.py this is more complicated than it needs
to be, because the annotations have been reorganized and cleaned up.

"""

import argparse
import datetime
import itertools
import json
import logging
import re
from collections import defaultdict
from os import PathLike
from pathlib import Path
from typing import Any

import pympi  # type: ignore

LOGGER = logging.getLogger(Path(__file__).stem)


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "annodir", help="Directory containing annotation files", type=Path
    )
    parser.add_argument("metadata", help="JSON file with annotation info")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose debug output"
    )
    return parser


def add_recordings(
    session_data: dict[str, Any],
    info: dict[str, list],
    annodir: PathLike,
    pathpath: PathLike,
):
    recording_paths = set(x["path"] for x in session_data["recordings"])
    for recording in itertools.chain(info["recordings"], info["mp3s"], info["wavs"]):
        if "metadata" in recording:
            recording_id = recording["metadata"]["FileName"]
            if recording_id not in session_data["metadata"]:
                session_data["metadata"][recording_id] = recording["metadata"]
            assert session_data["metadata"][recording_id] == recording["metadata"]
            recording["metadata_id"] = recording_id
            del recording["metadata"]
        if "speaker" in recording:
            speaker_id = recording["speaker"]["ID"]
            if speaker_id not in session_data["metadata"]:
                session_data["speakers"][speaker_id] = recording["speaker"]
            assert session_data["speakers"][speaker_id] == recording["speaker"]
            recording["speaker_id"] = speaker_id
            del recording["speaker"]
        if "path" not in recording:
            recording["path"] = str(pathpath / recording["name"])
            if not (annodir / recording["path"]).exists():
                LOGGER.warning(
                    "Annotation recording %s does not exist, skipping",
                    recording["path"],
                )
                continue
        if "metadata_id" in recording and recording["path"] not in recording_paths:
            session_data["recordings"].append(recording)


def find_sessions(annodir: PathLike, metadata: list[list]):
    """Find annotation sessions and associated EAF and audio files."""
    sessions: dict[str, dict] = {}
    for path, info in metadata:
        pathpath = Path(path)
        session_id = None
        session_status = None
        for part in pathpath.parts:
            session_match = re.match(r"(\S*\d\d\d\d-?\d\d-?\d\d(?:-\d\d)?)", part)
            if session_match:
                session_id = session_match.group(1)
            status_match = re.search(
                r"(DONE|ERROR|WORKING|FINISHED|GUIDE|STOPPED)", part, re.I
            )
            if status_match:
                session_status = status_match.group(1).upper()
        if session_id is None:
            # Try harder! Perhaps there are some EAFs? (we still
            # require one unique session per directory)
            for entry in (annodir / path).iterdir():
                session_match = re.match(
                    r"(\S*\d\d\d\d-?\d\d-?\d\d(?:-\d\d)?).*\.eaf", entry.name
                )
                if session_match:
                    if session_id is None:
                        session_id = session_match.group(1)
                    elif session_id != session_match.group(1):
                        LOGGER.warning(
                            "Multiple sessions in directory %s (%s != %s), skipping",
                            path,
                            session_id,
                            session_match.group(1),
                        )
                        continue
        if session_id is None:
            LOGGER.warning("Failed to find session ID in directory %s", path)
            continue
        if session_id not in sessions:
            sessions[session_id] = {
                "annotations": [],
                "recordings": info["recordings"],
                "metadata": {},
                "speakers": {},
            }
        session_data = sessions[session_id]
        add_recordings(session_data, info, annodir, pathpath)
        for eaf in info["eafs"]:
            name = eaf["name"]
            session_match = re.match(r"(\S*\d\d\d\d-?\d\d-?\d\d(?:-\d\d)?)", name)
            if session_match:
                file_session_id = session_match.group(1)
                if session_id is not None and file_session_id != session_id:
                    LOGGER.warning(
                        "File %s session_id %s does not match directory %s",
                        name,
                        file_session_id,
                        session_id,
                    )
            eaf["path"] = str(pathpath / name)
            eaf["status"] = session_status
            session_data["annotations"].append(eaf)
    for path, session_data in sessions.items():
        sort_eafs(session_data["annotations"])
    return sessions


def sort_eafs(eafs: list[dict]):
    """Sort a list of EAF files somewhat optimally, by best status, most
    annotations, most recent, largest, and shortest filename.
    """
    eafs.sort(
        key=lambda x: (
            x["status"] in ("DONE", "FINISHED"),
            x.get("annodate", x["mtime"]),
            x.get("nexport", 0),
            -len(x["name"]),
            x["size"],
        ),
        reverse=True,
    )


def merge_eafs_by_content(annodir: PathLike, session_id: str, eafs: list[dict]):
    """Merge equivalent EAFs, as determined by the timestamps and annotations."""
    cache: dict[str, pympi.Elan.Eaf] = {}
    for eaf in eafs:
        path = eaf["path"]
        try:
            cache[path] = pympi.Elan.Eaf(annodir / path)
        except Exception as exc:
            LOGGER.warning("Invalid EAF: %s (%s)", path, exc)
            continue
        eaf["annodate"] = datetime.datetime.fromisoformat(
            cache[path].adocument["DATE"]
        ).timestamp()
        export_tier_name = cache[path].get_tier_ids_for_linguistic_type("tmd-export")
        if export_tier_name:
            _, annotations, _, _ = cache[path].tiers[export_tier_name[0]]
            eaf["nexport"] = sum(
                export == "Export" for _, export, _, _ in annotations.values()
            )

    while True:
        neafs = len(eafs)
        to_remove = set()
        sort_eafs(eafs)
        for idx, eaf in enumerate(eafs):
            if idx in to_remove:
                continue
            elan = cache.get(eaf["path"], None)
            if elan is None:
                to_remove.add(idx)
                continue
            for jdx in range(idx + 1, len(eafs)):
                if jdx in to_remove:
                    continue
                other_path = eafs[jdx]["path"]
                other = cache.get(other_path, None)
                if other is None:
                    to_remove.add(jdx)
                    continue
                LOGGER.debug("%d %d", idx, jdx)
                if elan.tiers == other.tiers and elan.timeslots == other.timeslots:
                    to_remove.add(jdx)
        new_eafs = []
        for idx, eaf in enumerate(eafs):
            if idx not in to_remove:
                new_eafs.append(eaf)
        LOGGER.debug(f"{session_id}: {neafs} => {len(new_eafs)}")
        if neafs == len(new_eafs):
            break
        eafs = new_eafs
    return eafs


def prune_eafs(annodir: PathLike, sessions: dict[str, dict]):
    """Remove duplicate EAFs from each session."""
    for session_id, session_data in sessions.items():
        eafs = defaultdict(list)
        # Add them in previously sorted order to get the "best" one (even though they're the same)
        for eaf in session_data["annotations"]:
            eafs[eaf["md5"]].append(eaf)
        new_eafs = []
        for md5 in eafs:
            new_eafs.append(eafs[md5][0])
        LOGGER.debug(
            f"{session_id}: {len(session_data['annotations'])} => {len(new_eafs)}"
        )
        new_eafs = merge_eafs_by_content(annodir, session_id, new_eafs)
        sort_eafs(new_eafs)
        session_data["annotations"] = new_eafs


if __name__ == "__main__":
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    with open(args.metadata) as infh:
        metadata = json.load(infh)
    session_data = find_sessions(args.annodir, metadata)
    prune_eafs(args.annodir, session_data)
    print(json.dumps(sorted(session_data.items()), indent=2))
