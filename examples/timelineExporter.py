import sys

sys.path.append("../")
import json
import time

from environment import *

from trapi.api import TrBlockingApi

tr = TrBlockingApi(NUMBER, PIN, locale=LOCALE)
tr.login()

data = []
after = ""

try:
    while True:
        res = tr.timeline(after=after)
        print(res)
        for d in res["data"]:
            data.append(d)
        after = res["cursors"]["after"]
        time.sleep(1)
except:
    print("finished!")


# Write JSON file
with open("./myTimeline.json", "w") as f:
    json.dump(data, f, indent="\t")
