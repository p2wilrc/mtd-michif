#!/usr/bin/env python3

"""Create mapping from sessions in metadata to FLAC/MP3/WAV audio
files in recordings.

This is now more complicated than it really needs to be, because the
recordings have been reorganized in a reasonably sane directory
structure.  Still, it tries to be robust, in the case where your
recordings are in different formats or with imprecise names.
"""

import argparse
import hashlib
import json
import logging
import os
import re
from itertools import chain
from os import PathLike
from pathlib import Path
from typing import Dict, Union

import tinytag  # type: ignore

LOGGER = logging.getLogger(Path(__file__).stem)


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", help="JSON file with recording metadata")
    parser.add_argument("recdir", help="Directory containing recordings")
    parser.add_argument("annodir", help="Directory containing annotation files")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose debug output"
    )
    return parser


class ElanUntangler:
    """Untangle ELAN, WAV, and MP3 files to augment metadata."""

    metadata: Dict[str, dict]
    recordings: Dict[str, dict]
    annodirs: Dict[str, Dict[str, Union[list, set]]]

    def __init__(self, metadata: dict):
        self.metadata = metadata
        self.recordings = {}
        self.annodirs = {}

    def _find_recordings(self, recdir: PathLike):
        """Find recordings in a directory and add basic info."""
        for root, dirs, files, rootfd in os.fwalk(recdir):
            annodir = Path(root)
            for name in files:
                if name.startswith("."):
                    continue
                path = annodir / name
                if not path.is_file:
                    continue
                try:
                    tag = tinytag.TinyTag.get(path)
                    reldir = annodir.relative_to(recdir)
                    if name in self.recordings:
                        LOGGER.warning("Duplicate recording: %s", name)
                        continue
                    base, _ = os.path.splitext(name)
                    LOGGER.info("Adding recording %s from %s", base, path)
                    self.recordings[base] = dict(
                        name=base,
                        path=str(reldir / name),
                        tag=dict(
                            duration=tag.duration,
                            samplerate=tag.samplerate,
                            channels=tag.channels,
                        ),
                    )
                except tinytag.tinytag.TinyTagException:
                    pass

    def _exact_match_recordings(self):
        """Associate recording files with metadata."""
        metadata = self.metadata["sessions"]
        for name in self.recordings:
            if name in metadata:
                self.recordings[name]["metadata"] = metadata[name]

    def _resolve_track_metadata(self, name, tracks):
        """Attempt to resolve a file to the appropriate track-specific
        metadata.

        In the case of two tracks usually one is the interviewer and
        the other is the speaker.  If we don't know which track was
        used to generate an exported file (unfortunately this is the
        case) then we have to assume that it corresponds to the track
        with a Michif speaker as the primary speaker.
        """
        metadata = self.metadata["sessions"]
        people = self.metadata["people"]
        for track in tracks:
            if track not in metadata:
                continue
            speaker = metadata[track]["PrimarySpeaker"]
            if "michif" in people[speaker]["Language"].lower():
                LOGGER.info(
                    "Assuming exported file %s is speaker %s (track %s)",
                    name,
                    speaker,
                    track,
                )
                return track
        return None

    def _map_metadata(self, name, base):
        """Resolve metadata from a recording to a known session."""
        metadata = self.metadata["sessions"]
        LOGGER.info("Matched %s to %s in metadata", name, base)
        self.recordings[name]["metadata"] = metadata[base]
        # Update the "name" as well as it is a key for metadata
        self.recordings[name]["name"] = base
        # do not overwrite a perfect match!
        if base not in self.recordings:
            self.recordings[base] = self.recordings[name]

    def _fuzzy_match_recordings(self):
        """Associate recording files with metadata using approximate matching."""
        metadata = self.metadata["sessions"]
        for name in list(self.recordings.keys()):
            if name in metadata or "metadata" in self.recordings[name]:
                continue
            base = re.sub(r"-(tr\d|elan|crim$|for_export$|olympus)", "", name)
            if base in metadata:
                self._map_metadata(name, base)
                continue
            track = self._resolve_track_metadata(
                name, [f"{name}-tr1", f"{name}-tr2", f"{base}-tr1", f"{base}-tr2"]
            )
            if track is not None:
                self._map_metadata(name, track)
                continue
            approx_name = name.replace("-", "")
            found = False
            for other in metadata:
                approx_other = other.replace("-", "")
                if approx_name == approx_other:
                    self._map_metadata(name, other)
                    found = True
                    break
            if not found:
                LOGGER.warning("Recording %s not found in metadata", name)

    def add_recordings(self, recdir: PathLike):
        """Read recordings and associate with metadata."""
        people = self.metadata["people"]
        self._find_recordings(recdir)
        self._exact_match_recordings()
        self._fuzzy_match_recordings()
        # And find the speakers
        for name in list(self.recordings.keys()):
            if "metadata" in self.recordings[name]:
                speaker = self.recordings[name]["metadata"]["PrimarySpeaker"]
                if speaker in people:
                    self.recordings[name]["speaker"] = people[speaker]
                else:
                    LOGGER.warning(
                        "%s: speaker ID %s not found in metadata", name, speaker
                    )

    def add_annotations(self, topdir: PathLike):
        """Read annotation directories and create file inventory."""
        for root, dirs, files, dir_fd in os.fwalk(topdir, topdown=True):
            annodir = Path(root)
            reldir = annodir.relative_to(topdir)
            if str(reldir) == "Recordings":  # DO NOT WANT
                del dirs[:]
                continue
            eafs = []
            wavs = []
            mp3s = []
            for name in files:
                if name.startswith("."):
                    continue
                base, _ = os.path.splitext(name)
                stat = os.stat(name, dir_fd=dir_fd)
                if ".eaf" in name.lower():
                    with open(annodir / name, "rb") as infh:
                        digest = hashlib.md5()
                        while True:
                            chunk = infh.read(65536)
                            if len(chunk) == 0:
                                break
                            digest.update(chunk)
                    eafs.append(
                        dict(
                            name=name,
                            path=str(reldir / name),
                            mtime=stat.st_mtime,
                            size=stat.st_size,
                            md5=digest.hexdigest(),
                        )
                    )
                elif ".wav" in name.lower():
                    tag = tinytag.TinyTag.get(annodir / name)
                    wavs.append(
                        dict(
                            name=base,
                            path=str(reldir / name),
                            mtime=stat.st_mtime,
                            size=stat.st_size,
                            tag=dict(
                                duration=tag.duration,
                                samplerate=tag.samplerate,
                                channels=tag.channels,
                            ),
                        )
                    )
                elif ".mp3" in name.lower():
                    tag = tinytag.TinyTag.get(annodir / name)
                    mp3s.append(
                        dict(
                            name=base,
                            path=str(reldir / name),
                            mtime=stat.st_mtime,
                            size=stat.st_size,
                            tag=dict(
                                duration=tag.duration,
                                samplerate=tag.samplerate,
                                channels=tag.channels,
                            ),
                        )
                    )
            if not eafs:  # It's of no use to us!
                if mp3s or wavs:
                    LOGGER.error("Directory %s contains audio but no EAFs!", reldir)
                continue
            eafs.sort(key=lambda x: (x["mtime"], -len(x["name"])), reverse=True)
            mp3s.sort(key=lambda x: (x["mtime"], -len(x["name"])), reverse=True)
            wavs.sort(key=lambda x: (x["mtime"], -len(x["name"])), reverse=True)
            self.annodirs[str(reldir)] = dict(eafs=eafs, wavs=wavs, mp3s=mp3s)

    def resolve_annotations(self):  # noqa: C901
        """Resolve annotation files to recordings.

        This does not attempt to decide which annotation file to use
        for a given recording, just finds all the ones that are
        presumed to match.

        Matching is done based on:

        - Filename: if the basename of the EAF file is the same, we
          assume it's an annotation for it.
        - Approximate filename: if the basename of the EAF is a
          substring of the recording name, we will also assume it's an
          annotation for it.

        The presumed recordings' filenames are added to the
        "recordings" key of each value in `self.annodirs`
        """
        bogus_annotations = set()
        people = self.metadata["people"]
        metadata = self.metadata["sessions"]
        for path, files in self.annodirs.items():
            recordings = set()
            for info in files["eafs"]:
                name = info["name"]
                idx = name.lower().index(".eaf")
                base = name[:idx]
                base = re.sub(r"\s+.*$", "", base)
                base = re.sub(r"\(\d+\).*$", "", base)
                base = re.sub(r"-(working|practice)$", "", base, flags=re.I)
                if base in self.recordings:
                    recordings.add(base)
                base1 = f"{base}-tr1"
                if base1 in self.recordings:
                    recordings.add(base1)
                base2 = f"{base}-tr2"
                if base2 in self.recordings:
                    recordings.add(base2)
            if not recordings:
                LOGGER.warning("Could not find original recordings for %s", path)
                if not files["wavs"] and not files["mp3s"]:
                    LOGGER.error(
                        "Could not find *any* recordings for %s, removing", path
                    )
                    bogus_annotations.add(path)
            files["recordings"] = [self.recordings[name] for name in recordings]
            # It really does not matter how we sort them but we must sort them!
            files["recordings"].sort(key=lambda x: x["name"])
            # Do some cursory verification on the audio
            duration = None
            duration_source = None
            for info in files["recordings"]:
                if duration is None:
                    duration = info["tag"]["duration"]
                    duration_source = info["path"]
                delta = abs(info["tag"]["duration"] - duration)
                # Assume that the original recordings must be correct
                if delta > 0.1 and path not in bogus_annotations:
                    LOGGER.error(
                        "recording %s has abnormal duration (%.3f vs %.3f in %s), removing for %s",
                        info["path"],
                        info["tag"]["duration"],
                        duration,
                        duration_source,
                        path,
                    )
                    bogus_annotations.add(path)
            for info in chain(files["wavs"], files["mp3s"]):
                if duration is None:
                    duration = info["tag"]["duration"]
                    duration_source = info["path"]
                delta = abs(info["tag"]["duration"] - duration)
                # Annotation recordings (which we hope we won't use)
                # can just be removed without removing the annotation
                # itself
                if delta > 10.0 and path not in bogus_annotations:
                    LOGGER.warning(
                        "annotation audio %s has abnormal duration (%.3f vs %.3f in %s), removing for %s",
                        info["path"],
                        info["tag"]["duration"],
                        duration,
                        path,
                    )
                    # No metadata, no recording, as far as we're concerned
                    continue
                if info["name"] in metadata:
                    info["metadata"] = metadata[info["name"]]
                # Try again without any extra tags
                cleanname = re.sub(r"-(tr\d|elan|for_export|olympus)", "", info["name"])
                if "metadata" not in info:
                    if cleanname in metadata:
                        info["metadata"] = metadata[cleanname]
                        LOGGER.info(
                            "Mapped %s to metadata for %s", info["name"], cleanname
                        )
                # Try to map it to a specific track number
                if "metadata" not in info:
                    track = self._resolve_track_metadata(
                        cleanname,
                        [
                            f"{info['name']}-tr1",
                            f"{info['name']}-tr2",
                            f"{cleanname}-tr1",
                            f"{cleanname}-tr2",
                        ],
                    )
                    if track is not None:
                        info["metadata"] = metadata[track]
                        LOGGER.info("Mapped %s to metadata for %s", info["name"], track)
                # Resolve speaker info
                if "metadata" in info:
                    speaker = info["metadata"]["PrimarySpeaker"]
                    if speaker in people:
                        info["speaker"] = people[speaker]
                    else:
                        LOGGER.warning(
                            "%s: speaker %s not found in metadata",
                            info["name"],
                            speaker,
                        )

        for bogus in bogus_annotations:
            del self.annodirs[bogus]


def main():
    parser = make_argparse()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    with open(args.metadata) as infh:
        metadata = json.load(infh)
    app = ElanUntangler(metadata)
    app.add_recordings(args.recdir)
    app.add_annotations(args.annodir)
    app.resolve_annotations()
    print(json.dumps(sorted(app.annodirs.items()), indent=2))


if __name__ == "__main__":
    main()
