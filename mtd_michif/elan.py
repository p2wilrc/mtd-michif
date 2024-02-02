"""
Functions for getting annotations from ELAN files
"""

import csv
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from os import PathLike
from pathlib import Path
from typing import Iterable, Literal, NamedTuple, Optional, TextIO, Union

import Levenshtein
from pympi.Elan import Eaf  # type: ignore

from .dictionary import Dictionary
from .textnorm import normalize_english, normalize_michif
from .types import Entry, Example

LOOSE_PARENTHETICALS = re.compile(r"\((.*?)\)\w*\.?$")
EXTRA_INFO = re.compile(r"\s-.*")
BAD_SUBDEF = re.compile(r"[-\(]?\d\)")
LOGGER = logging.getLogger("elan")


def clean_headword(english: Optional[str]) -> tuple[str, str]:
    """Get headword and possible sense "clarification"."""
    if english is None:
        return "", ""
    headword = EXTRA_INFO.sub("", english)
    sense = ""
    if m := LOOSE_PARENTHETICALS.search(headword.strip()):
        if m.start() > 0:
            sense = m.group(1)
            headword = (headword[: m.start()] + headword[m.end() :]).strip()
    before, sep, after = headword.partition("—")
    if sep:
        headword = before
    if m := BAD_SUBDEF.search(headword):
        headword = headword[: m.start()].strip()
    return headword, sense


def clean_definition(michif: Optional[str]) -> str:
    """Remove alternate spellings and things."""
    if michif is None:
        return ""
    if m := LOOSE_PARENTHETICALS.search(michif):
        if m.start() > 0:
            LOGGER.info("Removing %s from %s", m.group(0), michif)
            michif = (michif[: m.start()] + michif[m.end() :]).strip()
    return michif


def parse_time(timestr: str) -> int:
    """Parse time string to milliseconds"""
    m = re.match(r"(?:(\d+):)?(\d+):(\d+)\.(\d+)", timestr)
    if m is None:
        raise ValueError("Invalid time string %s" % timestr)
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    csecs = int(m.group(4))
    return csecs * 10 + seconds * 1000 + minutes * 60000 + hours * 3600000


def format_time(milliseconds: Union[float, int]) -> str:
    """Format a timestamp nicely, for some reason there is no function in
    the Python standard library to do this!  Batteries, what
    batteries?
    """
    seconds = milliseconds * 0.001
    minutes = seconds // 60
    seconds = seconds - minutes * 60
    csecs = round((seconds - int(seconds)) * 100)
    if minutes > 60:
        hours = minutes // 60
        minutes -= hours * 60
        return "%d:%02d:%02d.%02d" % (hours, minutes, int(seconds), csecs)
    return "%d:%02d.%02d" % (minutes, int(seconds), csecs)


@dataclass(slots=True)
class Span:
    """Span of audio with associated annotations."""

    eaf_path: Path
    start: int
    end: int
    annotation_id: str
    annotations: dict[str, str] = field(default_factory=dict)

    @property
    def export(self) -> bool:
        return self.annotations.get("tmd-export", "Don't Export") == "Export"

    @export.setter
    def export(self, value: bool):
        self.annotations["tmd-export"] = "Export" if value else "Don't Export"

    @property
    def annotation_type(self) -> Optional[str]:
        return self.annotations.get("tmd-annotation-type", None)

    @annotation_type.setter
    def annotation_type(self, value: str):
        self.annotations["tmd-annotation-type"] = value

    @property
    def annotation_base(self) -> Optional[str]:
        annotation_type = self.annotation_type
        if annotation_type is None:
            return None
        base, _, _ = annotation_type.partition("-")
        return base

    @annotation_base.setter
    def annotation_base(self, value: str):
        annotation_type = self.annotation_type
        if annotation_type is None:
            self.annotation_type = value
            return
        base, _, cont = annotation_type.partition("-")
        if cont:
            self.annotation_type = f"{value}-{cont}"
        else:
            self.annotation_type = value

    @property
    def mispronunciation(self) -> bool:
        annotation_type = self.annotation_type
        if annotation_type is None:
            return False
        base, _, cont = annotation_type.partition("-")
        return cont == "Mispronunciation"

    @property
    def continued(self) -> bool:
        annotation_type = self.annotation_type
        if annotation_type is None:
            return False
        base, _, cont = annotation_type.partition("-")
        return cont == "Continued"

    @continued.setter
    def continued(self, value: bool):
        annotation_type = self.annotation_type
        if annotation_type is None:
            raise ValueError("No annotation type found, cannot set continued")
        if self.mispronunciation:
            raise ValueError("Cannot set continued for a mispronunciation")
        base, _, cont = annotation_type.partition("-")
        if base not in ("Headword", "Example"):
            raise ValueError("Not a headword or example, cannot set continued")
        if value:
            self.annotation_type = f"{base}-Continued"
        else:
            self.annotation_type = base

    @property
    def headword(self):
        return self.annotations.get("tmd-headword", None)

    @headword.setter
    def headword(self, value):
        self.annotations["tmd-headword"] = value

    @property
    def original_english_text(self) -> Optional[str]:
        return self.annotations.get("tmd-english-text", None)

    @original_english_text.setter
    def original_english_text(self, value: str):
        self.annotations["tmd-english-text"] = value

    @property
    def original_michif_text(self) -> Optional[str]:
        return self.annotations.get("tmd-michif-text", None)

    @original_michif_text.setter
    def original_michif_text(self, value: str):
        self.annotations["tmd-michif-text"] = value

    def __lt__(self, other):
        return self.start < other.start

    def __str__(self):
        return "%s:%s:%s:%s:%d:%d:%s:%s" % (
            repr(self.headword),
            self.annotation_type,
            self.eaf_path.name,
            self.annotation_id,
            self.start,
            self.end,
            repr(self.original_english_text),
            repr(self.original_michif_text),
        )


class SpanExtractor:
    eaf_path: Path
    eaf: Eaf
    text_tier: str
    spans: dict[str, Span]

    def __init__(self, eaf_path: PathLike):
        """Extract Span objects from an EAF file."""
        self.eaf_path = Path(eaf_path)
        self.eaf = eaf = Eaf(eaf_path)
        self.spans = {}
        # The tier with linguistic type "text" contains the timeslots for each word/phrase
        # and all other tiers refer to its annotations
        text_tiers = eaf.get_tier_ids_for_linguistic_type("text")
        # Sometimes the linguistic type is wrong, so look for a tier with aligned annotations
        if len(text_tiers) == 0:
            for tier in eaf.tiers:
                if eaf.tiers[tier][0]:
                    LOGGER.warning(
                        "No tiers of type 'text', using %s as it has aligned annotations",
                        tier,
                    )
                    text_tiers = [tier]
                    break
        if len(text_tiers) > 1:
            raise RuntimeError(
                "EAF should have exactly one 'text' tier, not: %s" % text_tiers
            )
        else:
            (self.text_tier,) = text_tiers
        # Construct spans from the aligned annotations in the text tier
        self.aligned_annotations, _, self.attributes, _ = eaf.tiers[self.text_tier]
        for annotation_id, (start, end, _, _) in self.aligned_annotations.items():
            self.spans[annotation_id] = Span(
                eaf_path=self.eaf_path,
                start=eaf.timeslots[start],
                end=eaf.timeslots[end],
                annotation_id=annotation_id,
            )
        # Attach child reference annotations to each span (arguably, pympi should do this for us)
        for tier_id, (
            _,
            reference_annotations,
            attributes,
            _,
        ) in eaf.tiers.items():
            if not reference_annotations:
                continue
            linguistic_type = attributes["LINGUISTIC_TYPE_REF"]
            for annotation_id, (
                reference_id,
                value,
                _,
                _,
            ) in reference_annotations.items():
                span = self.spans[reference_id]
                assert linguistic_type not in span.annotations
                span.annotations[linguistic_type] = value

    def __iter__(self):
        return iter(sorted(self.spans.values(), key=lambda x: x.start))

    def update_eaf(self):
        """Update annotations in Eaf object from spans."""
        for tier_id, (
            _,
            reference_annotations,
            attributes,
            _,
        ) in self.eaf.tiers.items():
            if not reference_annotations:
                continue
            linguistic_type = attributes["LINGUISTIC_TYPE_REF"]
            unseen_spans = set(self.spans.keys())
            for annotation_id in reference_annotations:
                (reference_id, value, alouette, farfadet) = reference_annotations[
                    annotation_id
                ]
                span = self.spans[reference_id]
                unseen_spans.remove(reference_id)
                reference_annotations[annotation_id] = (
                    reference_id,
                    span.annotations[linguistic_type],
                    alouette,
                    farfadet,
                )
            # A lot of annotations are just missing, find the ones we
            # updated to not be missing and create them
            updated_unseen_spans = []
            for reference_id in unseen_spans:
                span = self.spans[reference_id]
                # FIXME: not using None here because we convert it to
                # "" elsewhere... need to be consistent about this
                if span.annotations.get(linguistic_type):
                    updated_unseen_spans.append(span)
            if updated_unseen_spans:
                LOGGER.info(
                    "Unseen but updated spans in %s(%s):", tier_id, linguistic_type
                )
                for span in updated_unseen_spans:
                    LOGGER.info("\t%s", span)
                    # Pympi's method is basically useless, don't use it
                    annotation_id = self.eaf.generate_annotation_id()
                    reference_annotations[annotation_id] = (
                        span.annotation_id,
                        span.annotations[linguistic_type],
                        None,
                        None,
                    )


class MatchType(IntEnum):
    """Type of match - note that these are ordered by preference"""

    EXACT = 0
    MICHIF = 1
    ENGLISH = 2


# Not an Enum, for Reasons. Such TypeScript, so wow.
MatchedBy = Literal["Headword", "Example"]


class SpanMatch(NamedTuple):
    type: MatchType
    by: MatchedBy
    score: int
    entry: Entry
    example: Optional[Example] = None


class AnnotationMatcher:
    def __init__(self, dictionary: Dictionary, max_distance: int = 3):
        self.english_example_index: defaultdict[
            str, set[tuple[Entry, Example]]
        ] = defaultdict(set)
        self.michif_example_index: defaultdict[
            str, set[tuple[Entry, Example]]
        ] = defaultdict(set)
        self.english_index: defaultdict[str, set[Entry]] = defaultdict(set)
        self.michif_index: defaultdict[str, set[Entry]] = defaultdict(set)
        self.max_distance = max_distance
        self.bad_annotations: list[Span] = []
        for entry in dictionary.entries.values():
            michif = clean_definition(entry.michif)
            overcrg = normalize_michif(michif)
            if overcrg:
                self.michif_index[overcrg].add(entry)
            overeng = normalize_english(entry.english)
            if overeng:
                self.english_index[overeng].add(entry)
            for example in entry.examples:
                overeng = normalize_english(example.english)
                if overeng:
                    self.english_example_index[overeng].add(
                        (
                            entry,
                            example,
                        )
                    )
                michif = clean_definition(example.michif)
                overcrg = normalize_michif(michif)
                if overcrg:
                    self.michif_example_index[overcrg].add(
                        (
                            entry,
                            example,
                        )
                    )

    def score(self, norm_michif: str, ref_michif: str) -> int:
        if norm_michif == "":  # NO MATCH!
            return self.max_distance + 1
        return Levenshtein.distance(
            norm_michif, normalize_michif(ref_michif), score_cutoff=self.max_distance
        )

    def match_headwords(self, span: Span) -> Iterable[tuple[Entry, MatchType]]:
        # First *get* the headword (and sense)
        english, sense = clean_headword(span.headword)
        # Apply normalizations for OCR and other issues
        norm_headword = normalize_english(english)
        # Try to find something
        english_matches = self.english_index[norm_headword]
        # Get Michif definition
        michif = clean_definition(span.original_michif_text)
        # Apply normalizations for OCR and other issues (these are
        # different for Michif because of language-specific things,
        # e.g. articles, preverbs, orthography)
        norm_michif = normalize_michif(michif)
        # Try to find something
        michif_matches = self.michif_index[norm_michif]

        exact_matches = english_matches & michif_matches
        seen_matches: set[Entry] = set()
        if len(exact_matches) == 1:
            match = exact_matches.pop()
            seen_matches.add(match)
            yield match, MatchType.EXACT
        # Extra step here to prefer exact match with the same sense
        # (probably irrelevant since the Michif would be different
        # otherwise!)
        if len(exact_matches) > 1:
            sorted_matches = sorted(exact_matches)
            for match in sorted_matches:
                if sense and match.clarification == sense:
                    if match not in seen_matches:
                        seen_matches.add(match)
                        yield match, MatchType.EXACT
            for match in sorted_matches:
                if match not in seen_matches:
                    seen_matches.add(match)
                    yield match, MatchType.EXACT
        for match in sorted(michif_matches):
            if match not in seen_matches:
                seen_matches.add(match)
                yield match, MatchType.MICHIF
        for match in sorted(english_matches):
            if match not in seen_matches:
                seen_matches.add(match)
                yield match, MatchType.ENGLISH

    def match_examples(self, span: Span) -> Iterable[tuple[Entry, Example, MatchType]]:
        # See above, basically the same thing except we look in a
        # different index (and don't need to deal with
        # "clarifications")
        norm_english = normalize_english(span.original_english_text)
        english_matches = self.english_example_index[norm_english]
        norm_michif = normalize_michif(span.original_michif_text)
        michif_matches = self.michif_example_index[norm_michif]
        exact_matches = english_matches & michif_matches
        seen_matches: set[tuple[Entry, Example]] = set()
        for entry, example in sorted(exact_matches):
            if (entry, example) not in seen_matches:
                seen_matches.add((entry, example))
                yield entry, example, MatchType.EXACT
        for entry, example in sorted(michif_matches):
            if (entry, example) not in seen_matches:
                seen_matches.add((entry, example))
                yield entry, example, MatchType.MICHIF
        for entry, example in sorted(english_matches):
            if (entry, example) not in seen_matches:
                seen_matches.add((entry, example))
                yield entry, example, MatchType.ENGLISH

    def match_span(
        self,
        span: Span,
    ) -> list[SpanMatch]:
        """Return list of matches sorted by MatchType, MatchedBy (matching
        span.annotation_base), Levenshtein distance of Michif text."""
        headword_matches = self.match_headwords(span)
        example_matches = self.match_examples(span)
        matches: list[SpanMatch] = []
        # Doing this twice (it's cheap though)
        norm_michif = normalize_michif(clean_definition(span.original_michif_text))
        for entry, match_type in headword_matches:
            # Doing this thrice (it's cheap though)
            score = self.score(norm_michif, clean_definition(entry.michif))
            if score <= self.max_distance:
                matches.append(SpanMatch(match_type, "Headword", score, entry, None))
        for entry, example, match_type in example_matches:
            score = self.score(norm_michif, example.michif)
            if score <= self.max_distance:
                matches.append(SpanMatch(match_type, "Example", score, entry, example))
        # Sort on match type, annotation type, edit distance, text
        return sorted(
            matches, key=lambda m: (m[0], m[1] != span.annotation_base, m[2], m[3])
        )

    def group_spans(self, spans: list[Span]) -> list[tuple[list[Span], str]]:
        """Group spans presumed to correspond to a particular dictionary item
        (headword or example) into one or more subsequences presumed
        to be instances of that item.  Keep track of possible problems
        so we can repair and/or flag for review.

        This is messy work because annotators did ... a lot of things.
        And we need to rely on the annotator comments to decipher what
        they did in the case of "chopped and spliced" audio.  We
        *only* allow this when it's fairly explicit, because
        apparently annotators also annotate different versions of the
        *same* word/example with the same syntax and not in a
        consistent way.  The reason we do all this here instead of
        just fixing the EAF files is that when the pieces are out of
        order it is impossible to fix the EAFs in a way to get the
        correct result (except perhaps by adding another annotation
        tier to make this explicit, which is even more work).
        """
        groups: list[tuple[list[Span], str]] = []
        current_spans: list[tuple[int, Span]] = []
        warnings: list[str] = []
        span_total = len(current_spans)
        first_span_idx = span_idx = 0

        def new_group():
            if len(current_spans) != span_total:
                LOGGER.warning(
                    "Expected %d spans from annotations but got %d",
                    span_total,
                    len(current_spans),
                )
                add_warning(
                    "Expected %d spans from annotations but got %d"
                    % (
                        span_total,
                        len(current_spans),
                    )
                )
            current_spans.sort()
            groups.append(([s[1] for s in current_spans], ",".join(warnings)))
            del current_spans[:]
            del warnings[:]

        def add_warning(warning: str):
            warnings.append(warning)

        for span in spans:
            comment = span.annotations.get("tmd-annotator-comment", "")
            m = re.match(r".*\b(?:pt\.?|part)\D*(\d+)/(\d+)", comment, re.I)
            if m is None:
                m = re.match(r".*(\d+)/(\d+)\D*\bpart", comment, re.I)
            if m:
                span_idx = int(m.group(1))
                new_span_total = int(m.group(2))
                idx_text = " (%d/%d)" % (span_idx, new_span_total)
            else:
                span_idx = len(current_spans) + 1 if span.continued else 1
                new_span_total = None
                idx_text = ""

            if span.continued:
                if len(current_spans) == 0:
                    # Only warn if we don't have an explicitly marked ordering
                    if span_idx == 1:
                        LOGGER.warning(
                            "Continued with no initial span%s: %s:%s",
                            idx_text,
                            span,
                            comment,
                        )
                        add_warning("Continued with no initial span")
                    first_span_idx = span_idx
                else:
                    LOGGER.info("Continued span%s: %s", idx_text, span)
            elif idx_text and span_idx < first_span_idx:
                # Handle specific case of explicitly marked 1/3 after 2/3
                LOGGER.info("Out-of-order span%s: %s:%s", idx_text, span, comment)
            else:
                if current_spans:
                    new_group()
                if span_idx != 1:
                    LOGGER.warning(
                        "Out-of-order initial span%s: %s:%s", idx_text, span, comment
                    )
                    add_warning("Out-of-order initial span (according to comment)")
                else:
                    LOGGER.info("Initial span%s: %s:%s", idx_text, span, comment)
                first_span_idx = span_idx

            current_spans.append((span_idx, span))
            if new_span_total is not None:
                span_total = new_span_total
            else:
                span_total = len(current_spans)
        if current_spans:
            new_group()
        return groups

    def write_bad_annotations(self, outfh: TextIO):
        writer = csv.DictWriter(outfh, ["EAF", "RefID", "Text", "Start", "End"])
        writer.writeheader()
        for span in self.bad_annotations:
            message = ":".join(
                (
                    str(span.annotation_type),
                    str(span.headword),
                    str(span.original_english_text),
                    str(span.original_michif_text),
                )
            )
            writer.writerow(
                {
                    "EAF": span.eaf_path.name,
                    "RefID": span.annotation_id,
                    "Text": message,
                    "Start": span.start,
                    "End": span.end,
                }
            )
