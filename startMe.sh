
source venv/bin/activate

echo "* 1st: timeline and AND documents extraction from Trade Republic."
echo "*      NEEDS to login to trade republic"
echo "********************************************************************"
python3 ./examples/timelineExporterWithDocsAndDetails.py

echo " "
echo "********************************************************************"
echo "* 2nd: Generate a CSV file from the data extracted above"
echo "*      DOES _NOT_ NEED to login to trade republic"
echo "********************************************************************"
# not done yet
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
