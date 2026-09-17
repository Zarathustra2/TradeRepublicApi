import sys

sys.path.append("../")
from trapi.api import TrBlockingApi

from environment import *

import json
import time

tr = TrBlockingApi(NUMBER, PIN, locale=LOCALE)
tr.login()


def fetch_all(request):
    """Pages through a timeline topic until the server stops handing out a cursor."""
    items = []
    after = None
    while True:
        res = request(after=after)
        items.extend(res["items"])
        print(f"{len(items)} entries so far")

        after = res.get("cursors", {}).get("after")
        if not after:
            return items
        time.sleep(1)


# Trade Republic split the former "timeline" topic in two: the transactions
# carry everything that moves money, the activity log holds the rest.
transactions = fetch_all(tr.timeline_transactions)
activity_log = fetch_all(tr.timeline_activity_log)

# Write JSON files
with open("./myTimeline.json", "w") as f:
    json.dump(transactions, f, indent="\t")

with open("./myActivityLog.json", "w") as f:
    json.dump(activity_log, f, indent="\t")

print(f"finished: {len(transactions)} transactions, {len(activity_log)} activity entries")
