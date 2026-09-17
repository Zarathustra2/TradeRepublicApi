#!/bin/sh
echo "* this Python VENV is not required but _strongly_ recommended"
source venv/bin/activate

echo "********************************************************************"
echo "* 1st: export the timeline, its details and the documents"
echo "*      NEEDS to log in to Trade Republic"
echo "*      Approve the notification in the app when one appears."
echo "*      Documents go into ./_docDownloads and are only fetched once,"
echo "*      so keeping the folder makes every later run cheap."
echo "********************************************************************"
python3 ./examples/timelineExporterWithDocsAndDetails.py

echo " "
echo "********************************************************************"
echo "* 2nd: generate the CSV from what was exported above"
echo "*      DOES _NOT_ need to log in to Trade Republic"
echo "*      Entries the converter does not recognise are listed at the"
echo "*      end instead of being dropped silently."
echo "********************************************************************"
python3 ./examples/timelineCsvConverter.py

echo " "
echo "********************************************************************"
echo "* 3rd: save the files to a permanent location"
echo "*      DOES _NOT_ need to log in to Trade Republic"
echo "********************************************************************"
#cp -u ./myTransactions.csv ~/OneDrive/000.10.WorkDay/21C.Dec.2021/
#cp -R -u ./_docDownloads/  ~/OneDrive/500.025.Banks/_tradeRepAutoExport/
