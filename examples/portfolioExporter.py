import sys
sys.path.append('../')
from trapi.api import TRApi

from environment import *

import json
import asyncio

def process(jsonData):
    print(jsonData)
    # Write JSON file
    with open('./myPortfolio.json', 'w') as f:
        json.dump(jsonData, f, indent="\t")
    exit()

async def main():
    tr = TRApi(NUMBER, PIN)
    tr.login()

    await tr.portfolio(callback=process)

    await tr.start()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())