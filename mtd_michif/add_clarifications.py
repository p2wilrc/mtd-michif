#!/usr/bin/env python3

"""Add the "clarifications" of English headword senses to the
headwords.  Has to be done as a final postprocessing step because
MotherTongues isn't capable of sorting on multiple fields, and because
the senses can't be present when matching annotations (FIXME: actually
that may not be true)
"""

import argparse

from mtd_michif.dictionary import Dictionary


def make_argparse() -> argparse.ArgumentParser:
    """Make the argparse."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dictionary", help="JSON file with final dictionary (including audio)"
    )
    parser.add_argument("outfile", help="JSON file for post-processed dictionary")
    return parser


def add_clarifications(dictionary):
    for entry in dictionary.entries.values():
        if entry.clarification is not None:
            # Skip these
            if entry.clarification.lower().startswith("(see"):
                continue
            entry.english = f"{entry.english} ({entry.clarification})"
            entry.clarification = None


def main(args):
    dictionary = Dictionary.load_json(args.dictionary)
    dictionary.save_json(args.outfile)


if __name__ == "__main__":
    parser = make_argparse()
    args = parser.parse_args()
    main(args)
