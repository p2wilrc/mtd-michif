"""
Functions for matching words to examples in Laverdure definitions.
"""

import fileinput
import itertools
import logging
import re
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from mtd_michif.language_id import language_id
from mtd_michif.parse_entries import ParsedEntry
from mtd_michif.pydantic_models import Entry, Example

LOGGER = logging.getLogger("extract-examples")


def levenshtein(s1, s2):
    """Small and clever implementation of edit distance between two
    sequences."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def score_example(word, example):
    """Score an example using edit distance (FIXME: should use morphology)"""
    best_score = len(word)
    for i in range(len(example) - len(word) + 1):
        target = example[i : i + len(word)]
        score = levenshtein(word.lower(), target.lower())
        if score < best_score:
            best_score = score

    return best_score


def split_first_with_comma(examples: list[str]) -> list[str]:
    """In some cases the first example is split with a comma."""
    possible_examples = examples[0].split(",")
    if len(possible_examples) == 2:
        label0, _ = language_id(possible_examples[0])
        label1, _ = language_id(possible_examples[1])
        if label0 != label1:
            return [x.strip() for x in possible_examples] + examples[1:]
    return examples


class ExampleGroup(BaseModel):
    """Pair of lists of examples grouped by language.  Note that the
    fields here *must* match the language names coming from the
    classifier, which is why they are 'eng' and 'crg', not 'english'
    and 'michif'.
    """

    eng: list[str] = Field(default=[], description="Sequence of English sentences")
    crg: list[str] = Field(default=[], description="Sequence of Michif sentences")


def group_examples(examples: list[str]) -> list[ExampleGroup]:
    """Pair subsequences by language."""
    examples = split_first_with_comma(examples)
    classed = [(language_id(x)[0], x) for x in examples]
    grouped = [
        (lang, [x[1] for x in sents])
        for lang, sents in itertools.groupby(classed, lambda x: x[0])
    ]
    paired = [
        ExampleGroup.model_validate({l1: s1, l2: s2})
        for ((l1, s1), (l2, s2)) in zip(grouped[::2], grouped[1::2])
    ]
    if len(grouped) % 2:
        lang, sent = grouped[-1]
        paired.append(ExampleGroup.model_validate({lang: sent}))
    return paired


def spread_examples(example_groups: list[ExampleGroup]) -> list[Example]:
    """Spread/split example groups with multiple crg for one eng, yielding
    paired eng/crg examples."""
    examples = []
    for eg in example_groups:
        # print([(lang, len(ex[lang])) for lang in ex], ex)
        if not eg.eng or not eg.crg or len(eg.eng) == len(eg.crg):
            examples.append(Example(english=" ".join(eg.eng), michif=" ".join(eg.crg)))
        elif len(eg.eng) == 1:
            if ";" in eg.eng[0]:  # FIXME: special case hack
                examples.append(Example(english=eg.eng[0], michif=" ".join(eg.crg)))
            else:
                examples.extend(
                    Example(english=eg.eng[0], michif=crg) for crg in eg.crg
                )
        elif len(eg.crg) > len(eg.eng) and len(eg.crg) % len(eg.eng) == 0:
            englen = len(eg.eng)
            examples.extend(
                Example(
                    english=" ".join(eg.eng),
                    michif=" ".join(eg.crg[jdx : jdx + englen]),
                )
                for jdx in range(0, len(eg.crg), englen)
            )
        else:
            examples.append(Example(english=" ".join(eg.eng), michif=" ".join(eg.crg)))
    return examples


def find_sense(word: str) -> tuple[str, Optional[str]]:
    """Find embedded senses in definitions"""
    m = re.match(r"(.*)\s+\(([^\)]+)\)$", word)
    if m:
        return (m.group(1), m.group(2))
    return (word, None)


def score_examples(eng: str, crg: str, examples: list[Example]) -> list[float]:
    """Score examples versus words using normalized Levenshtein"""
    scores = []
    for ex in examples:
        score = 0
        engchars = re.sub(r"\W+", "", eng)
        if len(engchars) == 0:
            LOGGER.warning("Empty English headword for %s", crg)
            score += 1
        elif ex.english:
            exengchars = re.sub(r"\W+", "", "".join(ex.english))
            score += score_example(engchars, exengchars) / len(engchars)
        crgchars = re.sub(r"\W+", "", crg)
        if len(crgchars) == 0:
            LOGGER.warning("Empty Michif headword for %s", eng)
            score += 1
        elif ex.michif:
            excrgchars = re.sub(r"\W+", "", "".join(ex.michif))
            score += score_example(crgchars, excrgchars) / len(crgchars)
        scores.append(score / 2)
    return scores


def create_entry(
    entry_fields: dict[str, Any], michif: str, examples: Optional[list[Example]] = None
) -> Entry:
    word, sense = find_sense(michif)
    if sense is not None:
        entry_fields["clarification"] = sense
    if examples is not None:
        return Entry(**entry_fields, michif=word, examples=examples)
    else:
        return Entry(**entry_fields, michif=word)


def extract_examples(
    entry: ParsedEntry, repeat_example_score: float = 0.0
) -> Iterable[Entry]:
    """Extract individual entries with matching examples.

    Ensures that each example gets used at least once - only examples
    scoring less than `repeat_example_score` (minimum normalized
    Levenshtein distance from headword) can be repeated, set this to
    zero to never repeat them.
    """
    LOGGER.debug("parsed entry: %s", entry)
    # Sometimes there is no definition, only examples, so move them to the right place
    if len(entry.michif) == 1 and entry.examples:
        entry_lang, _ = language_id(entry.michif[0])
        example_langs = set(language_id(example)[0] for example in entry.examples)
        if len(example_langs) == 1 and entry_lang != next(iter(example_langs)):
            entry.examples.insert(0, entry.michif[0] + ".")
            entry.michif = []

    # Extract the fields from the ParsedEntry
    entry_fields = entry.model_dump(exclude={"michif", "examples"})
    # No examples, just return entries
    if not entry.examples:
        return [create_entry(entry_fields, michif=word) for word in entry.michif]

    # Indexed by Michif definition (they all have the same English headword)
    entries: dict[str, Entry] = {}

    # Group and spread example sentences to get 1-to-1 Examples
    example_groups = group_examples(entry.examples)
    ngroups = len(example_groups)
    LOGGER.debug("example groups: %s", example_groups)
    examples = spread_examples(example_groups)
    LOGGER.debug("examples: %s", examples)

    # Handle case of no definition - one entry, all examples
    if len(entry.michif) == 0 and examples:
        return [
            Entry(
                **entry_fields,
                michif="",
                examples=[
                    Example(english=ex.english, michif=ex.michif, score=score)
                    for ex, score in zip(
                        examples, score_examples(entry.english, "", examples)
                    )
                ],
            )
        ]
    elif len(examples) == 1 and not examples[0].michif:
        # Handle case of only one English example, presumed to correspond to all Michif definitions
        # (FIXME: this might generalize to the case of only one Michif example as well)
        for word in entry.michif:
            example = examples[0].model_copy()
            example.michif = word  # FIXME: why?
            (example.score,) = score_examples(entry.english, word, [example])
            entries[word] = create_entry(entry_fields, michif=word, examples=[example])
    elif len(entry.michif) == ngroups and len(entry.michif) == len(examples):
        # Easy (and frequent) case: one example for each word, in
        # order.  We require that they not be "spread" either as this
        # can cause mismatches.
        # Score them anyway as they might get merged later
        for word, example in zip(entry.michif, examples):
            (example.score,) = score_examples(entry.english, word, [example])
            # print("scored", score, word, ex)
            entries[word] = create_entry(entry_fields, michif=word, examples=[example])
    else:
        # Match words to examples greedily
        scored: list[tuple] = []
        for word in entry.michif:
            scored.extend(
                zip(
                    score_examples(entry.english, word, examples),
                    range(len(examples)),
                    itertools.repeat(word),
                )
            )
        LOGGER.debug("scored examples: %s", scored)
        scored.sort()
        seen_examples = set()
        for score, idx, word in scored:
            example = examples[idx].model_copy()
            example.score = score
            # Make sure all the words and examples get used
            if idx not in seen_examples:
                # Add to list of examples
                if word in entries:
                    entries[word].examples.append(example)
                else:
                    entries[word] = create_entry(
                        entry_fields, michif=word, examples=[example]
                    )
            elif word not in entries:
                # Only repeat examples if they have a good enough score
                if score < repeat_example_score:
                    entries[word] = create_entry(
                        entry_fields, michif=word, examples=[example]
                    )
                else:
                    entries[word] = create_entry(entry_fields, michif=word)
            seen_examples.add(idx)
    LOGGER.debug("entries: %s", entries)
    return entries.values()


def main():
    entries = []
    for spam in fileinput.input():
        entry = ParsedEntry.parse_raw(spam)
        entries.extend(extract_examples(entry))
    for entry in entries:
        print(entry.json(exclude_defaults=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
