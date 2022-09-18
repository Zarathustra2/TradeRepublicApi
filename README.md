## Addendum to Export _Trade Republic_ Timeline as Excel(csv) 

This section only explains a specific use-case, which has been tested in the examples folder. 

**The rest of the readme is intentionally not modified.**

### Steps to use

Important note: This use case is tested on Linux, python 3.8 and 
with German Language only.

 - Update the ```./examples/envConsts.py``` file with appropriate path(s).
 - copy ```environment_template.py``` to ```environment.py``` and change it to match your TR account.
 - See the ```StartMe.sh``` linux command-line script for how it is used further.

---

## Trade Republic API

This is an unofficial API for the German broker Trade Republic.

Unfortunately the previous owner has made his repo private. This is meant to be a follow-up repo, more features to be added in the future.

Currently, this can be used to try out algorithmic trading or learning how to process a lot of data.

Trade Republic only allows one device to be registered at the same time. So if you are currently logged in on your phone it will log you out from your phone.

Also running it the first time will likely error but then running it for the second time will work. Have to debug this but not much time.

## Example blocking history
```python3
from api import TrBlockingApi

# This will go through your most recent history events
# and print it on the terminal
def main():

    tr = TrBlockingApi(NUMBER, PIN)
    tr.login()

    res = tr.hist()
    print(res.keys())
    for x in res["data"]:
        print(tr.hist_event(x["data"]["id"]))
```


## Example async
```python3

def process(json_data):
    print("I am a processor: ", json_data)

async def main():
    tr = TRApi(NUMBER, PIN)
    tr.login()

    # Each callback can be specified 
    # if wanted, default is print
    await tr.cash(callback=lambda x: print(f"Cash data: {x}"))
    await tr.portfolio()

    isin = "US62914V1061"
    await tr.derivativ_details(isin)
    await tr.stock_details(isin)
    await tr.ticker(isin, callback=process)
    await tr.news(isin) 
    
    await tr.start()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
```

# JSON Format
## Dividende
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "1512453d-1880-4b46-ac4e-2a8ee3f97187",
		"timestamp": 1616811300786,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/Dividend.png",
		"title": "Stock XYZ",
		"body": "Gutschrift Dividende pro Aktie von 0,40 USD",
		"cashChangeAmount": 1.97,
		"action": {
			"type": "timelineDetail",
			"payload": "1512453d-1880-4b46-ac4e-2a8ee3f97187"
		},
		"attributes": [

		],
		"month": "2021-03"
	}
}
```

## Einzahlung
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "7f854148-4278-45f3-8c99-e2f7059ab70c",
		"timestamp": 1616660487759,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/CashIn.png",
		"title": "Einzahlung",
		"body": "Geldeingang vom Konto\nDE32120300001032514893",
		"cashChangeAmount": 100.0,
		"attributes": [

		],
		"month": "2021-03"
	}
}
```

## Auszahlung
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "f4d62473-d4ed-485a-b56e-7c0509c04701",
		"timestamp": 1617126782673,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/CashOut.png",
		"title": "Auszahlung",
		"body": "Geldausgang an Dein\nReferenzkonto",
		"cashChangeAmount": -5.0,
		"attributes": [

		],
		"month": "2021-03"
	}
}
```

## Sparplan Ausführung
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "91a39f02-376b-4fd7-a3c4-05a3cd1e52ba",
		"timestamp": 1615910518967,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/SavingsPlanExecuted.png",
		"title": "Stock XYZ",
		"body": "Sparplan ausgef\u00fchrt zu 156,86 \u20ac",
		"cashChangeAmount": -9.99,
		"action": {
			"type": "timelineDetail",
			"payload": "91a39f02-376b-4fd7-a3c4-05a3cd1e52ba"
		},
		"attributes": [

		],
		"month": "2021-03"
	}
}
```

## Kauf
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "67ce42be-ec6a-4e97-bb1e-e4eac899bb4f",
		"timestamp": 1616690513004,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/Arrow-Right.png",
		"title": "Stock XYZ",
		"body": "Kauf zu 50,99 \u20ac",
		"cashChangeAmount": -51.99,
		"action": {
			"type": "timelineDetail",
			"payload": "67ce42be-ec6a-4e97-bb1e-e4eac899bb4f"
		},
		"attributes": [

		],
		"month": "2021-03"
	}
}
```

## Verkauf
```json
{
	"type": "timelineEvent",
	"data": {
		"id": "3265a78b-4738-419a-88a5-f8d3f5cc914d",
		"timestamp": 1617008391425,
		"icon": "https://assets.traderepublic.com/img/icon/timeline/Arrow-Left.png",
		"title": "Stock XYZ",
		"body": "Limit Verkauf zu 265,30 \u20ac\nRendite: \ufffc 22,20 %",
		"cashChangeAmount": 123.4,
		"action": {
			"type": "timelineDetail",
			"payload": "3265a78b-4738-419a-88a5-f8d3f5cc914d"
		},
		"attributes": [
			{
				"location": 35,
				"length": 9,
				"type": "positiveChange"
			}
		],
		"month": "2021-03"
	}
}
```
