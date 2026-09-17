"""Turns an exported timeline into a CSV for Portfolio Performance.

    python3 timelineExporterWithDocsAndDetails.py
    python3 timelineCsvConverter.py

Reads myTimeline.json and, when it is there, myTimelineDetails.json, and
writes myTransactions.csv.

Without the details there are no share counts, no prices and no isins,
because a timeline entry carries none of those - only its total amount. The
converter still writes those entries, with the columns left empty.

Entries whose eventType the converter does not know are reported at the end
rather than dropped in silence, so a new kind of event does not quietly
disappear from the export.
"""

import sys

sys.path.append("../")

import json
import os
from collections import Counter

from trapi.timeline import (
    EVENT_TYPES,
    NOT_EXPORTED,
    transaction_of,
    write_csv,
)

from environment import *

TIMELINE_FILE = "./myTimeline.json"
DETAILS_FILE = "./myTimelineDetails.json"
CSV_FILE = "./myTransactions.csv"



def load(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    items = load(TIMELINE_FILE)
    if items is None:
        raise SystemExit(
            f"{TIMELINE_FILE} is missing - run timelineExporterWithDocsAndDetails.py first"
        )

    details = load(DETAILS_FILE, {})
    if not details:
        print(f"note: {DETAILS_FILE} is missing, "
              "shares, prices and isins will stay empty")

    transactions = []
    skipped = Counter()

    for item in items:
        if not isinstance(item, dict):
            continue

        # No fixed decimal separator: one and the same response mixes
        # "€26.55" and "9,99 €", so each value is read on its own.
        transaction = transaction_of(item, details.get(item.get("id")))
        if transaction is None:
            event_type = item.get("eventType") or "without an eventType"
            known = event_type in EVENT_TYPES
            skipped["cancelled or deleted" if known else event_type] += 1
            continue

        transactions.append(transaction)

    transactions.sort(key=lambda t: (t.date is None, t.date))

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        write_csv(transactions, f, locale=LOCALE)

    print(f"{len(transactions)} transactions written to {CSV_FILE}")

    without_isin = sum(1 for t in transactions
                       if t.isin is None and t.kind in ("buy", "sell"))
    if without_isin:
        print(f"{without_isin} trades have no isin - their detail was missing")

    if skipped:
        print("\nnot exported:")
        unknown = False
        for reason, count in skipped.most_common():
            explanation = NOT_EXPORTED.get(reason)
            if explanation:
                print(f"  {count:>5}  {reason} - {explanation}")
            else:
                print(f"  {count:>5}  {reason}")
                unknown = reason not in ("cancelled or deleted",)
        if unknown:
            print("\nAn eventType listed without a reason is one this "
                  "converter does not know yet. If it belongs in the export, "
                  "add it to EVENT_TYPES in trapi/timeline.py.")


if __name__ == "__main__":
    main()
