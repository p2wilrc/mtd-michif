#!/usr/bin/env python

"""Read information from TM metadata XLSX and write to JSON for future use."""

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from os import PathLike
from pathlib import Path

from openpyxl import load_workbook  # type: ignore

LOGGER = logging.getLogger(Path(__file__).stem)


def make_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", help="Excel notebook with metadata")
    return parser


def read_metadata(path: PathLike) -> dict[str, dict | list]:
    wb = load_workbook(path)

    people = {}
    hdr = list(next(wb["People"].iter_rows(1, 1, values_only=True)))
    for row in wb["People"].iter_rows(2, values_only=True):
        row = {hdr[i]: x for i, x in enumerate(row)}
        people[row["ID"]] = row
    sessions: defaultdict[str, dict] = defaultdict(dict)
    hdr = list(next(wb["Sessions"].iter_rows(1, 1, values_only=True)))
    for row_idx in range(2, wb["Sessions"].max_row + 1):
        row = {hdr[i]: x.value for i, x in enumerate(wb["Sessions"][row_idx])}
        if row["FileName"] is None:
            continue
        for col in ("SessionDate", "StatusDate"):
            if row[col] is not None:
                if isinstance(row[col], datetime):
                    row[col] = row[col].strftime("%Y-%m-%d")
                else:
                    LOGGER.info("%s is not datetime: %s", col, row[col])
        filename, _ = os.path.splitext(row["FileName"])
        if filename in sessions:
            LOGGER.warning("Duplicate file %s", filename)
        sessions[filename] = row
    notes = []
    hdr = list(
        next(wb["Annotator Notes & Missed Words"].iter_rows(1, 1, values_only=True))
    )
    for row in wb["Annotator Notes & Missed Words"].iter_rows(2, values_only=True):
        row = {hdr[i]: x for i, x in enumerate(row)}
        if row["FileName"] is None:
            continue
        for col in ("StatusDate",):
            if row[col] is not None:
                if isinstance(row[col], datetime):
                    row[col] = row[col].strftime("%Y-%m-%d")
                else:
                    LOGGER.info("%s is not datetime: %s", col, row[col])
        notes.append(row)
    return {"people": people, "sessions": sessions, "notes": notes}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = make_argparse()
    args = parser.parse_args()
    print(json.dumps(read_metadata(args.metadata), indent=2))
