# Check the portfolio total profit and a telegram message


import sys

sys.path.append("../")


import json
import time
from datetime import datetime

from pandas import json_normalize

import requests
import time
import hashlib
from   urllib.request import urlopen, Request

from trapi.api import TrBlockingApi
from environment import *

exec(open("telegram_bot.py").read())
# set telegram bot_token, bot_chatID


tr = TrBlockingApi(NUMBER, PIN, locale=LOCALE)
tr.login()

# check portfolio for a specific variable
def check_portfolio(portfolioVariable):
	
	portfolio      = tr.portfolio()
	portfolioValue = portfolio[portfolioVariable]
	
	return(portfolioValue)
	
# filter and calculate total for a specific variable
def check_hist(histVariable, histVariableSum):
	
	hist = tr.hist()
	hist = json_normalize(hist['data'])
	hist = hist[hist['data.title'] == histVariable]
	
	histSum = sum(hist[histVariableSum])
	
	return(histSum)	

# alert in telegram chat
def send_telegram_alert(payload, bot_token, bot_chatID):

   telegram_bot_sendtext(str(alert), bot_token, bot_chatID)


portfolioVariable = 'unrealisedProfit'
histVariable      = 'Cash In'
histVariableSum   = 'data.cashChangeAmount'

profit = check_portfolio(portfolioVariable)

cashIn = check_hist(histVariable, histVariableSum)



alert = str(datetime.now()) + ' Profit: '  + str(round(profit - cashIn ,2)) + ' EUR'
   
send_telegram_alert(alert)
   


 

