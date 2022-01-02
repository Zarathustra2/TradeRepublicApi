####################################################################################################################
# PREREQUISITES:
#     0. environment_template.py to environment.py and fill the correct data
#     1. MUST HAVE PYTHON 3 installed
#     2. PERFORM: pip install -r requirements.txt
#     3. Has been tested only on Linux - Sorry
#
# USAGE:
#
#     python3 ./examples/timelineExporterWithDocsAndDetails.py
#
#     INFO 1:
#       When used for the very first time ypu will be asked for a 4-digit code that is sent to you with and SMS.
#       Giving this 4-digit code will disconnect your mobile app and connect/pair this set of Python scripts
#       to your Trade republic account. To reconnect back to your mobile app (or any other istallation) you
#       must pair the device again.
#     INFO 2:
#       Output files will reside in folders configured in envConsts.py file
####################################################################################################################

import sys
sys.path.append("../")
sys.path.append("trapi/")
sys.path.append("example/")
from api import TrBlockingApi
from api import TRapiExcServerErrorState
from environment import *
from envConsts import *
import json
import time
import os
import uuid
import requests  # to download documents

RUN_GUID = str(uuid.uuid4())


class TRunner:
    iRemainingRetries: int = 5

    def __init__(self):
        self.data = []
        self.after = ""
        self.dataEvDetails = []
        self.iCounter: int = 0
        self.iCounterEntries: int = 0
        self.dataEvDetails = []
        self.bRepeat: bool = False
        self.tr = TrBlockingApi(NUMBER, PIN, locale="de")
        self.tr.login()

    def InitMe(self):
        self.__init__()

    @staticmethod
    def SaveOldOutput(sFolderPath: str, sFName: str, riid: str, sNewExt: str) -> None:
        sBkpDir = "{0}_bckp/".format(sFolderPath)
        sNewFileName = "{0}{1}.{2}.{3}".format(sBkpDir, sFName, riid, sNewExt)
        sFileName = sFolderPath + sFName
        try:  # rename old files to store them just in case
            os.makedirs(sBkpDir, exist_ok=True)
            os.rename(sFileName, sNewFileName)
            print("\tINFO: File ""{0}"" renamed to ""{1}""".format(sFileName, sNewFileName))
        except Exception as e:
            print(e)
            print("\tWARNING: Old output file cannot be saved ""{0}"" renamed to ""{1}""".format(sFileName, sNewFileName))
        return None

    @staticmethod
    def getRecommendPrefix(d2) -> str:
        sRecommendPrefix: str = ""
        try:
            titleText = d2["titleText"]
            sRecommendPrefix = titleText.replace(" ", "").replace("-", "_").replace("/", "").replace(".", "_")
            sRecommendPrefix = sRecommendPrefix.replace("(", "").replace(")", "").replace("&", "")
        except Exception:
            pass
        return sRecommendPrefix

    @staticmethod
    def downloadFiles(d2Pack: any, sTitlePrefix: str):
        try:
            for d_section in d2Pack["sections"]:
                if d_section["type"] == "documents":
                    for d_docLine in d_section["documents"]:
                        sTitle = ""
                        try:
                            sTitle = d_docLine["title"]
                        except Exception:
                            pass
                        # makesure that this is legal for a file name char even though international chars are accepted by all OSes now
                        sTitle = sTitle.lower()
                        sTitle = sTitle.replace("ö", "oe").replace("ü", "ue").replace("ä", "ae").replace("\n", "_")

                        sDateZ = ""
                        try:
                            sDateZ = d_docLine["detail"]
                        except Exception:
                            pass
                        # makesure that this is leagal for a file name char
                        sDateZ = sDateZ.replace(".", "-").replace("/", "-").replace("\\", "-").replace(":", "-")

                        if d_docLine["action"]["type"] == "browserModal":
                            sActionCommand = d_docLine["action"]["payload"]

                            sFileNameFound = ""
                            sPart1 = ""
                            iPlace = sActionCommand.find(".pdf")
                            if iPlace != -1:
                                try:
                                    sFileNameFound = sActionCommand
                                    # remove the final ".pdf and replace chars that will be used later"
                                    sFileNameFound = sFileNameFound[(iPlace - (47 + 4)): iPlace].replace("-", "")
                                    sFileNameFound = sFileNameFound.replace(" ", "")

                                    # trailing
                                    iCountZ = 0
                                    while iCountZ < 6 and not sFileNameFound[iCountZ].isdigit():
                                        iCountZ += 1
                                    if sFileNameFound[iCountZ].isdigit():
                                        if "0" == sFileNameFound[iCountZ]:
                                            iCountZ += 1  # remove a trailingZero if such
                                        sFileNameFound = sFileNameFound[iCountZ:]
                                    else:
                                        pass

                                    sFileNameFound = sFileNameFound.replace("\\", "-").replace("/", "-").replace(".",
                                                                                                                 "-")

                                    if not (sFileNameFound[5].isdigit() and sFileNameFound[6].isdigit()):
                                        sFileNameFound = sFileNameFound.replace("-", "0", 1)
                                    else:
                                        sFileNameFound = sFileNameFound.replace("-", "", 1)  # delete the "-"

                                    if not (sFileNameFound[7].isdigit() and sFileNameFound[8].isdigit()):
                                        sFileNameFound = sFileNameFound.replace("-", "0", 1)
                                    else:
                                        sFileNameFound = sFileNameFound.replace("-", "", 1)  # delete the "-"

                                    sPart1 = sFileNameFound[:8]
                                    sFileNameFound = sFileNameFound[10 + 8:]
                                except Exception:
                                    print("***************** ERROR WHEN PARSING ***************")

                                sFileNameFound = sFileNameFound.replace(" ", "-")  # remove all spaces
                                sFileNameBase = S_DOCDOWNLOADS_PATH + sPart1 + "_" + sTitlePrefix + "_" + sFileNameFound
                                if sTitle != "":
                                    sTitle = sTitle.replace("  ", "-").replace(" ", "-").replace(",", "")
                                    sFileNameBase += "_" + sTitle
                                if sDateZ != "":
                                    sDateZ = sDateZ.replace("  ", "-").replace(" ", "-").replace(",", "")
                                    sFileNameBase += "_" + sDateZ

                                sFileNameBase = sFileNameBase.replace("\n", "_")

                                sFileName = sFileNameBase + ".pdf"
                                sFileNameTx = sFileNameBase + ".txt"
                                if not os.path.isfile(sFileName):
                                    ra = requests.get(sActionCommand, allow_redirects=True)
                                    open(sFileName, 'wb').write(ra.content)
                                    open(sFileNameTx, 'w', encoding='utf-8').writelines(sActionCommand)
                            else:
                                print("Warning: ***************** IGNORING NON PDF DOCUMENTS?! ***************")
        except Exception as exError:
            print(exError)
            print("ERROR: Unexpected Failure while getting pdf Documents\n PROBABLY NEED TO CREATE A FOLDER")
            exit()

    def Run(self):
        self.InitMe()
        os.makedirs(S_DOC_DOWNLOADS, exist_ok=True)
        try:
            TRunner.iRemainingRetries = 5
            bCursorFinished = False
            while not bCursorFinished:
                res = self.tr.hist(after=self.after)
                self.bRepeat = False

                self.iCounter += 1
                print("No. {0} **************".format(self.iCounter))

                for d in res["data"]:
                    self.data.append(d)

                    # s = json.dumps(d, indent="\t")
                    self.iCounterEntries += 1
                    guidEv = d["data"]["id"]
                    # print(guidEv)
                    # print("**>ENTRY No.{0} ****** {1}".format(iCounterEntries, guidEv))

                    try:
                        try:
                            oAction = d["data"]["action"]  # if here we throw an exception then it is as expected
                        except KeyError:
                            pass
                        except Exception:
                            pass
                        else:
                            guidEv2 = oAction["payload"]
                            sType = oAction["type"]
                            if sType == "timelineDetail":
                                assert (guidEv2 == guidEv)
                                d2 = self.tr.hist_event(guidEv2)
                                if d2 is not None:
                                    d2Pack = d2
                                    self.dataEvDetails.append(d2Pack)
                                    sRecommendPrefix = TRunner.getRecommendPrefix(d2)
                                    TRunner.downloadFiles(d2Pack, sRecommendPrefix)
                            else:
                                print("WARNING: new type of action {0}".format(sType))
                    except TRapiExcServerErrorState as eExx:
                        if TRunner.iRemainingRetries == 0:
                            print(" ****  ")
                            raise eExx
                        self.bRepeat = True
                        TRunner.iRemainingRetries -= 1
                        print("****will retry")
                        print(eExx)
                    if self.bRepeat:
                        break
                # end  of for

                if self.bRepeat:
                    sTemp = "\t*** Starting over - remaining Retries {0}\n\tup to {1} will go faster"
                    print(sTemp.format(TRunner.iRemainingRetries, self.iCounter))
                    time.sleep(5)
                    self.InitMe()
                else:
                    tmp = res["cursors"]
                    try:
                        self.after = tmp["after"]
                        time.sleep(1)
                    except KeyError:
                        bCursorFinished = True
                #while loop

        except Exception as ExErr:
            # print(ExErr)
            print("ExPrint")
            print(ExErr)
        else:
            # Write JSON files
            TRunner.SaveOldOutput(S_OUTPUT_DIR, S_TIMELN_JSNFILE, RUN_GUID, "json")
            with open(S_TIMELN_JSNFILE_PATH, "w") as f:
                json.dump(self.data, f, indent="\t")
                print("\tSUCCESS: Events JSON File written{0}\n".format(S_TIMELN_JSNFILE_PATH))

            TRunner.SaveOldOutput(S_OUTPUT_DIR, S_TIMELD_JSNFILE, RUN_GUID, "json")
            with open(S_TIMELD_JSNFILE_PATH, "w") as f:
                json.dump(self.dataEvDetails, f, indent="\t")
                print("\tSUCCESS: Details for Events JSON File written{0}\n".format(S_TIMELN_JSNFILE_PATH))

            print(" DONE: ************   finished EXPORTING!  ************ ")

r = TRunner()
r.Run()