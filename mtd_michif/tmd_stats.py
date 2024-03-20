import argparse
import json
from pathlib import Path

from tqdm import tqdm

from mtd_michif.dictionary import Dictionary
from mtd_michif.types import Entry, Example

parser = argparse.ArgumentParser(
    description="Get statistics of built dictionary",
)
parser.add_argument(
    "-r",
    "--ref",
    type=Path,
    metavar="FILE",
    help="the reference JSON file to use",
)
parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="report differences verbosely",
)
parser.add_argument(
    "dictionary",
    type=Path,
    metavar="FILE",
    help="the dictionary JSON file to load",
)


def entry_stats(ref_entries, hyp_entries):
    """Collect precision/recall statistics for one or more entries.

    Because this is just based on *unique* words, it's recommended
    that you do this for individual entries if possible (but generally
    this is done for all the entries for a given headword).
    """

    def get_lang_words(entry, lang):
        words = getattr(entry, lang).lower().split()
        for example in entry.examples:
            words.extend(getattr(example, lang).lower().split())
        if lang == "english" and entry.clarification:
            words.extend(entry.clarification.lower().split())
        return words

    ref_eng = []
    ref_crg = []
    for entry in ref_entries:
        ref_eng.extend(get_lang_words(entry, "english"))
        ref_crg.extend(get_lang_words(entry, "michif"))
    hyp_eng = []
    hyp_crg = []
    for entry in hyp_entries:
        hyp_eng.extend(get_lang_words(entry, "english"))
        hyp_crg.extend(get_lang_words(entry, "michif"))
    ref_total = hyp_total = ref_correct = hyp_correct = 0
    refset = set(ref_eng)
    for word in set(hyp_eng):
        hyp_total += 1
        if word in refset:
            hyp_correct += 1
    refset = set(ref_crg)
    for word in set(hyp_crg):
        hyp_total += 1
        if word in refset:
            hyp_correct += 1
    hypset = set(hyp_eng)
    for word in set(ref_eng):
        ref_total += 1
        if word in hypset:
            ref_correct += 1
    hypset = set(hyp_crg)
    for word in set(ref_crg):
        ref_total += 1
        if word in hypset:
            ref_correct += 1
    return ref_total, hyp_total, ref_correct, hyp_correct


def create_entry(entry_dict):
    """Create an Entry from a legacy JSON representation."""
    entry = Entry(english=entry_dict["english"], michif=entry_dict["michif"])
    if "clarification" in entry_dict:
        entry.clarification = entry_dict["clarification"]
    if "example" in entry_dict:
        example = entry_dict["example"]
        entry.examples.append(
            Example(english=example["english"], michif=example["michif"])
        )
    if "examples" in entry_dict:
        for example in entry_dict["examples"]:
            entry.examples.append(
                Example(english=example["english"], michif=example["michif"])
            )
    return entry


def main():
    args = parser.parse_args()
    dictionary = Dictionary.load_json(args.dictionary)
    n_examples = 0
    missing_audio = 0
    missing_example_audio = 0
    entries = dictionary.entries.values()
    for entry in tqdm(entries):
        if not entry.audio:
            missing_audio += 1
        if entry.examples:
            n_examples += 1
            if all(not example.audio for example in entry.examples):
                missing_example_audio += 1
    print(
        "Dictionary has %d entries and %d entries with examples:"
        % (len(entries), n_examples)
    )
    print(
        "\t%d entries are missing audio (%.2f%%)"
        % (missing_audio, missing_audio / len(entries) * 100)
    )
    print(
        "\t%d entries are missing examples (%.2f%%)"
        % (len(entries) - n_examples, (len(entries) - n_examples) / len(entries) * 100)
    )
    print(
        "\t%d examples are missing audio (%.2f%%)"
        % (missing_example_audio, missing_example_audio / n_examples * 100)
    )
    if args.ref:
        testsets = [args.ref]
    else:
        testdata = Path(__file__).parent.parent / "testdata" / "dictionary"
        testsets = testdata.iterdir()
    print("\nTest sets:")
    stats = {}
    for testset in testsets:
        if testset.suffix != ".json":
            continue
        with open(testset) as infh:
            ts_stats = stats[testset.stem] = dict(rt=0, ht=0, rc=0, hc=0)
            ref = [create_entry(entry_dict) for entry_dict in json.load(infh)]
            ref_words = set(entry.english for entry in ref)
            ref_byword = dict(
                (word, [entry for entry in ref if entry.english == word])
                for word in ref_words
            )
            hyp_byword = dict(
                (word, [entry for entry in entries if entry.english == word])
                for word in ref_words
            )
            for headword in ref_byword:
                rt, ht, rc, hc = entry_stats(ref_byword[headword], hyp_byword[headword])
                ts_stats["rt"] += rt
                ts_stats["ht"] += ht
                ts_stats["rc"] += rc
                ts_stats["hc"] += hc
                if args.verbose and (rt != rc or ht != hc):
                    print(f"{headword}:")
                    print("ref:", ref_byword[headword])
                    print("hyp:", hyp_byword[headword])
            p = ts_stats["hc"] / ts_stats["ht"] if ts_stats["ht"] else 0
            r = ts_stats["rc"] / ts_stats["rt"] if ts_stats["rt"] else 0
            f1 = (2 * p * r / (p + r)) if p + r != 0 else 0
            print("\t%s precision %.4f recall %.4f f1 %.4f" % (testset.stem, p, r, f1))
    all_stats = {}
    for st in "rt", "ht", "rc", "hc":
        all_stats[st] = sum(x[st] for x in stats.values())
    p = all_stats["hc"] / all_stats["ht"]
    r = all_stats["rc"] / all_stats["rt"]
    f1 = (2 * p * r / (p + r)) if p + r != 0 else 0
    print("Overall: precision %.4f recall %.4f f1 %.4f" % (p, r, f1))


if __name__ == "__main__":
    main()
