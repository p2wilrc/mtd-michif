"""
Functions for parsing the text format of the Laverdure dictionary.
"""

import fileinput
import json
import logging
import re
from pathlib import Path
from typing import Optional

import pysbd  # type: ignore
from pydantic import BaseModel, Field

LOGGER = logging.getLogger("parse-entries")
SEGMENTER = pysbd.Segmenter(clean=True)
MODEL_PATH = Path(__file__).parent / "models" / "ocr-hyphenation.json"
with open(MODEL_PATH, "rt") as infh:
    SPLITS = json.load(infh)


class ParsedEntry(BaseModel):
    """Single entry in the TMD dictionary (could be multiple on a line with different senses)"""

    english: str = Field(description="English headword")
    michif: list[str] = Field(description="Michif translations")
    clarification: Optional[str] = Field(
        None, description="English description of specific sense"
    )
    examples: list[str] = Field(default=[], description="Example sentences")


def parse_multiple(headword: str, segs: list[str]) -> list[ParsedEntry]:
    """Parse multiple senses of a headword into separate entries."""
    prev_start = 0
    entries: list[ParsedEntry] = []
    # FIXME: sbd's "intuitions" are sometimes wrong, we should
    # actually just split on \d+\) like Jacob's code did
    for idx, seg in enumerate(segs):
        m = re.match(r"\d+\)\s*(.*)", seg)
        if m:
            if idx != 0:
                entries.append(
                    parse_subdefinition(
                        headword, segs[prev_start], segs[prev_start + 1 : idx]
                    )
                )
            segs[idx] = m.group(1)
            prev_start = idx
    entries.append(
        parse_subdefinition(headword, segs[prev_start], segs[prev_start + 1 :])
    )
    return entries


def parse_subdefinition(headword: str, definition: str, segs: list[str]) -> ParsedEntry:
    """Parse one of multiple senses of a headword (which might in turn
    have embedded senses of definitions)."""
    sense, sep, def2 = definition.partition("—")
    if sep == "":
        return parse_definition(headword, None, definition, segs)
    else:
        return parse_definition(headword, sense, def2, segs)


def parse_definition(
    headword: str, sense: Optional[str], definition: str, segs: list[str]
) -> ParsedEntry:
    """Parse definition into definition and example text, creating
    multiple entries in the case where there are embedded senses per
    definition."""
    # Try to partition into words + example three different ways
    words, sep, example = definition.partition(";")
    if sep == "":
        words, sep, example = definition.partition("—")
    if sep == "":
        words, sep, example = definition.partition(":")
    # A leading dash means trouble
    if segs and segs[0].startswith("—"):
        # The "word" was actually a sense
        if words:
            sense = words
        # The first segment was actually (at least partly) the word
        words = segs[0][1:]
        before, sep, after = words.partition(";")
        if sep:
            words = before
            segs[0] = after
        else:
            segs = segs[1:]
    # Check if we split the word somewhere
    if example == "":
        new_start = 0
        # Glom on comma-separated stuff that pysbd split by accident
        for idx, seg in enumerate(segs):
            if seg.startswith(",") and ";" not in seg:
                words += seg
                new_start = idx + 1
        segs = segs[new_start:]
        # Scan forward to see if we have an example separator
        for idx, seg in enumerate(segs):
            before, sep, after = seg.partition(";")
            if sep == "":
                before, sep, after = definition.partition("—")
            if sep == "":
                before, sep, after = definition.partition(":")
            if sep:
                words += " "
                words += " ".join(segs[:idx])
                words += " "
                words += before
                segs[idx] = after
                new_start = idx
                break
        segs = segs[new_start:]
    examples: list[str] = []
    if example:
        examples.append(example)
    # Now any remaining segments should belong to the examples
    examples.extend(segs)
    # Make an entry (note that there may be embedded senses in the Michif, we have to deal with these later, after example matching)
    michif = [w for w in (ww.strip(". ") for ww in words.split(",")) if w]
    entry = ParsedEntry(
        english=headword.strip(),
        michif=michif,
        clarification=sense,
        examples=examples,
    )
    cleanup_entry(entry)
    return entry


def cleanup_line(line: str):
    """Apply various clean-ups to input text."""
    # Hyphenation that was transformed into space by bogus postprocessing
    headword, _, definitions = line.partition("—")
    if definitions:
        if headword in SPLITS:
            LOGGER.info("Found %s in hyphenation table", headword)
            for split in SPLITS[headword]:
                joined = split.replace(" ", "")
                LOGGER.info("Replacing %s with %s", split, joined)
                line = line.replace(split, joined)
                LOGGER.info("Now %s", line)
    # Hyphenation+newline (this seems too general, but it actually works)
    line = re.sub(r"(\w)- (\w)", r"\1\2", line)
    # Stray OCR spaces (many others exist as well...)
    line = line.replace(" ing", "ing")
    # More OCR artifacts
    line = re.sub(r"[1I]['’]([aeiouAEIOU])", r"l’\1", line)
    line = re.sub(r"\bI(a|ee|i)\b", r"l\1", line)
    # Chapter titles that got tacked onto examples by OCR
    line = re.sub(r"\s+[A-Z]\s*$", "", line)

    # Semicolons at end of subdefinition
    line = re.sub(r"; (\d\))", r". \1", line)
    # Extraneous dashes
    line = re.sub(r"—([2-9]\))", r" \1", line)
    # Missing spaces after quoted punctuation (confuses pysbd)
    line = re.sub(r"([.!?]’)(\w)", r"\1 \2", line)
    # Extraneous periods at end of line
    line = re.sub(r"\.? \.$", ".", line)

    return line


def cleanup_entry(entry: ParsedEntry):  # noqa: C901
    """Apply textual clean-up and some special-case rules to fix up examples."""
    if not entry.examples:
        return
    # Examples that are actually just clarifications
    next_examples = []
    for example in entry.examples:
        if m := re.match(r"\((.*)\)\.?\s*$", example):
            entry.clarification = m.group(1)
        else:
            next_examples.append(example)
    entry.examples = next_examples
    # Clean up example text
    entry.examples = [x.strip() for x in entry.examples]
    # Tack interjections onto the following sentence
    for idx, sent in enumerate(entry.examples[:-1]):
        nwords = sent.count(" ") + 1
        nextsent = entry.examples[idx + 1]
        nextwords = nextsent.count(" ") + 1
        if sent.endswith("!"):
            if (nwords == 1 and nextwords > 1) or (
                nwords == 2
                and len(sent) < 15  # hack
                and not sent.startswith("Not")  # hack
                and not entry.examples[idx + 1].endswith("!")
            ):
                entry.examples[idx] = " ".join((sent, nextsent))
                entry.examples[idx + 1] = ""
    # Delete deletions
    entry.examples = [x for x in entry.examples if x]
    # FIXME: Refactor all these things below!
    # FIXME: Was it really worth using pysbd? We have to second-guess it a lot...
    # Override pysbd's intuitions about acronyms
    next_examples = []
    for sent in entry.examples:
        ins = []
        while True:
            m = re.search(r"[A-Z]\.[A-Z]\. [A-Z]", sent)
            if not m:
                break
            start, end = m.span()
            ins.append(sent[: end - 2])
            sent = sent[end - 1 :]
        ins.append(sent)
        next_examples.extend(ins)
    entry.examples = next_examples
    # Split on adjacent quoted words
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition("’ ‘")
            if sep:
                next_examples.append(before + "’")
                after = "’" + after
            else:
                next_examples.append(before)
                break
    entry.examples = next_examples
    # WTF pysbd, 'I said WTF.' Will split but not...
    # WTF pysbd, ‘I said WTF.’ What the h*ck?
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition(".’ ")
            if sep:
                next_examples.append(before + ".’")
            else:
                next_examples.append(before)
                break
    entry.examples = next_examples
    # OMFG!!!!
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition("det. ")
            if sep:
                next_examples.append(before + "det.")
            else:
                next_examples.append(before)
                break
    entry.examples = next_examples
    # FIXME: refactor this crap or ditch @#$@#$ pysbd
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition("me. ")
            if sep:
                next_examples.append(before + "me.")
            else:
                next_examples.append(before)
                break
    entry.examples = next_examples
    # ARGH!!!
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition(".) ")
            if sep:
                next_examples.append(before + ".)")
            else:
                next_examples.append(before)
                break
    entry.examples = next_examples
    # Split on dashes
    next_examples = []
    for sent in entry.examples:
        after = sent
        while after:
            before, sep, after = after.partition(" — ")
            next_examples.append(before)
            if not sep:
                break
    entry.examples = next_examples


def parse_line(line: str) -> list[ParsedEntry]:
    """Parse a line into one or more dictionary entries."""
    line = cleanup_line(line)
    segs = SEGMENTER.segment(line)
    headword, sep, definition = segs[0].partition("—")
    # Senses attached to headwords
    m = re.match(r"(.*\S)\s*\(([^\)]+)\)\s*$", headword)
    if m:
        headword, sense = m.groups()
    else:
        sense = None
    m = re.match(r"\(?([^\)]+)\)?—(.*)", definition)
    if m:
        sense, definition = m.groups()
    m = re.match(r"\(([^\)]+)\)\s+(.*)", definition)
    if m:
        sense, definition = m.groups()
    if definition.startswith("1)"):
        segs[0] = definition
        return parse_multiple(headword, segs)
    if len(segs) > 1 and segs[1].startswith("1)"):
        return parse_multiple(headword, segs[1:])
    return [parse_definition(headword, sense, definition, segs[1:])]


def main():
    for spam in fileinput.input():
        if spam.startswith("#"):
            continue
        entries = parse_line(spam)
        for entry in entries:
            print(entry.json(exclude_defaults=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
