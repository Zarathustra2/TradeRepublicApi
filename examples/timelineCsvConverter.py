import json
import re
from datetime import datetime

# Read my timeline
with open("myTimeline.json", "r", encoding="utf-8") as f:
    timeline = json.loads(f.read())

# Read stock JSON data
with open("../LS/isins.json", "r", encoding="utf-8") as f:
    lsIsins = json.loads(f.read())

# All stocks crawled from TR
with open("allStocks.json", "r", encoding="utf-8") as f:
    allStocks = json.loads(f.read())
    companyNames = {}
    for stock in allStocks:
        companyNames[stock["company"]["name"]] = stock["isin"]

# Fixed ISINs
with open("companyNameIsins.json", "r", encoding="utf-8") as f:
    fixedIsins = json.loads(f.read())


# Extract decimal number in a string
def getDecimalFromString(inputString):
    try:
        numbers = re.findall("[-+]?\d.*\,\d+|\d+", inputString)
        return numbers[0].replace(".", "").replace(",", ".")
    except:
        return None
    return None


# Unify a company name to compare
# Trade Republic uses different company names. This makes it very hard to map the timeline events to companies.
# @TradeRepublic: Please add ISIN in timeline event JSON
def unifyCompanyName(inputString):
    unify = "".join(e for e in inputString if e.isalnum()).lower()
    return unify


# Return ISIN from company name. Uses the JSON object from isins.json
# Returns None, if no ISIN found
def getIsinFromStockName(stockName):
    try:
        return companyNames[stockName]
    except:
        try:
            # Try to get the ISIN from the fixed list
            return fixedIsins[stockName]
        except:
            stockNameUnify = unifyCompanyName(stockName)
            for stock in lsIsins:
                try:
                    isin = stock[1]
                    name = stock[2]
                    nameUnify = unifyCompanyName(stock[2])
                    if stockNameUnify in nameUnify:
                        return isin
                except:
                    continue
    return ""


# Portfolio Performance transaction types
# Kauf, Einlage, Verkauf, Zinsen, Gebühren, Dividende, Umbuchung (Eingang), Umbuchung (Ausgang)

missingIsins = {}

# Write transactions.csv file
# date, transaction, shares, amount, total, fee, isin, name
with open("myTransactions.csv", "w") as f:
    f.write("Datum;Typ;Stück;amount;Wert;Gebühren;ISIN;name\n")
    for event in timeline:
        event = event["data"]
        dateTime = datetime.fromtimestamp(int(event["timestamp"] / 1000))
        date = dateTime.strftime("%Y-%m-%d")

        title = event["title"]
        try:
            body = event["body"]
        except:
            body = ""

        if "storniert" in body:
            continue

        # Cash in
        if title == "Einzahlung":
            f.write(
                "{0};{1};{2};{3};{4};{5};{6};{7}\n".format(
                    date, "Einlage", "", "", event["cashChangeAmount"], "", "", ""
                )
            )
        elif title == "Auszahlung":
            f.write(
                "{0};{1};{2};{3};{4};{5};{6};{7}\n".format(
                    date, "Entnahme", "", "", abs(event["cashChangeAmount"]), "", "", ""
                )
            )
        # Dividend - Shares
        elif title == "Reinvestierung":
            # TODO: Implement reinvestment
            print("Detected reivestment, skipping... (not implemented yet)")
        # Dividend - Cash
        elif "Gutschrift Dividende" in body:
            isin = getIsinFromStockName(title)
            amountPerShare = getDecimalFromString(body)
            f.write(
                "{0};{1};{2};{3};{4};{5};{6};{7}\n".format(
                    date,
                    "Dividende",
                    "",
                    amountPerShare,
                    event["cashChangeAmount"],
                    "",
                    isin,
                    title,
                )
            )
            if isin == "" and title not in missingIsins.keys():
                missingIsins[title] = ""
                print("WARNING: Company not found ({0}), missing ISIN".format(title))
        # Savings plan execution or normal buy
        elif (
            body.startswith("Sparplan ausgeführt")
            or body.startswith("Kauf")
            or body.startswith("Limit Kauf zu")
        ):
            fee = 0
            if body.startswith("Kauf") or body.startswith("Limit Kauf zu"):
                fee = 1.0
            isin = getIsinFromStockName(title)
            amountPerShare = abs(float(getDecimalFromString(body)))
            cashChangeAmount = abs(event["cashChangeAmount"])
            shares = "{0:.4f}".format((cashChangeAmount - fee) / amountPerShare)
            f.write(
                "{0};{1};{2};{3};{4};{5};{6};{7}\n".format(
                    date,
                    "Kauf",
                    shares,
                    amountPerShare,
                    cashChangeAmount,
                    fee,
                    isin,
                    title,
                )
            )
            if isin == "" and title not in missingIsins.keys():
                missingIsins[title] = ""
                print("WARNING: Company not found ({0}), missing ISIN".format(title))
        # Sell
        elif body.startswith("Verkauf") or body.startswith("Limit Verkauf zu"):
            isin = getIsinFromStockName(title)
            amountPerShare = abs(float(getDecimalFromString(body)))
            cashChangeAmount = abs(event["cashChangeAmount"])
            shares = "{0:.4f}".format(cashChangeAmount / amountPerShare)
            f.write(
                "{0};{1};{2};{3};{4};{5};{6};{7}\n".format(
                    date,
                    "Verkauf",
                    shares,
                    amountPerShare,
                    cashChangeAmount,
                    "1.0",
                    isin,
                    title,
                )
            )
            if isin == "" and title not in missingIsins.keys():
                missingIsins[title] = ""
                print("WARNING: Company not found ({0}), missing ISIN".format(title))

if len(missingIsins.keys()) > 0:
    print("--- MISSING ISINs ---")
    print(json.dumps(missingIsins, indent="\t", sort_keys=True))
    print("Add ISINs to companyNameIsins.json and start again\n")

print("Finished!")
