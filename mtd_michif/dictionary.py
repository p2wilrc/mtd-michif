"""Module containing code to extract definitions and examples from
Laverdure Turtle Mountain Dictionary of Michif.
"""

import json
import logging
import re
from collections import defaultdict
from typing import Optional

from pydantic import RootModel

from . import extract_examples, parse_entries
from .pydantic_models import Entry

LOGGER = logging.getLogger("mtd-michif")


"""Model for writing the dictionary so we don't have to care about Path not being serializable."""
SavedDictionary = RootModel[list[Entry]]


class Dictionary:
    """Dictionary of English to Michif."""

    def __init__(self, omit_ids=False):
        self.entries = {}
        self.unknown_ids = 0
        self.omit_ids = omit_ids

    def save_json(self, filename):
        """Save the dictionary to a JSON file."""
        with open(filename, "w") as outfile:
            if self.omit_ids:
                entries = SavedDictionary.model_validate(sorted(self.entries.values()))
            else:
                entries = SavedDictionary.model_validate(
                    sorted(self.entries.values(), key=lambda x: x.id)
                )
            outfile.write(entries.model_dump_json(indent=2, exclude_defaults=True))
            outfile.write("\n")  # satisfy emacs

    @classmethod
    def load_json(cls, filename):
        """Load the dictionary from a JSON file."""
        dictionary = Dictionary()
        with open(filename) as infile:
            data = json.load(infile)
            for entry_dict in data:
                entry = Entry.model_validate(entry_dict)
                if entry.id is None:
                    dictionary.omit_ids = True
                dictionary.add_entry(entry)
        return dictionary

    @classmethod
    def from_text(
        cls, path, repeat_example_score=0.0, omit_ids=False, uncorrectables=None
    ):
        """Parse dictionary from text input."""
        dictionary = Dictionary(omit_ids=omit_ids)
        overrides = defaultdict(list)
        if uncorrectables is not None:
            for (english, _, _), entry in uncorrectables.entries.items():
                overrides[english].append(entry)
        with open(path) as infile:
            page = 0
            lineno = 0
            for line in infile:
                m = re.match(r"^#\s*(\d+)?", line)
                if m:
                    if m.group(1):
                        page = int(m.group(1))
                        lineno = 1
                    continue
                dictionary.parse_line(
                    line, page, lineno, repeat_example_score, overrides
                )
                lineno += 1
        return dictionary

    def parse_line(
        self,
        line: str,
        page: int = 0,
        lineno: int = 0,
        repeat_example_score: float = 0.0,
        overrides: Optional[dict[str, list]] = None,
    ):
        """Parse a line in the text-format Turtle Mountain Dictionary,
        adding the entries to the dictionary."""
        parsed_entries = parse_entries.parse_line(line)
        # Assume that there is only one headword, and apply overrides if so
        if not parsed_entries:
            return
        headword = parsed_entries[0].english
        if overrides is not None and headword in overrides:
            entries = overrides[headword]
        else:
            entries = []
            for parsed_entry in sorted(
                parsed_entries,
                key=lambda x: (
                    "" if x.clarification is None else x.clarification,
                    x.michif,
                ),
            ):
                example_entries = extract_examples.extract_examples(parsed_entry)
                for entry in sorted(
                    example_entries,
                    key=lambda x: (
                        "" if x.clarification is None else x.clarification,
                        x.michif,
                    ),
                ):
                    entries.append(entry)
        defno = 1
        for entry in entries:
            if not self.omit_ids:
                if page and lineno:
                    entry.id = "%03d-%03d-%02d" % (page, lineno, defno)
                    defno += 1
                else:
                    entry.id = "999-99-%02d" % self.unknown_ids
                    self.unknown_ids += 1
            self.add_entry(entry)

    def add_entry(self, entry: Entry):
        """Add an entry to the dictionary, updating indexes."""
        key = (entry.english, entry.michif, entry.clarification)
        if key in self.entries:
            # Merge examples in otherwise duplicate entries
            LOGGER.warning(
                "Merging examples for duplicate entry %s(%s):%s",
                entry.english,
                entry.clarification,
                entry.michif,
            )
            self.entries[key].examples.extend(entry.examples)
        else:
            if entry.id is None and not self.omit_ids:
                entry.id = "999-99-%02d" % self.unknown_ids
                self.unknown_ids += 1
            self.entries[key] = entry
