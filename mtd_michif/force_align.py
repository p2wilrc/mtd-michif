#!/usr/bin/env python3

"""Force-align audio clips to generate readalongs and find problem annotations."""

import argparse
import csv
import json
import logging
import re
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

import g2p  # type: ignore
from soundswallower import Decoder, get_model_path
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map

from mtd_michif.dictionary import Dictionary

LOGGER = logging.getLogger("force-align")


def make_argparse():
    """Make the argparse."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dictionary", help="JSON file with final dictionary (including audio)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to write dictionary with added segmentations",
    )
    parser.add_argument(
        "-b",
        "--problem-annotations",
        type=Path,
        help="Path to write CSV of bad annotations.",
    )
    return parser


def align_clip(text, clip):
    global decoder
    audio = subprocess.run(
        ["sox", "-V1", "-G", clip.path, "-t", "raw", "-r", "8000", "-"],
        stdout=subprocess.PIPE,
        check=True,
    )
    decoder.set_align_text(text)
    decoder.start_utt()
    decoder.process_raw(audio.stdout, full_utt=True)
    decoder.end_utt()
    return decoder.dumps()


def force_align(dictionary):  # noqa: C901
    transducer = g2p.make_g2p("crg-tmd", "eng-arpabet", tokenize=False)
    tokenizer = g2p.make_tokenizer("crg-tmd")

    # FIXME: this is very JavaScripty
    entries = []
    orig_texts = []
    texts = []
    clips = []
    prons = {}

    def emit_text(michif, audio, entry):
        # Must match the "tokenization" done in the web front-end!
        # (word-modal.component.ts for the moment but should be
        # refactored to a service)
        words = re.split(r"[\s.,:;()]+", michif.strip().lower())
        for word in words:
            if not word:
                continue
            if word in prons:
                continue
            phones = []
            for token in tokenizer.tokenize_text(word):
                if token["is_word"]:
                    tphones = str(transducer(token["text"]))
                    if tphones:  # Skip bogus tokens
                        phones.append(tphones)
            pron = re.sub(r"\s+", " ", " ".join(phones).strip())
            if not pron:
                pron = "SIL"
            prons[word] = pron
        for clip in audio:
            orig_texts.append(michif)
            texts.append(" ".join(words).strip())
            clips.append(clip)
            entries.append(entry)

    LOGGER.info("Creating pronunciations...")
    for entry in tqdm(dictionary.entries.values()):
        emit_text(entry.michif, entry.audio, entry)
        for example in entry.examples:
            emit_text(example.michif, example.audio, entry)

    LOGGER.info("Aligning audio...")
    with NamedTemporaryFile("wt", suffix=".dict") as tempfh:
        for word in sorted(prons):
            print("\t".join((word, prons[word])), file=tempfh)
        tempfh.flush()

        global decoder
        decoder = Decoder(
            hmm=get_model_path("en-us"),
            dict=tempfh.name,
            samprate=8000,
            loglevel="FATAL",
        )  # Silence!

    problem_annotations = []
    for orig_text, text, clip, entry, result_text in zip(
        orig_texts,
        texts,
        clips,
        entries,
        process_map(align_clip, texts, clips, chunksize=16),
    ):
        result = json.loads(result_text)

        def is_word(seg):
            word = seg["t"]
            return word and word[0] != "<" and word[0] != "["

        starts = [round(w["b"] * 100) for w in result["w"] if is_word(w)]
        # Omit the first word as we will always show it!
        if len(starts) > 1:
            clip.starts = starts[1:]
        elif len(starts) == 0:
            # Oops, this failed
            problem_annotations.append((orig_text, clip, entry))
    return problem_annotations


def save_problem_annotations(problem_annotations: list[tuple], path: Path):
    with open(path, "wt") as outfh:
        writer = csv.DictWriter(
            outfh, ["ID", "Text", "Session", "Start", "End", "MP3", "Details"]
        )
        writer.writeheader()
        for michif, clip, entry in problem_annotations:
            # Session ID, possibly a track number (ignored), start, end
            # FIXME: we should have used underscores or spaces or something
            m = re.match(
                r"(.*-\d\d\d\d-?\d\d-?\d\d(?:-\d\d)?).*-(\d+\.\d+)-(\d+\.\d+)\.\w+$",
                clip.path.name,
            )
            assert m is not None
            session, start, end = m.groups()
            dstart = str(round(float(start) * 1000))
            dend = str(round(float(end) * 1000))
            writer.writerow(
                {
                    "ID": entry.id,
                    "Text": michif,
                    "Session": session,
                    "Start": dstart,
                    "End": dend,
                    "MP3": clip.path,
                    "Details": "Alignment failed",
                }
            )


def main():
    parser = make_argparse()
    args = parser.parse_args()
    dictionary = Dictionary.load_json(args.dictionary)
    problem_annotations = force_align(dictionary)

    if args.output:
        dictionary.save_json(args.output)
    if args.problem_annotations:
        save_problem_annotations(problem_annotations, args.problem_annotations)
    else:
        for michif, clip, entry in problem_annotations:
            print(f"{entry.id} ({entry.english}): {michif} ({clip.path.name})")


if __name__ == "__main__":
    main()
