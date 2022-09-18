####################################################################################################################
# PREREQUISITES:
#   0. SEE COMMENTS in file examples/timelineExporterWithDocsAndDetails.py
#   1. python3 ./examples/timelineExporterWithDocsAndDetails.py // yes this is prerequisite
#      This must be executed to export the JSONs that this very py file uses
#
# USAGE:
#   python3 ./examples/timelineExporterWithDocsAndDetails.py
#
####################################################################################################################

# import decimal
import copy
import json
import re
from datetime import datetime
from decimal import *
import sys

# from chardet import detect

sys.path.append("../")
import envConsts
from environment import LOCALE

####################################################################################
if LOCALE != "de":
    print("ERROR: Unfortunately, this script works only with local DE.\n")
    print("The JSON parsed is exported by the TR API while in DE Local.\n")
    exit(-1)
####################################################################################

print("==***START CONVERSION***================================================\n")

# Read my timeline
with open(envConsts.S_TIMELN_JSNFILE_PATH, "r", encoding="utf-8") as f:
    timeline = json.loads(f.read())

# Details open
with open(envConsts.S_TIMELD_JSNFILE_PATH, "r", encoding="utf-8") as f:
    timeline_det = json.loads(f.read())

# Fixed ISINs
with open(envConsts.S_COMPNAMEISINS_PATH , "r", encoding="utf-8") as f:
    fixedIsins = json.loads(f.read())

with open("examples/ignoredEntries.json", "r", encoding="utf-8") as f:
    entriesToIgnorePre = json.loads(f.read())

# Extract decimal number in a string
def getDecimalFromString(inputString: str) -> Decimal:
    try:
        numbers = re.findall("[-+]?\d.*\,\d+|\d+", inputString)
        fResult: Decimal = Decimal(numbers[0].replace(".", "").replace(",", "."))
        return fResult
    except Exception:
        return None


# Unify a company name to compare
# Trade Republic uses different company names. This makes it very hard to map the timeline events to companies.
# @TradeRepublic: Please add ISIN in timeline event JSON
# def unifyCompanyName(inputString):
#    unify = "".join(e for e in inputString if e.isalnum()).lower()
#    return unify


# Return ISIN from company name. Uses the JSON object from isins.json
# Returns None, if no ISIN found
def getIsinFromStockName(stockName):
    try:
        # Try to get the ISIN from the fixed list
        return fixedIsins[stockName]
    except KeyError:
        return ""  # will make it reported


# Portfolio Performance transaction types
# Kauf, Einlage, Verkauf, Zinsen, Gebühren, Dividende, Umbuchung (Eingang), Umbuchung (Ausgang)
# Buy, Deposit, Sell, Interest, Fees, Dividends, Transfer (Inbound), Transfer (Outbound)

missingIsins = {}
entriesToIgnore = {}

detailDict = {}  # dict([(1,''), (2, {})])
lTypeList = []
lColList = []


# noinspection PyShadowingNames
def reportAndAddMissingISINs(isin: str, title: str, tmID: str, date: datetime) -> None:
    if isin == "" and title not in missingIsins.keys():
        missingIsins[title] = ""
        print(
            "WARNING: Company(event title) not found ({0}), missing ISIN @ ({2}) in id({1})".format(title, tmID, date))


def inCurrencyType(dec: Decimal) -> float:
    return float(dec)


def processEvent(detailEv, lColList2, lTypeList2, currRecord):
    # we keep the header management hear to have this accessed only here.
    #    Otherwise, Detailed comment Header Management is hardcoded and
    #    thus, not dependent of details themselves
    DET_COMMENT_HEADER = "Detail Comment"
    if DET_COMMENT_HEADER not in lColList2:
        lColList2.append(DET_COMMENT_HEADER)
        lTypeList2.append("string")

    sections = detailEv["sections"]
    sMasterTitle = detailEv["titleText"]
    iAbrNo: int = 0
    iNoOfSummary: int = 0  # must always be 1 but just in case
    for sec in sections:
        if sec["type"] == "table":
            sSecItemTitle = sec["title"]
            bProcess: bool = False
            if sSecItemTitle.startswith("\u00dcbersicht"):
                iNoOfSummary += 1
                bProcess = True
            elif sSecItemTitle.startswith("Abrechnung"):
                iAbrNo += 1
                bProcess = True
                # Merge single entry as Entry 0 to avoid excessive columns
                if sSecItemTitle == "Abrechnung 1":
                    sSecItemTitle = "Abrechnung"
            # The 2 sections have similar processing
            # We are processing all sections that have "value"'s
            if bProcess:
                for secItem in sec["data"]:
                    itemTitle = secItem["title"]
                    sDetAttribName = "{0}({1})".format(itemTitle, sSecItemTitle)
                    itemValue: float = 0
                    bValue: bool = False
                    try:
                        itemValue = secItem["detail"]["value"]
                        bValue = True
                    except KeyError:
                        itemValue = 0  # defence
                    if bValue:
                        itemType = secItem["detail"]["type"]
                        # itemValue = secItem["detail"]["value"]
                        if currRecord is None:
                            if not (sDetAttribName in lColList2):
                                lColList2.append(sDetAttribName)
                                lTypeList2.append(itemType)
                            else:
                                pass
                        else:
                            # assuming no repeating entries like "sum"
                            currRecord[sDetAttribName] = itemValue
                            # we currently ignore type

    if currRecord is not None:
        currRecord[DET_COMMENT_HEADER] = "{0}, Summary Entries {1}, Accounting Entries: {2}".format(sMasterTitle
                                                                                                    , iNoOfSummary
                                                                                                    , iAbrNo)

def makeDetailsDictionary(timeline_det2, detailDict2):
    for detailEv2 in timeline_det2:
        sKey = detailEv2["id"]
        detailDict2[sKey] = detailEv2


def ExtractColumns(lColList2, lTypeList2):
    for detailEv2 in timeline_det:
        processEvent(detailEv2, lColList2, lTypeList2, None)


def initCols(lColList2, lTypeList2):
    lColList2.append("TRANS_ID")
    lTypeList2.append("string")
    lColList2.append("RAW_Timestamp")
    lTypeList2.append("string")
    lColList2.append("RAW_JsonBody")
    lTypeList2.append("string")
    lColList2.append("Datum")
    lTypeList2.append("string")
    lColList2.append("Type")
    lTypeList2.append("string")
    lColList2.append("NofShares")
    lTypeList2.append("string")
    lColList2.append("PricePerShareInEuroMilliCent")
    lTypeList2.append("string")
    lColList2.append("BankChangeInEuroMilliCent")
    lTypeList2.append("string")
    lColList2.append("GebührenInEuroMilliCent")
    lTypeList2.append("string")
    lColList2.append("ISIN")
    lTypeList2.append("string")
    lColList2.append("Name")
    lTypeList2.append("string")
    lColList2.append("Comment")
    lTypeList2.append("string")

def reorderColumns(lColList2, lTypeList2):
    storedList = copy.deepcopy(lColList2)
    storedTypeList = copy.deepcopy(lTypeList2)
    lColList2.clear()
    lTypeList2.clear()

    # This is just a wished order. In case the column does not exist it will only print a warning
    S_ORDEREDCOLS = ["Datum"   # : "2021-12-01 18:41:29",
                    , "Type"  #
                    , "ISIN"  # : "US19260Q1076",
                    , "Name"  # "Kauf/verkauf/company name
                    , "PricePerShareInEuroMilliCent"  # : 2755000,
                    , "BankChangeInEuroMilliCent"  # : -27560000,
                    , "Anzahl(\u00dcbersicht)"  # : 10,
                    , "Limit Preis(\u00dcbersicht)"  # "",
                    , "Vrs. Total(\u00dcbersicht)"   # "",
                    , "Preis(\u00dcbersicht)"        # 275.5,
                    , "Total(\u00dcbersicht)"        # 2755.0,
                    , "Gesamt(\u00dcbersicht)"       # : "",
                    , "Bestand(\u00dcbersicht)"      # "" : ,
                    , "Dividende pro St\u00fcck(\u00dcbersicht)"  # : "",
                    , "Bemessungsgrundlage(Abrechnung)"  # : -2755,
                    , "Fremdkostenzuschlag(Abrechnung)"  # : -1,
                    , "Gesamt(Abrechnung)"               # : -2756,
                    , "Kapitalertragssteuer(Abrechnung)"  # : "",
                    , "Solidarit\u00e4tszuschlag(Abrechnung)"  # : "",
                    , "Eintragung Namensaktie(Abrechnung)"  # : "",
                    , "Mehrwertsteuer(Abrechnung)"  # : "",
                    , "Quellensteuer DE f\u00fcr US-Emittent(Abrechnung)"  # : "",
                    , "Zwischensumme(Abrechnung)"  # : "",
                    , "Wechselkurs(Abrechnung)"  # : "",
                    , "Kapitalertragssteuer Optimierung(Abrechnung)"  # : "",
                    , "Solidarit\u00e4tszuschlag Optimierung(Abrechnung)"  # : ""
                    , "Kapitalertragssteuer Optimierung(Abrechnung 2)"  # : "",
                    , "Solidarit\u00e4tszuschlag Optimierung(Abrechnung 2)"  # : "",
                    , "Gesamt(Abrechnung 2)"  # : "",
                    ]
                        # NOT ORDERED - if another language is used these will be more
                        # "TRANS_ID"
                        # "RAW_Timestamp"
                        # "RAW_JsonBody"
                        # "NofShares": -10, Calculated and reversed that is why I prefer to keep it as
                        #                just info - Anzahl is more reliable
                        # "Geb\u00fchrenInEuroMilliCent": -10000,
                        # "Comment": "",
                        # "Detail Comment": "Kauf Coinbase, Summary Entries 1, Accounting Entries: 1",
    # APPLY the order
    storedTypeListTypes = {}
    iL: int = 0
    while iL < len(storedList):
        storedTypeListTypes[storedList[iL]] = storedTypeList[iL]
        iL += 1

    for sColName in S_ORDEREDCOLS: 
        if sColName in storedList:
            lColList2.append(sColName)
            lTypeList2.append(storedTypeListTypes[sColName])

    # add all Manual reorder before this line
    # now copy the rest
    iIter = 0
    iLen = len(storedList)
    while iIter < iLen:
        sItem = storedList[iIter]
        if sItem not in lColList2:
            lColList2.append(sItem)
            lTypeList2.append(storedTypeList[iIter])
        iIter += 1


def initRecord(lColList2, lTypeList2, outRecord2):
    k = 0
    lengthZ = len(lColList2)
    while k < lengthZ:
        outRecord2[lColList2[k]] = ""
        k += 1

def prepRecord(detEv, outRec, tmId2,  sTimestamp2, szBody, date2, sType, iNoShares, mcentsPricePerShare,
               mcentsChangeAmount, mFee,  sIsin,  sTitle2,  szProcessingComment,
               lColList2=lColList, lTypeList2=lTypeList):
    outRec["TRANS_ID"] = tmId2
    outRec["RAW_Timestamp"] = sTimestamp2
    outRec["RAW_JsonBody"] = szBody
    outRec["Datum"] = date2
    outRec["Type"] = sType
    outRec["NofShares"] = iNoShares
    outRec["PricePerShareInEuroMilliCent"] = mcentsPricePerShare
    outRec["BankChangeInEuroMilliCent"] = mcentsChangeAmount
    outRec["GebührenInEuroMilliCent"] = mFee
    outRec["ISIN"] = sIsin
    outRec["Name"] = sTitle2
    outRec["Comment"] = szProcessingComment
    if detEv is not None:
        processEvent(detEv, lColList2, lTypeList, outRec)

def writeRecord(fFile, lColList2 , outRecord2):
    j: int = 0
    iLength = len(lColList2)
    sTemp = ""
    while j < iLength:
        if sTemp != "":
            sTemp += ";"
        sTemp += str(outRecord2[lColList2[j]])
        j += 1
    # fFile.write(sTemp)


makeDetailsDictionary(timeline_det2=timeline_det, detailDict2=detailDict)
initCols(lColList2=lColList, lTypeList2=lTypeList)
# print(lColList)
# print(lTypeList)
ExtractColumns(lColList2=lColList, lTypeList2=lTypeList)
# print(lColList)
# print(lTypeList)

timelineEvent = timeline[0]
sTypeName: str = timelineEvent["type"]
if sTypeName != "timelineEvent":
    print("ERROR: Event types changed in timeline")
    exit()

# Write transactions.csv file
# date, transaction, shares, amount, total, fee, isin, name

iTotalCount = int(0)
iRoundingErrCount = int(0)

with open(envConsts.S_TRANSA_CSVFILE_PATH, "w") as f:
    # write Header

    outRecords = []
    for event in timeline:
        outRecord = {}
        sProcessingComment = ""
        event = event["data"]
        iTimestamp: int = event["timestamp"]
        sTimestamp: str = "\"'{0}\"".format(event["timestamp"])
        dateTime = datetime.fromtimestamp(int(event["timestamp"] / 1000))
        date: datetime = dateTime.strftime("%Y-%m-%d %H:%M:%S")
        tmID = event["id"]
        sBody = ""
        title = event["title"]

        try:
            body = event["body"]
            sBody = "\"{0}\"".format(body.replace("\n", "\\n").replace("\u20ac", "**"))
            sBody = sBody.replace("\ufffc", "**").replace(",", ".")
        except KeyError:
            body = ""

        detailEvZ = None
        try:
            detailEvZ = detailDict[tmID]
        except KeyError:
            detailEvZ = None

        # set Minimum known data
        initRecord(lColList, lTypeList, outRecord)

        szType: str = ""
        if title != "":
            szType = title  # The title is the type of transaction normally
        else:
            szType = sBody

        # This is Default Prep - later processing is overwriting it
        prepRecord(None, outRec=outRecord, tmId2=tmID, sTimestamp2=sTimestamp
            , szBody=sBody, date2=date, sType=szType, iNoShares="", mcentsPricePerShare=""
            , mcentsChangeAmount="", mFee="", sIsin="", sTitle2=sBody
            , szProcessingComment="Default Comment")

        # Cash in and out
        if (title == "Einzahlung"
                or title == "Auszahlung"):
                # TODO add entries for English
            tmpStr: str = str(event["cashChangeAmount"])
            cashChangeAmount: Decimal = Decimal(tmpStr)
            sOperation = "if this is output then there is error"
            if LOCALE == "de":
                if title == "Einzahlung":
                    sOperation = "Einlage"
                else:
                    sOperation = "Entnahme"
            else:
                if title == "Einzahlung":
                    sOperation = "Cash In"
                else:
                    sOperation = "Cash Out"

            prepRecord(detailEvZ, outRecord, tmID, sTimestamp , sBody
                , date
                , sOperation   # "Vorabpauschale",#"Pre-tax",
                , ""  # empty number of shares
                , ""  # empty price per share
                , inCurrencyType(cashChangeAmount)
                , ""  # no fee ... hopefully
                , ""  # isin
                , ""  # title
                , sProcessingComment)

            writeRecord(f, lColList, outRecord)

        elif ("Vorabpauschale" in body
              or "Steuerabrechnung" in title
        ):
            # pretax ...?!
            isin = getIsinFromStockName(title)
            tmpStr: str = str(event["cashChangeAmount"])
            cashChangeAmount: Decimal = Decimal(tmpStr)
            prepRecord(detailEvZ, outRecord, tmID, sTimestamp
                       , sBody
                       , date
                       , title
                       , ""
                       , ""
                       , inCurrencyType(cashChangeAmount)
                       , ""
                       , isin
                       , title
                       , sProcessingComment)
            # processEvent(detailEvZ, lColList, lTypeList, outRecord)
            writeRecord(f, lColList, outRecord)
        elif title == "Eintragung Aktienregister":
            # look for a company name inside the body
            # for some strange reason the title of the event is this time not
            #  even remotely the Company "loose" name
            sFoundName = ""
            for sCompanyName in fixedIsins:
                if sCompanyName in body:
                    sFoundName = sCompanyName
                    break
            if sFoundName != "":
                isin = getIsinFromStockName(sFoundName)
            else:
                isin = ""
            tmpStr: str = str(event["cashChangeAmount"])
            cashChangeAmount: Decimal = Decimal(tmpStr)

            prepRecord(detailEvZ, outRecord, tmID, sTimestamp , sBody
                , date
                , title  # sFoundName  # "Vorabpauschale",#"Pre-tax",
                , ""     # empty number of shares
                , ""     # empty price per share
                , inCurrencyType(cashChangeAmount)
                , inCurrencyType(cashChangeAmount)  # yes this is pure fee"", #fee?!
                , isin
                , sFoundName
                , sProcessingComment)
            # processEvent(detailEvZ, lColList, lTypeList, outRecord)
            writeRecord(f, lColList, outRecord)

            reportAndAddMissingISINs(isin, title, tmID, date)

        # Dividend - Shares
        # elif title == "Reinvestierung":
        #    # TODO: Implement reinvestment
        #    print("Detected reinvestment, skipping... (not implemented yet)")
        # Dividend - Cash
        elif "Gutschrift Dividende" in body or "Dividend per" in body:
            isin = getIsinFromStockName(title)
            amountPerShare = getDecimalFromString(body)
            tmpStr: str = str(event["cashChangeAmount"])
            cashChangeAmount: Decimal = Decimal(tmpStr)

            prepRecord(detailEvZ, outRecord, tmID, sTimestamp , sBody
                , date
                , "Dividende" if LOCALE == "de" else "Dividend"
                , ""  # empty number of shares
                , ""  # empty price per share
                , inCurrencyType(cashChangeAmount)
                , ""
                , isin
                , title
                , sProcessingComment)
            # processEvent(detailEvZ, lColList, lTypeList, outRecord)
            writeRecord(f, lColList, outRecord)
            reportAndAddMissingISINs(isin, title, tmID, date)

        # Savings plan execution or normal buy
        # OR Sell
        elif (
                body.startswith("Sparplan ausgeführt")
                or body.startswith("Kauf")
                or body.startswith("Limit Kauf zu")
                or body.startswith("Verkauf")
                or body.startswith("Limit Verkauf zu")
                or body.startswith("Savings Plan executed")
                or body.startswith("Buy order")
                or body.startswith("Limit Buy order")
        ):
            sOperation: str = ""  # to be re-merged for LOCAL
            if body.startswith("Kauf") or body.startswith("Limit Kauf zu"):
                sOperation = "Kauf" if LOCALE == "de" else "Buy"  # "Kauf"
                fee = -1.0
            elif body.startswith("Verkauf") or body.startswith("Limit Verkauf zu"):
                sOperation = "Verkauf" if LOCALE == "de" else "Buy"  # "verk"
                fee = -1.0
            else:
                sOperation = "Kauf"
                fee = 0
            isin = getIsinFromStockName(title)
            amountPerShare: Decimal = (getDecimalFromString(body))  # .copy_abs())
            tmpStr: str = str(event["cashChangeAmount"])
            cashChangeAmount: Decimal = Decimal(tmpStr)  # .copy_abs()
            netCash: Decimal = Decimal(cashChangeAmount - Decimal(fee))  # the amount is always
            shares: Decimal = (netCash / amountPerShare)
            intShares: int = int(round(shares))
            iTotalCount = iTotalCount + 1
            if netCash.compare(Decimal(intShares) * amountPerShare) != 0:
                iRoundingErrCount = iRoundingErrCount + 1
                # print("WARNING: Rounding Error")  # should be an ASSERT(FALSE);
                sProcessingComment = "{0} !=  {1} * {2} DIFF is: {3} @ {4} | {5} {6}".format(
                    netCash, intShares, amountPerShare, netCash - (Decimal(intShares) * amountPerShare), date, title,
                    isin)
                # print(sProcessingComment)

            prepRecord(detailEvZ, outRecord, tmID, sTimestamp , sBody
                , date
                , sOperation
                , intShares
                , inCurrencyType(amountPerShare)
                , inCurrencyType(cashChangeAmount)
                , inCurrencyType(fee)
                , isin
                , title
                , sProcessingComment)
            # processEvent(detailEvZ, lColList, lTypeList, outRecord)
            writeRecord(f, lColList, outRecord)

            reportAndAddMissingISINs(isin, title, tmID, date)

        elif (  # b100
              body.startswith("Limit Kauf-Order storniert")
              or body.startswith("Limit Kauf-Order ausgelaufen")
              or body.startswith("Hauptversammlung")
              or title.startswith("E-Mail bestätigt")
              or title.startswith("Ex-Post Kosteninformation")  # Only informative according to the TR site
              # https://support.traderepublic.com/de-de/133-Was-ist-die-Ex_Post-Kosteninformation
              or title.startswith("Unterlagen Aktualisierung")
              or body.startswith("Limit Verkauf-Order ausgelaufen")
              or "storniert" in body
        ):
            bFail: bool = True
            try:  # by definition this MUST fail. Otherwise, we MUST not ignore this line
                tmpStr: str = str(event["cashChangeAmount"])
            except KeyError:
                bFail = False
            if bFail:
                print("ERROR: unhandled JSON Entry with ***_cashChangeAmount_ = {3}***\n    from {2} {0} | {1}".format(
                    title, body, date, tmpStr))
                exit(-1)
                sFoundName = ""
            sFoundName = ""
            for sCompanyName in fixedIsins:
                if sCompanyName in body:
                    sFoundName = sCompanyName
                    break
            if sFoundName != "":
                isin = getIsinFromStockName(sFoundName)
            else:
                isin = ""

            prepRecord(detailEvZ, outRecord, tmID, sTimestamp , sBody
                           , date
                           , sBody  # ,  title
                           , ""
                           , ""
                           , ""
                           , ""
                           , isin
                           , title
                           , "b100 Default comment")

        elif tmID in entriesToIgnorePre:
            bFail: bool = True
            try:  # by definition this MUST fail. Otherwise, we not ignore this line
                tmpStr: str = str(event["cashChangeAmount"])
            except KeyError:
                tmpStr = ""  # defence
                bFail = False
            if bFail:
                print("ERROR: IGNORED ENTRY with ***_cashChangeAmount_***\n    from {2} {0} | {1} |{3}".format(title,
                                                                                                               body,
                                                                                                               date,
                                                                                                               tmID))
                print("       cashChangeAmount = {0}".format(tmpStr))
                print("       CORRECT YOUR ignoredEntries.json file!!!")
                print("       FAILING TO FIX THIS MAY RESULT IN UNBALANCED CALCULATIONS\n")
                print("************************* ERROR \n")
                exit(-1)
        else:
            sRecommendedEntryComment = "title {0} | body {1} | datetime: {2} unhandled JSON ENTRY".format(title, body,
                                                                                                         date)
            entriesToIgnore[tmID] = sRecommendedEntryComment
            print("WARNING: guid \"{0}\": \"{1}\"".format(tmID, sRecommendedEntryComment))

        outRecords.append(outRecord)

    reorderColumns(lColList2=lColList, lTypeList2=lTypeList)
    # now write the file from memory to disk

    # write Header
    sOutStr = ""
    i = 0
    length = len(lColList)
    while i < length:
        if sOutStr != "":
            sOutStr += ";"
        sOutStr += lColList[i]
        i += 1
    f.writelines("{0}\n".format(sOutStr))

    # write rows
    for eRec in outRecords:
        i = 0
        sOutStr = ""
        length = len(lColList)
        while i < length:
            if i > 0:
                sOutStr += ";"
            sOutStr += str(eRec[lColList[i]])
            i += 1
        f.writelines("{0}\n".format(sOutStr))
    f.close()

if len(missingIsins.keys()) > 0:
    print("=======================================================\n")
    print("--- MISSING ISINs ---")
    print("=======================================================\n")
    print(json.dumps(missingIsins, indent="\t", sort_keys=True))
    print("=======================================================\n")
    print("***>Add ISINs to companyNameIsins.json and start again\n")
if len(entriesToIgnore.keys()) > 0:
    print("=======================================================\n")
    print("--- Entries That are suggested to be ignored ---")
    print("=======================================================\n")
    print(json.dumps(entriesToIgnore, indent="\t", sort_keys=False))
    print("=======================================================\n")
    print("***> Add these to your ignoredEntries.json file after checking each of them\n")

print("=======================================================\n")
print("TotalCount:{0} RoundingCount: {1}\n".format(iTotalCount, iRoundingErrCount))

with open(envConsts.S_TIMELD_FLATJSNFILE_PATH, "w", encoding="utf-8") as f2:
    f2.write(json.dumps(outRecords, indent="\t", sort_keys=False))

print("********* Finished! *********")
print("*****************************")
