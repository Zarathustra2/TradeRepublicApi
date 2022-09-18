echo "* this Python VENV is not required but _strongly_ recommended"
source venv/bin/activate

echo "* 1st: timeline and AND documents extraction from Trade Republic."
echo "*      NEEDS to login to trade republic"
echo "* NOTE: the script will download the complete timeline as JSON"
echo "*       Documents are stored in a relative path as per envConsts.py"
echo "*       Thus, if the folder is not cleared each run will download"
echo "*       only new documents"
echo "********************************************************************"
python3 ./examples/timelineExporterWithDocsAndDetails.py

echo " "
echo "********************************************************************"
echo "* 2nd: Generate a CSV file from the data extracted above"
echo "*      DOES _NOT_ NEED to login to trade republic"
echo "*      - new entries, which you can copy paste to your" 
echo "*        ignoredEntries.json file will be generated. it is suggested"
echo "*        that you add paste them there _only_  after you are sure that"
echo "*        no additional processing is needed"
echo "*      - new entries, which you can copy paste to your"
echo "*        companyNameIsins.json file will also be generated"
echo "* Recommended is that you create a private repo in which you keep these files"
echo "********************************************************************"
python3 ./examples/timelineCSVconvWithDetails.py 

# python3 ./examples/timelineExporterWithDocsAndDetails.py
# save the files somewhere
echo " "
echo "********************************************************************"
echo "* 3rd: Save files to permanent location, if directories does not exist this step will fail"
echo "*      Only changed and new files will be copied"
echo "*      DOES _NOT_ NEED to login to trade republic"
echo "********************************************************************"
#cp -R -u ./_storedOutputs/myTransactions.csv ~/OneDrive/000.10.WorkDay/21C.Dec.2021/
#cp -R -u ~/_prj/trRep5/_docDownloads/  ~/OneDrive/500.025.Banks/_tradeRepAutoExport/
