"""Exports the timeline together with the detail of every entry.

Writes myTimeline.json and myTimelineDetails.json, and downloads the
documents Trade Republic attaches to an entry - order confirmations, dividend
statements and the like.

    python3 timelineExporterWithDocsAndDetails.py

The details are what timelineCsvConverter.py needs for share counts, prices
and isins: the timeline entries themselves carry none of those.
"""

import sys

sys.path.append("../")

import json
import os
import time

import requests

from trapi.api import TrBlockingApi
from trapi.timeline import detail_documents, document_url

from environment import *

TIMELINE_FILE = "./myTimeline.json"
DETAILS_FILE = "./myTimelineDetails.json"
DOCUMENT_DIR = "./_docDownloads"


def fetch_timeline(tr):
    """Pages through the transactions until the server runs out of cursors."""
    items = []
    after = None
    while True:
        res = tr.timeline_transactions(after=after)
        items.extend(res["items"])
        print(f"  {len(items)} entries")

        after = res.get("cursors", {}).get("after")
        if not after:
            return items
        time.sleep(1)


def fetch_details(tr, items):
    """The detail of every entry that links to one, keyed by entry id."""
    details = {}
    for number, item in enumerate(items, start=1):
        payload = (item.get("action") or {}).get("payload")
        if not payload:
            continue
        try:
            details[item["id"]] = tr.timeline_detail(payload)
        except Exception as error:
            # One entry the server cannot render is no reason to lose the
            # rest of the export.
            print(f"  detail {number}/{len(items)} failed: {error}")
            continue
        if number % 25 == 0:
            print(f"  {number}/{len(items)} details")
        time.sleep(0.2)
    return details


def download_documents(tr, details, directory):
    """Saves every document of every detail, skipping what is already there.

    Trade Republic attaches documents in two ways. Some come as a ready to
    use link to a storage host, others only as a path that has to be fetched
    from the API with the cookies of the session.
    """
    os.makedirs(directory, exist_ok=True)
    saved, failed = 0, 0

    for event_id, detail in details.items():
        for number, document in enumerate(detail_documents(detail), start=1):
            url = document_url(document)
            if not url:
                continue

            name = "".join(c if c.isalnum() or c in "-_" else "_"
                           for c in document["title"])[:60]
            path = os.path.join(directory, f"{event_id}_{number}_{name}.pdf")
            if os.path.isfile(path):
                continue

            # Only the API gets to see the session. The ready made links
            # point at a storage host, and the cookies have no business
            # being sent there.
            fetch = tr.session.get if url.startswith(tr.url) else requests.get

            try:
                response = fetch(url, timeout=60)
                response.raise_for_status()
            except Exception as error:
                print(f"  could not download {document['title']}: {error}")
                failed += 1
                continue

            with open(path, "wb") as f:
                f.write(response.content)
            saved += 1

    return saved, failed


def main():
    tr = TrBlockingApi(NUMBER, PIN, locale=LOCALE, timeout=30)

    print("Logging in - approve the notification in the app if one appears")
    tr.login()

    print("Timeline")
    items = fetch_timeline(tr)

    print("Details")
    details = fetch_details(tr, items)

    with open(TIMELINE_FILE, "w") as f:
        json.dump(items, f, indent="\t")
    with open(DETAILS_FILE, "w") as f:
        json.dump(details, f, indent="\t")

    print("Documents")
    saved, failed = download_documents(tr, details, DOCUMENT_DIR)

    tr.close()

    print(f"\n{len(items)} entries, {len(details)} details, "
          f"{saved} documents saved into {DOCUMENT_DIR}"
          + (f", {failed} failed" if failed else ""))


if __name__ == "__main__":
    main()
