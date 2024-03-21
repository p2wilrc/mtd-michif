#!/usr/bin/env python3

"""
Generate ELAN directories for reannotation from list of failed alignments.
"""

import argparse
import csv
import datetime
import itertools
import json
import logging
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from pympi.Elan import Eaf  # type: ignore
from tqdm.contrib.concurrent import process_map

from mtd_michif.elan import format_time, parse_time

LOGGER = logging.getLogger("bad-annotations-to-elan")
PFSX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<preferences version="1.1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.mpi.nl/tools/elan/Prefs_v1.1.xsd">
    <pref key="LayoutManager.SelectedTabIndex">
        <Int>0</Int>
    </pref>
    <pref key="LayoutManager.VisibleMultiTierViewer">
        <String>mpi.eudico.client.annotator.viewer.TimeLineViewer</String>
    </pref>
    <pref key="GridViewer.MultiTierMode">
        <Boolean>true</Boolean>
    </pref>
    <pref key="GridViewer.TierName">
        <String>VID-text</String>
    </pref>
    <pref key="GridViewer.MultiTierMode.Subdivision">
        <Boolean>false</Boolean>
    </pref>
    <pref key="MultiTierViewer.ActiveTierName">
        <String>VID-text</String>
    </pref>
    <pref key="SelectionBeginTime">
        <Long>%(begin)d</Long>
    </pref>
    <pref key="SelectionEndTime">
        <Long>%(end)d</Long>
    </pref>
    <pref key="TimeScaleBeginTime">
        <Long>%(wbegin)d</Long>
    </pref>
    <pref key="MediaTime">
        <Long>%(begin)d</Long>
    </pref>
    <pref key="SignalViewer.ZoomLevel">
        <Float>100.0</Float>
    </pref>
    <pref key="TimeLineViewer.ZoomLevel">
        <Float>100.0</Float>
    </pref>
    <pref key="LayoutManager.CurrentMode">
        <Int>1</Int>
    </pref>
    <prefList key="MultiTierViewer.HiddenTiers">
        <String>VID-translation</String>
        <String>VID-notes</String>
        <String>VID-TMD-annotation-status</String>
    </prefList>
</preferences>
"""
HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
<title>ELAN files for checking</title>
<meta charset="UTF-8">
</head>
<body>
<h1>ELAN files for checking</h1>
"""
HTML_FOOTER = """</body>
</html>
"""


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-metadata",
        type=Path,
        help="Session metadata file.",
        default="data/annotation_sessions.json",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Base directory for annotations",
        default="raw/Annotations",
    )
    parser.add_argument(
        "--recordings",
        type=Path,
        help="Base directory for recordings",
        default="raw/Recordings",
    )
    parser.add_argument(
        "-n",
        "--num-sessions",
        type=int,
        default=0,
        help="Number of sessions per output directory (0 for all of them)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Directory where ELAN files will be written",
    )
    parser.add_argument(
        "-w",
        "--website",
        help="Base URL of dictionary for ELAN reannotation packages",
        default="https://localhost:4200",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose debug output"
    )
    parser.add_argument(
        "--problem-entries",
        type=Path,
        help="JSON file with 'problem' dictionary entries",
        default="logs/problem_entries.json",
    )
    parser.add_argument(
        "csvs",
        help="CSV files of individual bad annotation spans (without audio/entries)",
        type=Path,
        nargs="+",
    )
    return parser


def create_elan_files(outdir, session_info, recordings, annotations, start, end):
    """Create ELAN files for annotation."""
    eaf_info = session_info["annotations"][0]
    audio_info = session_info["recordings"][0]
    eaf_path = annotations / eaf_info["path"]
    speaker = session_info["speakers"][audio_info["speaker_id"]]
    speaker_name = " ".join(
        (
            speaker["First Name"],
            speaker["Last Name"],
        )
    )
    # Create or copy reduced audio
    mp3_path = None
    flac_path = recordings / audio_info["path"]
    for path in [
        recordings / f"{flac_path.stem}-elan.mp3",
        eaf_path.parent / f"{eaf_path.stem}-elan.mp3",
    ]:
        if path.exists():
            mp3_path = outdir / f"{eaf_path.stem}-elan.mp3"
            LOGGER.info("Copying MP3 from %s to %s", path, mp3_path)
            shutil.copy(path, mp3_path)
    if mp3_path is None:
        mp3_path = outdir / f"{eaf_path.stem}-elan.mp3"
        if not mp3_path.exists():
            LOGGER.info("Creating MP3 in %s", mp3_path)
            subprocess.run(
                [
                    "sox",
                    "-V1",
                    flac_path,
                    "-C",
                    "16.0",  # cannot use VBR, ELAN will fail
                    mp3_path,
                ],
                check=True,
            )
    eaf = Eaf(eaf_path)
    # Take this opportunity to fix a few things in the EAF
    for name, (_, _, attributes, _) in eaf.tiers.items():
        if "PARTICIPANT" in attributes and attributes["PARTICIPANT"] != speaker_name:
            LOGGER.info(
                "Fixing up PARTICIPANT in tier %s (was '%s', now '%s')",
                name,
                attributes["PARTICIPANT"],
                speaker_name,
            )
            attributes["PARTICIPANT"] = speaker_name
    eaf.media_descriptors = [
        {
            "MIME_TYPE": "audio/mpeg",
            "MEDIA_URL": f"file://{mp3_path.absolute()}",  # OMG WTF ELAN
            "RELATIVE_MEDIA_URL": f"./{mp3_path.name}",
        },
    ]
    eaf.to_file(outdir / eaf_path.name)
    # Set some reasonable preferences for ELAN
    with open(outdir / eaf_path.with_suffix(".pfsx").name, "wt") as outfh:
        outfh.write(PFSX_TEMPLATE % dict(wbegin=start - 500, begin=start, end=end))


def create_elan_directory(
    problem_annotations,
    session_metadata,
    recordings: Path,
    annotations: Path,
    outdir: Path,
    sessions: list[str],
    website: str = "https://dictionary.michif.org",
) -> tuple[list, list]:
    elan_files = []
    assignments = []
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "clips").mkdir(exist_ok=True)
    with open(outdir / "index.html", "wt") as outfh:
        outfh.write(HTML_HEADER)
        for session in sessions:
            infos = problem_annotations[session]
            session_info = session_metadata[session]
            eaf_info = session_info["annotations"][0]
            eaf_name = Path(eaf_info["path"]).name
            if ":" in infos[0]["Start"]:
                start = parse_time(infos[0]["Start"])
            else:
                start = int(infos[0]["Start"])
            if ":" in infos[0]["End"]:
                end = parse_time(infos[0]["End"])
            else:
                end = int(infos[0]["End"])
            elan_files.append(
                (
                    outdir,
                    session_info,
                    recordings,
                    annotations,
                    start,
                    end,
                )
            )
            assignments.append(
                {
                    "Session": session,
                    "Directory": outdir.name,
                    "Filename": eaf_name,
                }
            )
            outfh.write(f"<h2>{eaf_name}</h2>\n")
            outfh.write("<ul>\n")
            for info in infos:
                if ":" in info["Start"]:
                    display_start = info["Start"]
                else:
                    display_start = format_time(float(info["Start"]))
                if ":" in info["End"]:
                    display_end = info["End"]
                else:
                    display_end = format_time(float(info["End"]))
                outfh.write("  <li>\n")
                if "MP3" in info:
                    mp3 = Path(info["MP3"])
                    shutil.copy(mp3, outdir / "clips" / mp3.name)
                    outfh.write(
                        f'    <a target="_blank" href="{website}/search?show={info["ID"]}">{info["ID"]}</a>:\n'
                    )
                    outfh.write(
                        f"    {info['Text']} ({display_start} - {display_end})\n"
                    )
                    if "Details" in info:
                        outfh.write("(")
                        outfh.write(info["Details"].replace(",", ", "))
                        outfh.write(")\n")
                    outfh.write(f"    <br><audio controls src='clips/{mp3.name}'>\n")
                    outfh.write(
                        f"      <a href='clips/{mp3.name}'>Download audio</a>\n"
                    )
                    outfh.write("    </audio>\n")
                else:
                    outfh.write(f"    {info['EAF']}:\n")
                    outfh.write(
                        f"    {info['Text']} ({display_start} - {display_end})\n"
                    )
                outfh.write("  </li>\n")
            outfh.write("</ul>\n")
        outfh.write(HTML_FOOTER)
    return elan_files, assignments


def problem_annotations_to_elan(
    session_metadata: dict[str, dict],
    recordings: Path,
    annotations: Path,
    csvs: list[Path],
    output: Path,
    website: str = "https://dictionary.michif.org",
    num_sessions: int = 1,
):
    eaf_map = {}
    for session, session_info in session_metadata.items():
        eaf_info = session_info["annotations"][0]
        eaf_name = Path(eaf_info["path"]).name
        eaf_map[eaf_name] = session

    problem_annotations = defaultdict(list)
    for path in csvs:
        with open(path) as infh:
            reader = csv.DictReader(infh)
            for row in reader:
                if "Session" in row:
                    assert (
                        row["Session"] in session_metadata
                    ), f"Session {row['Session']} not found in metadata"
                else:
                    assert (
                        row["EAF"] in eaf_map
                    ), f"EAF {row['EAF']} not found in metadata"
                    row["Session"] = eaf_map[row["EAF"]]
                problem_annotations[row["Session"]].append(row)

    for session, to_check in problem_annotations.items():

        def row_key(row):
            return row["Start"], row["End"]

        to_check.sort(key=row_key)
        new_to_check = []
        for (start, end), group in itertools.groupby(to_check, row_key):
            rows = list(group)
            details = [r["Details"] for r in rows if "Details" in r]
            rows[0]["Details"] = ",".join(details)
            new_to_check.append(rows[0])
        problem_annotations[session] = new_to_check

    sessions = sorted(problem_annotations.keys())
    today = datetime.date.today().strftime("%Y%m%d")
    if num_sessions == 0:
        LOGGER.info("Creating ELAN files in %s", output)
        elan_files, assignments = create_elan_directory(
            problem_annotations,
            session_metadata,
            recordings,
            annotations,
            output,
            sessions,
            website,
        )
    else:
        elan_files = []
        assignments = []
        for idx, i in enumerate(range(0, len(sessions), num_sessions)):
            outdir = output / ("elan_files_%s_%d" % (today, idx))
            LOGGER.info("Creating ELAN files in %s", outdir)
            f, a = create_elan_directory(
                problem_annotations,
                session_metadata,
                recordings,
                annotations,
                outdir,
                sessions[i : i + num_sessions],
                website,
            )
            elan_files.extend(f)
            assignments.extend(a)
    process_map(create_elan_files, *zip(*elan_files))
    with open(output / f"assignments_{today}.csv", "wt") as outfh:
        writer = csv.DictWriter(
            outfh, fieldnames=["Directory", "Session", "Filename", "Annotator", "Done"]
        )
        writer.writeheader()
        writer.writerows(assignments)


def main(args):
    if not args.annotations.is_dir():
        LOGGER.error(
            "--annotations points to non-existent directory %s", args.annotations
        )
        sys.exit(1)
    if not args.recordings.is_dir():
        LOGGER.error(
            "--recordings points to non-existent directory %s", args.recordings
        )
        sys.exit(1)
    if args.output is None:
        LOGGER.warning("No --output specified, will do nothing")
        sys.exit(0)

    session_metadata = {}
    with open(args.session_metadata) as infh:
        for session, session_info in json.load(infh):
            session_metadata[session] = session_info

    problem_annotations_to_elan(
        session_metadata,
        args.recordings,
        args.annotations,
        args.csvs,
        args.output,
        args.website,
        args.num_sessions,
    )


if __name__ == "__main__":
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    main(args)
