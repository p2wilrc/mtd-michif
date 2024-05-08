"""
Export TMD data as CSV for spreadsheet.
"""

import csv
from mtd_michif.dictionary import Dictionary

dict = Dictionary.load_json("build/laverdure_final.json")
naudios = 0
example_naudios: list[int] = []
for entry in dict.entries.values():
    naudios = max(naudios, len(entry.audio))
    for idx, example in enumerate(entry.examples):
        if len(example_naudios) == idx:
            example_naudios.append(0)
        example_naudios[idx] = max(example_naudios[idx], len(example.audio))
fieldnames = ["ID", "English", "Clarification", "Michif"]
for idx in range(naudios):
    fieldnames.append(f"Audio {idx+1} Speaker")
    fieldnames.append(f"Audio {idx+1} Filename")
for idx, num in enumerate(example_naudios):
    fieldnames.append(f"Example {idx+1} English")
    fieldnames.append(f"Example {idx+1} Michif")
    for aidx in range(num):
        fieldnames.append(f"Example {idx+1} Audio {aidx+1} Speaker")
        fieldnames.append(f"Example {idx+1} Audio {aidx+1} Filename")

with open("build/laverdure_final.csv", "wt", encoding="utf-8-sig") as outfh:
    writer = csv.DictWriter(outfh, fieldnames=fieldnames)
    writer.writeheader()
    for entry in dict.entries.values():
        row = {}
        row["ID"] = entry.id
        row["English"] = entry.english
        row["Michif"] = entry.michif
        for idx, audio in enumerate(entry.audio):
            row[f"Audio {idx+1} Speaker"] = audio.speaker
            row[f"Audio {idx+1} Filename"] = audio.path.name
        for idx, example in enumerate(entry.examples):
            row[f"Example {idx+1} English"] = example.english
            row[f"Example {idx+1} Michif"] = example.michif
            for aidx, audio in enumerate(example.audio):
                row[f"Example {idx+1} Audio {aidx+1} Speaker"] = audio.speaker
                row[f"Example {idx+1} Audio {aidx+1} Filename"] = audio.path.name
        writer.writerow(row)
