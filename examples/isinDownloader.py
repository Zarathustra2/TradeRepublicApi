import sys
sys.path.append('../')
from trapi.api import TrBlockingApi

from environment import *

import json
import time
import argparse
import os

# This folder is used to store alle single ISIN files
OUTPUT_FOLDER = './stock_details/'

isins = []

# Create command line parameters
parser = argparse.ArgumentParser()
# Crawl
parser.add_argument("-i", "--isin", help="Crawl single ISIN")
parser.add_argument("-f", "--file", help="Crawl a list of ISINs")
parser.add_argument("-p", "--portfolio", action='store_true', help="Crawl all stocks from myPortfolio.json")
# Combine
parser.add_argument("-c", "--combine", action='store_true', help="Combine all stock data to a single JSON file")
args = parser.parse_args()

# Add to list
if args.isin != None:
    isins.append(args.isin)
if args.file != None:
    try:
        with open(args.file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                isins.append(line.rstrip())
    except Exception as e:
        print(e)
        exit()
if args.portfolio == True:
    try:
        with open("./myPortfolio.json", "r") as f:
            portfolio = json.loads(f.read())
            for position in portfolio["positions"]:
                isins.append(position["instrumentId"])
    except Exception as e:
        print("Error while opening portfolio file!")
        print(e)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

if len(isins) > 0:
    # TR Login
    tr = TrBlockingApi(NUMBER, PIN)
    tr.login()

    # Crawl all ISINs in list
    for isin in isins:
        isin = isin.rstrip()

        retry = 0
        while True:
            print('Processing {0}'.format(isin))
            res = tr.stock_details(isin)
            print(res)

            if res == None:
                retry = retry+1
                time.sleep(retry)
                if retry >= 3:
                    tr = TrBlockingApi(NUMBER, PIN)
                    tr.login()
            else:
                # Write JSON file
                with open('{0}{1}.json'.format(OUTPUT_FOLDER, isin), 'w') as f:
                    json.dump(res, f, indent="\t")
                break
            
        time.sleep(1)

if args.combine == True:
    stocks = []
    for filename in os.listdir(OUTPUT_FOLDER):
        print('Processing '+filename)
        stock = {}
        with open(OUTPUT_FOLDER + filename, 'r') as f:
            stock = json.loads(f.read())
        # Remove useless stuff
        del stock["hasKpis"]
        del stock["key"]
        stocks.append(stock)

    # Write JSON file
    with open('./allStocks.json', 'w') as f:
        json.dump(stocks, f, indent="\t")

print('Finished!')