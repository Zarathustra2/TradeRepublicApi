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

## Logging in

Trade Republic retired the device login this library used to rely on:
`/api/v1/auth/login` answers with HTTP 426 `CLIENT_VERSION_OUTDATED` and the
device registration is no longer served. The library uses the web login
instead, which keeps its state in cookies rather than in a signed token.

Trade Republic asks for a second factor. Newer accounts get a push
notification that has to be approved in the app, older ones an SMS.

```python3
tr = TrBlockingApi(NUMBER, PIN)

# Approval in the app: blocks until you confirm the push notification
tr.login()

# Code by SMS
tr.login(code="123456")
```

For more control over the steps:

```python3
data = tr.start_login()                              # triggers the second factor
tr.await_login_confirmation(data["processId"])       # waits for the app
# or
tr.verify_login(data["processId"], "123456")         # confirms with a code
```

Unlike the old device login, the web session does **not** log you out of the
app - both can be active at the same time.

### Keeping the session alive

Trade Republic drops the session after a few minutes without traffic. Both
APIs take care of that on their own:

- `TRApi.start()` extends the session in the background while it runs.
- `TrBlockingApi` extends it before a request when little time is left,
  because nothing runs in between two blocking calls.

So the usual case needs no attention. To do it yourself:

```python3
tr = TrBlockingApi(NUMBER, PIN, keep_session=False)
...
tr.refresh_session()               # extend it now
tr.refresh_session_if_needed()     # extend it if the end is near
tr.session_expires_in              # seconds the session should still last
```

`TRApi.start(keep_session=False)` does the same for the async API. Once the
session is gone for good, `refresh_session()` raises `TRapiExcSessionExpired`,
which says a new login is needed rather than that something went wrong on the
way.

How long a session lasts is not documented. `TRApi.session_lifetime` holds the
assumption the refresh is scheduled against and errs on the careful side;
raise or lower it if you measure something else.

The methods of the old flow (`device_login()`, `register_new_device()`,
`do_request()`) are kept but deprecated.

## Installation

```
pip install .
```

The scripts in `examples/` additionally need `pip install .[examples]`.

## API compatibility

Trade Republic changes its backend without notice. The state below was verified
against the live API in August 2026.

### Websocket protocol version

The `connect` frame carries a protocol version. Versions below 26 are refused
with `failed <latest supported version>` - this is the cause of the
`Connection Error: failed 30` / `failed 32` reports. The library sends version
31 by default and accepts an override:

```python3
tr = TrBlockingApi(NUMBER, PIN, connect_version=34)
```

### Renamed and removed subscriptions

| removed | use instead |
| --- | --- |
| `portfolio`, `compactPortfolio` | `compact_portfolio_by_type()` |
| `timeline` | `timeline_transactions()`, `timeline_activity_log()` |
| `timelineDetail` | `timeline_detail()` (now sends `timelineDetailV2`) |
| `timelineActions` | `timeline_actions_v2()` |
| `instrumentExchange` | `home_instrument_exchange()` |

Removed without a replacement, the server answers them with
`BAD_SUBSCRIPTION_TYPE`: `portfolioAggregateHistory`,
`portfolioAggregateHistoryLight`, `neonCards`, `messageOfTheDay`,
`instrumentSuitability`, `frontendExperiment`, `settings`, `bondDetails`,
`subscribeNews`, `unsubscribeNews`, `newsSubscriptions`, `confirmOrder`,
`orderOverview`, `stockOrderDetails` and `cashAvailableForOrder`. The
corresponding methods are kept but marked as deprecated.

### Newly wired up

`performance()`, `etf_details()`, `etf_composition()`, `crypto_details()`,
`savings_plans()`, `watchlists()`, `trading_perk_condition_status()` and
`timeline_actions_v2()`.

### Other behaviour worth knowing

- `aggregate_history_light()` no longer sends a `resolution` by default. The
  server silently discards subscriptions that carry one, so the request would
  simply never be answered.
- Prices are now delivered as JSON strings (`"265.5"`) rather than numbers.

## Tests

The offline tests drive the client against a fake websocket and need no
account:

```
make test
```

`make test-live` additionally runs smoke tests against the real API, using only
the topics that are served without a token.

## Example blocking history
```python3
from api import TrBlockingApi

# This will go through your most recent history events
# and print it on the terminal
def main():

    tr = TrBlockingApi(NUMBER, PIN)
    tr.login()

    res = tr.timeline()
    print(res.keys())
    for x in res["data"]:
        print(tr.timeline_detail(x["data"]["id"]))
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
    await tr.instrument(isin)
    await tr.stock_details(isin)
    await tr.ticker(isin, callback=process)
    await tr.neon_news(isin) 
    
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
