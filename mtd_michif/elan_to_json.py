"""
Extract TMD recordings and convert ELAN annotations into JSON
...which will then be converted into CSV for MotherTongues.

This uses the metadata extracted by read_metadata.py,
create_file_mapping.py and prune_eafs.py to find annotation files and
their associated recordings.  It performs some validation and
integrity checking on the output and reports prblems to standard error.

"""

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from os import PathLike
from pathlib import Path
from typing import Optional

from tqdm import tqdm  # type: ignore

from mtd_michif.dictionary import Dictionary
from mtd_michif.elan import AnnotationMatcher, Span, SpanExtractor
from mtd_michif.textnorm import normalize_michif
from mtd_michif.types import Clip, Entry, Example

LOGGER = logging.getLogger("elan-to-json")


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dictionary",
        "-d",
        default="build/laverdure.json",
        metavar="JSON",
        help="the JSON dictionary base",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="the output JSON file",
    )
    parser.add_argument(
        "--bad-annotations",
        type=Path,
        help="Path to write CSV of annotations to be manually checked.",
    )
    parser.add_argument(
        "--bad-audios",
        type=Path,
        help="Path to write CSV of audio files to be manually checked.",
    )
    parser.add_argument(
        "--log",
        "-l",
        metavar="FILE",
        help="output file for logs",
    )
    parser.add_argument(
        "--all-sessions",
        "-a",
        action="store_true",
        help="Use all annotation sessions (not just those marked completed)",
    )
    parser.add_argument(
        "--session", help="Extract only a single session (for debugging/testing)"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing output audio files",
    )
    parser.add_argument(
        "--session-metadata",
        "-m",
        default="build/annotation_sessions.json",
        metavar="PATH",
        help="the JSON file with sessions and metadata",
    )
    parser.add_argument(
        "--channel-mapping",
        "-c",
        default="build/channel_mapping.json",
        metavar="PATH",
        help="the JSON file with channel mappings for audio files",
    )
    parser.add_argument(
        "--output-audio-dir",
        "-A",
        metavar="PATH",
        help="the directory to save new audio files to",
        type=Path,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose debug output"
    )
    parser.add_argument(
        "--recordings",
        metavar="RECORDINGS_DIR",
        default="../mtd-michif-recordings",
        help="Base directory for recordings",
        type=Path,
    )
    parser.add_argument(
        "--annotations",
        metavar="ANNOTATION_DIR",
        default="../mtd-michif-annotations",
        help="Base directory for annotations",
        type=Path,
    )
    return parser


def find_annotations(
    args, session, session_data, channel_mapping, seen_eafs
) -> Optional[tuple[Path, dict, dict]]:
    """Determine the annotation and audio files to use for a given
    session.
    """
    LOGGER.info("Processing session %s", session)
    if len(session_data["annotations"]) == 0:
        LOGGER.warning("Session %s has no EAFs, skipping", session)
    elif len(session_data["annotations"]) > 1:
        LOGGER.warning("Session %s has multiple distinct EAFs, using best one", session)
    eaf = session_data["annotations"][0]
    if (
        not args.all_sessions
        and not args.session
        and eaf["status"] not in (None, "DONE", "FINISHED")
    ):
        LOGGER.warning("Session %s has no completed EAFs, skipping", session)
        return None
    elan_file = args.annotations / eaf["path"]
    if eaf["md5"] in seen_eafs:
        LOGGER.warning("Skipping duplicate EAF %s (%s)", elan_file, eaf["md5"])
        return None
    seen_eafs.add(eaf["md5"])
    # The metadata in the EAF files is often wrong, so we will not use it
    audio = None
    # Get the best recording
    for recording in session_data["recordings"]:
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
    audio["metadata"] = session_data["metadata"][audio["metadata_id"]]
    if "speaker_id" not in audio:
        # Not a fatal error though...
        LOGGER.error("Missing speaker for audio file %s", audio["path"])
    else:
        audio["speaker"] = session_data["speakers"][audio["speaker_id"]]
    return elan_file, audio, eaf


def get_speaker_name(audio_info, path) -> str:
    """Get speaker name from session metadata (EAF participant is often bogus)"""
    if "speaker" in audio_info:
        speaker = " ".join(
            (
                audio_info["speaker"]["First Name"],
                audio_info["speaker"]["Last Name"],
            )
        )
    else:
        # FIXME: Use Participant info in EAF
        logging.error("Unknown speaker for ELAN file %s", path.name)
        speaker = "Unknown"
    return speaker


class AudioExtractor(AnnotationMatcher):
    """A matcher for extracting audio clips"""

    def __init__(
        self,
        dictionary: Dictionary,
        output_audio_dir: Optional[PathLike] = None,
        force_audio=False,
    ):
        self.force_audio = force_audio
        self.output_audio_dir = (
            None if output_audio_dir is None else Path(output_audio_dir)
        )
        self.audio_info = {"name": "UNKNOWN", "path": "UNKNOWN"}
        self.bad_audios: list[dict] = []
        super().__init__(dictionary)

    def extract_audio(
        self,
        eaf_path: PathLike,
        audio_info: dict,
    ) -> list[Entry]:
        self.audio_info = audio_info
        speaker_name = get_speaker_name(audio_info, eaf_path)
        try:
            extractor = SpanExtractor(eaf_path)
        except RuntimeError as err:
            logging.error("Error reading %s: %s", eaf_path, err)
            return []
        if speaker_name and speaker_name != extractor.attributes["PARTICIPANT"]:
            LOGGER.warning(
                "%s: Speaker name from metadata %s does not match PARTICIPANT %s",
                eaf_path,
                speaker_name,
                extractor.attributes["PARTICIPANT"],
            )
        # For any given EAF, we should have one (and *only* one, but
        # good luck with that) sequence of Spans for any given Entry
        # and Example.
        entry_spans: defaultdict[Entry, list[Span]] = defaultdict(list)
        example_spans: defaultdict[tuple[Entry, Example], list[Span]] = defaultdict(
            list
        )
        for span in extractor:
            if not span.export:
                continue
            # We already know it won't match! Don't do anything and don't log it
            if span.annotations.get("tmd-match") == "No match (new)":
                continue
            matches = self.match_span(span)
            if not matches:
                LOGGER.error("NO MATCHES: %s", span)
                self.bad_annotations.append(span)
                continue
            # Take only the *best* match to avoid having zillions of
            # audio clips for common words!
            match_type, matched_by, score, entry, maybe_example = matches[0]
            if matched_by == "Headword":
                entry_spans[entry].append(span)
            elif matched_by == "Example":
                assert maybe_example is not None
                example_spans[entry, maybe_example].append(span)
        updated_entries: set[Entry] = set()
        for entry, spans in entry_spans.items():
            updated_entries.add(entry)
            for clip, warnings in self.create_audio_clips(
                entry.michif,
                spans,
                speaker_name,
            ):
                entry.audio.append(clip)
                if warnings:
                    self.add_bad_audio(entry.id, entry.michif, clip, warnings)
        for (entry, example), spans in example_spans.items():
            updated_entries.add(entry)
            for clip, warnings in self.create_audio_clips(
                example.michif,
                spans,
                speaker_name,
            ):
                example.audio.append(clip)
                if warnings:
                    self.add_bad_audio(entry.id, example.michif, clip, warnings)
        return list(updated_entries)

    def add_bad_audio(
        self, entry_id: Optional[str], text: str, clip: Clip, warnings: str
    ):
        """Add a clip to the list for review (in the same format as produced
        by force_align.py)."""
        # FIXME: Duplicated code with force_align.py
        m = re.match(
            r"(.*-\d\d\d\d-?\d\d-?\d\d(?:-\d\d)?).*-(\d+\.\d+)-(\d+\.\d+)\.\w+$",
            clip.path.name,
        )
        if m is None:
            LOGGER.error("Failed to parse time from path: %s", clip.path.name)
            return
        session, start, end = m.groups()
        dstart = str(round(float(start) * 1000))
        dend = str(round(float(end) * 1000))
        self.bad_audios.append(
            {
                "ID": str(entry_id),
                "Text": text,
                "Session": session,
                "Start": dstart,
                "End": dend,
                "MP3": clip.path,
                "Details": warnings,
            }
        )

    def write_bad_audios(self, outfh):
        writer = csv.DictWriter(
            outfh, ["ID", "Text", "Session", "Start", "End", "MP3", "Details"]
        )
        writer.writeheader()
        for info in self.bad_audios:
            writer.writerow(info)

    def create_audio_clips(
        self, text: str, spans: list[Span], speaker_name: Optional[str]
    ) -> list[tuple[Clip, str]]:
        if len(spans) == 0:
            return []
        LOGGER.info("Creating audio clips for %s", text)
        clips = []
        for group, warnings in self.group_spans(spans):
            clip = self.create_audio_clip(group, speaker_name)
            if clip is not None:
                clips.append((clip, warnings))
        return clips

    def create_audio_clip(
        self, spans: list[Span], speaker_name: Optional[str]
    ) -> Optional[Clip]:
        if speaker_name is None:
            speaker_name = "UNKNOWN"
        start = min(span.start for span in spans)
        end = max(span.end for span in spans)
        fileid = "%s-%.3f-%.3f" % (self.audio_info["name"], start * 0.001, end * 0.001)
        LOGGER.info("Creating %s.mp3 from spans:", fileid)
        ooo = False
        prev_end = 0
        duration = 0
        for span in spans:
            LOGGER.info("    %s", span)
            duration += span.start - span.end
            if span.start < prev_end:
                ooo = True
            prev_end = span.end
        if duration > 60000:
            LOGGER.error("Clip is much too long: %s", fileid)
            for span in spans:
                LOGGER.error("    %s", span)
                self.bad_annotations.append(span)
            return None
        if self.output_audio_dir is None:
            return Clip(speaker=speaker_name, path=("%s.mp3" % fileid))
        output_path = self.output_audio_dir / ("%s.mp3" % fileid)
        if output_path.exists() and not self.force_audio:
            LOGGER.info("%s: File exists, skipping", output_path)
            return Clip(speaker=speaker_name, path=output_path)
        audio_path = self.audio_info["path"]
        channels = self.audio_info.get("export", "-")
        if ooo:
            LOGGER.info("Spans are out of sequence, will splice...")
            return self.fancy_create_audio_clip(
                output_path, Path(audio_path), channels, spans, speaker_name
            )
        cmd = [
            "sox",
            "-V1",
            str(audio_path),
            str(output_path),
            "trim",
        ]
        for span in spans:
            cmd.append("=%.3f" % (span.start * 0.001))
            cmd.append("=%.3f" % (span.end * 0.001))
        cmd.append("remix")
        cmd.append(channels)
        subprocess.run(
            cmd,
            check=True,
        )
        return Clip(speaker=speaker_name, path=output_path)

    def fancy_create_audio_clip(
        self,
        output_path: Path,
        audio_path: Path,
        channels: str,
        spans: list[Span],
        speaker_name: str,
    ) -> Clip:
        with tempfile.TemporaryDirectory() as tempdir:
            span_files = []
            for idx, span in enumerate(spans):
                span_path = str(Path(tempdir) / ("span%d.wav" % idx))
                cmd = [
                    "sox",
                    str(audio_path),
                    span_path,
                    "trim",
                    "=%.3f" % (span.start * 0.001),
                    "=%.3f" % (span.end * 0.001),
                    "remix",
                    channels,
                ]
                subprocess.run(
                    cmd,
                    check=True,
                )
                span_files.append(span_path)
            cmd = [
                "sox",
                "-V1",
            ]
            cmd.extend(span_files)
            cmd.append(str(output_path))
            subprocess.run(
                cmd,
                check=True,
            )
        return Clip(speaker=speaker_name, path=output_path)

    def find_fallback_audio(self) -> list[Entry]:
        """Fill in missing Michif audio from other matching entries."""
        updated_entries = []
        for _, entries in self.michif_index.items():
            entry_clips = []
            for entry in entries:
                if entry.audio:
                    entry_clips.extend(entry.audio)
            if not entry_clips:
                continue
            entry_clips.sort(key=lambda x: (x.speaker, x.path), reverse=True)
            for entry in entries:
                updated = False
                if not entry.audio:
                    entry.audio = entry_clips[0:1]
                    updated = True
                for example in entry.examples:
                    if example.audio:
                        continue
                    example_michif = normalize_michif(example.michif)
                    example_clips = []
                    if example_michif in self.michif_example_index:
                        for _, ref_example in self.michif_example_index[example_michif]:
                            if ref_example.audio:
                                example_clips.extend(ref_example.audio)
                    if not example_clips:
                        continue
                    example_clips.sort(key=lambda x: (x.speaker, x.path), reverse=True)
                    example.audio = example_clips[0:1]
                    updated = True
                if updated:
                    updated_entries.append(entry)
        return updated_entries


def main():
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        filename=args.log,
        filemode="w",
    )
    dictionary = Dictionary.load_json(args.dictionary)
    LOGGER.info("Reading metadata from %s", Path(args.session_metadata).resolve())
    with open(args.session_metadata) as infh:
        metadata = json.load(infh)
    LOGGER.info(
        "Reading audio channel mapping from %s", Path(args.channel_mapping).resolve()
    )
    with open(args.channel_mapping) as infh:
        channel_mapping = json.load(infh)
    LOGGER.info("Recordings in %s", Path(args.recordings).resolve())
    LOGGER.info("Annotations in %s", Path(args.annotations).resolve())
    if args.output_audio_dir is not None:
        LOGGER.info("Writing audio files to %s", Path(args.output_audio_dir).resolve())
        os.makedirs(args.output_audio_dir, exist_ok=True)

    matcher = AudioExtractor(
        dictionary, output_audio_dir=args.output_audio_dir, force_audio=args.force
    )

    seen_eafs = set()
    elan_files = []
    for session, session_data in metadata:
        if args.session and session != args.session:
            continue
        info = find_annotations(args, session, session_data, channel_mapping, seen_eafs)
        if info is None:
            continue
        elan_files.append(info)
    elan_files.sort()
    LOGGER.info("Extracting audio...")
    for elan_file, audio, eaf in tqdm(elan_files):
        LOGGER.info("Processing ELAN file %s", elan_file)
        updated_entries = matcher.extract_audio(eaf_path=elan_file, audio_info=audio)
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
    if args.output:
        dictionary.save_json(args.output)
    if args.bad_annotations:
        with open(args.bad_annotations, "wt") as outfh:
            matcher.write_bad_annotations(outfh)
    if args.bad_audios:
        with open(args.bad_audios, "wt") as outfh:
            matcher.write_bad_audios(outfh)


if __name__ == "__main__":
    main()
