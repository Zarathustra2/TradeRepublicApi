from ecdsa import NIST256p, SigningKey
from ecdsa.util import sigencode_der
import base64
import hashlib
import time
import requests
import asyncio
import websockets
from deprecated import deprecated

import os

import json


class TRapiException(Exception):
    pass


class TRapiExcServerErrorState(TRapiException):
    pass


class TRapiExcServerUnknownState(TRapiException):
    pass


class TRApi:
    url = "https://api.traderepublic.com"

    # Protocol version sent with the websocket "connect" frame. Trade Republic
    # rejects outdated versions with "failed <latest>". As of 2026-08 the
    # server accepts 26 - 34; anything outside that range is refused.
    connect_version = 31

    # The server validates the client identification sent along with the
    # handshake, so it has to look like one of the official frontends.
    connect_payload = {
        "platformId": "webtrading",
        "platformVersion": "chrome - 94.0.4606",
        "clientId": "app.traderepublic.com",
        "clientVersion": "5582",
    }

    def __init__(self, number, pin, locale='en', connect_version=None):
        self.number = number
        self.pin = pin
        self.locale = locale
        if connect_version is not None:
            self.connect_version = connect_version
        self.signing_key = None
        self.ws = None
        self.sessionToken = None
        self.refreshToken = None
        self.mu = asyncio.Lock()
        self.started = False

        types = ["cash", "portfolio", "availableCash"]

        self.dict = {str(k): str(v) for v, k in enumerate(types)}

        self.callbacks = {}

        self.latest_response = {}

    def register_new_device(self, processId=None):
        self.signing_key = SigningKey.generate(curve=NIST256p, hashfunc=hashlib.sha512)
        if processId is None:
            r = requests.post(
                f"{self.url}/api/v1/auth/account/reset/device",
                json={"phoneNumber": self.number, "pin": self.pin},
            )

            bFailed = False
            try:
                processId = r.json()["processId"]
            except KeyError:
                bFailed = True

            if bFailed:
                raise Exception(f"Cannot Login! Details: {r.text}")
            else:
                print(f"*** The process id is: {processId}")

        pubkey = base64.b64encode(
            self.signing_key.get_verifying_key().to_string("uncompressed")
        ).decode("ascii")

        token = input("Enter your token: ")

        r = requests.post(
            f"{self.url}/api/v1/auth/account/reset/device/{processId}/key",
            json={"code": token, "deviceKey": pubkey},
        )

        if r.status_code == 200:
            key = self.signing_key.to_pem()
            with open("key", "wb") as f:
                f.write(key)

            return key
        else:
            print("no")

    def login(self, **kwargs):

        res = None
        if os.path.isfile("key"):
            res = self.do_request(
                "/api/v1/auth/login",
                payload={"phoneNumber": self.number, "pin": self.pin},
            )

        # The user is currently signed in with a different device
        if res == None or (
                res.status_code == 401
                and not kwargs.get("already_tried_registering", False)
        ):
            self.register_new_device()
            res = self.login(already_tried_registering=True)

        if res.status_code != 200:
            print(res.json(), res.status_code)
            raise TRapiException("could not login - see printed status_code")

        data = res.json()
        self.refreshToken = data["refreshToken"]
        self.sessionToken = data["sessionToken"]

        if data["accountState"] != "ACTIVE":
            raise TRapiException("Account not active")

        return res

    async def sub(self, payload_key, callback, **kwargs):
        if self.ws is None:
            self.ws = await websockets.connect("wss://api.traderepublic.com")
            msg = json.dumps(dict(self.connect_payload, locale=self.locale))
            await self.ws.send(f"connect {self.connect_version} {msg}")
            response = await self.ws.recv()

            if not response == "connected":
                # The server answers "failed <version>" when the protocol
                # version is no longer supported.
                raise TRapiException(
                    f"Connection Error: {response} "
                    f"(sent protocol version {self.connect_version})"
                )

        payload = kwargs.get("payload", {"type": payload_key})
        # Only authenticated topics expect a token. Sending "token": null makes
        # the server reject some public topics with a JSON_PARSE_ERROR.
        if self.sessionToken is not None:
            payload["token"] = self.sessionToken

        key = kwargs.get("key", payload_key)
        id = self.type_to_id(key)
        if id is None:
            async with self.mu:
                id = str(len(self.dict))
                self.dict[key] = id

        await self.ws.send(f"sub {id} {json.dumps(payload)}")

        self.callbacks[id] = callback

    def do_request(self, path, payload):

        if self.signing_key is None:
            with open("key", "rb") as f:
                self.signing_key = SigningKey.from_pem(
                    f.read(), hashfunc=hashlib.sha512
                )

        timestamp = int(time.time() * 1000)

        payload_string = json.dumps(payload)

        signature = self.signing_key.sign(
            bytes(f"{timestamp}.{payload_string}", "utf-8"),
            hashfunc=hashlib.sha512,
            sigencode=sigencode_der,
        )

        headers = dict()
        headers["X-Zeta-Timestamp"] = str(timestamp)
        headers["X-Zeta-Signature"] = base64.b64encode(signature).decode("ascii")
        headers["Content-Type"] = "application/json"
        return requests.request(
            method="POST", url=f"{self.url}{path}", data=payload_string, headers=headers
        )

    async def get_data(self):
        return await self.ws.recv()

    # list of requests: https://github.com/J05HI/pytr
    # -----------------------------------------------------------

    exchange_list = ["LSX", "TDG", "LUS", "TUB", "BHS", "B2C"]
    range_list = ["1d", "5d", "1m", "3m", "1y", "max"]
    instrument_list = ["stock", "fund", "derivative", "crypto"]
    jurisdiction_list = ["AT", "DE", "ES", "FR", "IT", "NL", "BE", "EE", "FI", "IE", "GR", "LU", "LT",
                         "LV", "PT", "SI", "SK"]
    expiry_list = ["gfd", "gtd", "gtc"]
    order_type_list = ["buy", "sell"]

    # todo accruedInterestTermsRequired

    async def add_to_watchlist(self, id, callback=print):
        """addToWatchlist request"""
        return await self.sub(
            "addToWatchlist",
            payload={"type": "addToWatchlist", "instrumentId": id},
            callback=callback,
            key=f"addToWatchlist {id}"
        )

    async def aggregate_history_light(self, isin, range="max", resolution=None, exchange="LSX", callback=print):
        """aggregateHistoryLight request

        No login required

        :param isin: the stock's isin
        :param range: the range to display ("1d", "5d", "1m", "3m", "1y", "max")
        :param resolution: the resolution in milliseconds. Defaults to None,
            which lets the server pick a resolution matching the range. Note
            that the server silently discards the subscription for most
            explicit values, so the request never gets an answer.
        :param exchange: the exchange the instrument is traded at
        :param callback: callback function
        :return: stock history
        """
        if range not in self.range_list:
            raise TRapiException(f"Range of time must be either one of {self.range_list}")

        if exchange not in self.exchange_list:
            raise TRapiException(f"exchange must be either one of {self.exchange_list}")

        payload = {"type": "aggregateHistoryLight",
                   "range": range,
                   "id": f"{isin}.{exchange}"}
        if resolution is not None:
            payload["resolution"] = resolution

        return await self.sub(
            "aggregateHistoryLight",
            payload=payload,
            callback=callback,
            key=f"aggregateHistoryLight {isin} {exchange} {range}",
        )

    async def available_cash(self, callback=print):
        """availableCash request"""
        await self.sub("availableCash", callback)

    async def available_cash_for_payout(self, callback=print):
        """availableCashForPayout request"""
        await self.sub("availableCashForPayout", callback)

    # todo availableSize

    async def cancel_order(self, id, callback=print):
        """cancelOrder request"""
        return await self.sub(
            "cancelOrder",
            payload={"type": "cancelOrder", "orderId": id},
            callback=callback,
            key=f"cancelOrder {id}"
        )

    # todo cancelPriceAlarm

    async def cancel_savings_plan(self, id, callback=print):
        """cancelSavingsPlan request"""
        await self.sub(
            "cancelSavingsPlan",
            payload={"type": "cancelSavingsPlan", "id": id},
            callback=callback,
            key=f"cancelSavingsPlan {id}"
        )

    async def cash(self, callback=print):
        """cash request"""
        await self.sub("cash", callback)

    # todo changeOrder

    async def change_savings_plan(self, id, isin, amount, startDate, interval, warnings_shown,
                                  callback=print):  # todo what is warningsshown?
        """changeSavingsPlan request"""

        params = {"instrumentId": isin,
                  "amount": amount,
                  "startDate": startDate,
                  "interval": interval
                  }

        return await self.sub(
            "changeSavingsPlan",
            payload={
                "type": "createSavingsPlan",
                "id": id,
                "parameters": params,
                "warningsShown": warnings_shown,
            },
            callback=callback,
            key=f"changeSavingsPlan {id}"
        )

    # todo collection

    @deprecated(reason="Removed by Trade Republic. Use function compact_portfolio_by_type")
    async def compact_portfolio(self, callback=print):
        """compactPortfolio request

        .. deprecated::
            The server answers with BAD_SUBSCRIPTION_TYPE. Use
            :meth:`compact_portfolio_by_type` instead.
        """
        await self.sub("compactPortfolio", callback)

    async def compact_portfolio_by_type(self, callback=print):
        """compactPortfolioByType request

        Login required!

        Replaces the removed portfolio and compactPortfolio topics.

        :return: the positions of the portfolio, grouped by instrument type
        """
        await self.sub("compactPortfolioByType", callback)

    # todo  confirmOrder

    async def create_price_alarm(self, isin, target_price, callback=print):
        """createPriceAlarm request"""
        return await self.sub(
            "createPriceAlarm",
            payload={
                "type": "createPriceAlarm",
                "instrumentId": isin,
                "targetPrice": target_price,
            },
            callback=callback,
            key=f"createPriceAlarm {isin} {target_price}",
        )

    async def create_savings_plan(self, isin, amount, startDate, interval, warnings_shown,
                                  callback=print):  # todo what is warningsshown?
        """createSavingsPlan request"""

        params = {"instrumentId": isin,
                  "amount": amount,
                  "startDate": startDate,
                  "interval": interval
                  }

        return await self.sub(
            "createSavingsPlan",
            payload={
                "type": "createSavingsPlan",
                "parameters": params,
                "warningsShown": warnings_shown,
            },
            callback=callback,
            key=f"createSavingsPlan {params} {warnings_shown}"
        )

    async def crypto_details(self, id, callback=print):
        """cryptoDetails request

        No login required

        :param id: the crypto instrument's id, e.g. "XF000BTC0017"
        :param callback: callback function
        """
        return await self.sub(
            "cryptoDetails",
            payload={"type": "cryptoDetails", "id": id},
            callback=callback,
            key=f"cryptoDetails {id}",
        )

    async def etf_composition(self, id, callback=print):
        """etfComposition request

        No login required

        :param id: the etf's isin
        :param callback: callback function
        :return: how the etf is composed by country, sector and holding
        """
        return await self.sub(
            "etfComposition",
            payload={"type": "etfComposition", "id": id},
            callback=callback,
            key=f"etfComposition {id}",
        )

    async def etf_details(self, id, callback=print):
        """etfDetails request

        No login required

        :param id: the etf's isin
        :param callback: callback function
        """
        return await self.sub(
            "etfDetails",
            payload={"type": "etfDetails", "id": id},
            callback=callback,
            key=f"etfDetails {id}",
        )

    # todo  followWatchlist

    @deprecated(reason="Removed by Trade Republic, the server answers with BAD_SUBSCRIPTION_TYPE")
    async def frontend_experiment(self, operation, experimentId, identifier, callback=print):
        """frontendExperiment request

        .. deprecated:: Removed by Trade Republic, no replacement.
        """
        return await self.sub(
            "frontendExperiment",
            payload={"type": "frontendExperiment", "operation": operation, "experimentId": experimentId,
                     "identifier": identifier},
            callback=callback,
            key=f"frontendExperiment {operation} {experimentId} {identifier}",
        )

    async def instrument(self, id, callback=print):
        """instrument request

        No login required

        Gets basic information about the instrument. For more information, use stock_details, crypto_details and etf_details.

        :param id: instrument's id
        :param callback: callback function
        :return: information about the instrument
        """
        return await self.sub(
            "instrument",
            payload={"type": "instrument", "id": id},
            callback=callback,
            key=f"instrument {id}",
        )

    @deprecated(reason="Removed by Trade Republic. Use function home_instrument_exchange")
    async def instrument_exchange(self, instrument_id, callback=print):
        """instrumentExchange request

        .. deprecated::
            The server answers with BAD_SUBSCRIPTION_TYPE. Use
            :meth:`home_instrument_exchange` instead.
        """
        return await self.sub(
            "instrumentExchange",
            payload={"type": "instrumentExchange", "instrumentId": instrument_id},
            callback=callback,
            key=f"instrumentExchange {instrument_id}",
        )

    async def home_instrument_exchange(self, instrument_id, callback=print):
        """homeInstrumentExchange request"""
        return await self.sub(
            "homeInstrumentExchange",
            payload={"type": "homeInstrumentExchange", "instrumentId": instrument_id},
            callback=callback,
            key=f"homeInstrumentExchange {instrument_id}",
        )

    @deprecated(reason="Removed by Trade Republic, the server answers with BAD_SUBSCRIPTION_TYPE")
    async def instrument_suitability(self, instrument_id, callback=print):
        """instrumentSuitability request

        .. deprecated:: Removed by Trade Republic, no replacement.
        """
        return await self.sub(
            "instrumentSuitability",
            payload={"type": "instrumentSuitability", "instrumentId": instrument_id},
            callback=callback,
            key=f"instrumentSuitability {instrument_id}",
        )

    # todo investableWatchlist
    @deprecated(reason="Removed by Trade Republic, the server answers with BAD_SUBSCRIPTION_TYPE")
    async def message_of_the_day(self, callback=print):
        """messageOfTheDay request

        .. deprecated:: Removed by Trade Republic, no replacement.
        """
        await self.sub("messageOfTheDay", callback)

    # todo  namedWatchlist
    @deprecated(reason="Removed by Trade Republic, the server answers with BAD_SUBSCRIPTION_TYPE")
    async def neon_cards(self, callback=print):
        """neonCards request

        .. deprecated:: Removed by Trade Republic, no replacement.
        """
        await self.sub("neonCards", callback)

    async def derivatives(self, isin, product_category, callback=print):
        # todo: create list for product_category
        """derivatives request"""
        return await self.sub(
            "derivatives",
            payload={"type": "derivatives", "underlying": isin, "productCategory": product_category},
            callback=callback,
            key=f"derivatives {isin}",
        )

    async def neon_search(self, query="", page=1, page_size=20, instrument_type="stock", jurisdiction="DE",
                          callback=print):
        """neonSearch request

        No login required
#todo params
        :return: list of instruments"""

        if instrument_type not in self.instrument_list:
            raise TRapiException(f"type must be either one of {self.instrument_list}")

        if jurisdiction not in self.jurisdiction_list:
            raise TRapiException(f"Jurisdiction must be either one of {self.jurisdiction_list}")

        filter = [{"key": "type", "value": instrument_type},
                  {"key": "jurisdiction", "value": jurisdiction},
                  # [{"key": "relativePerformance", "value": "VAL"}]  # todo: are there more filters?
                  ]
        data = {"q": query,
                "page": page,
                "pageSize": page_size,
                "filter": filter}
        await self.sub(
            "neonSearch",
            callback=callback,
            payload={"type": "neonSearch", "data": data},
            key=f"neonSearch {query} {page} {page_size} {filter}",
        )

    async def neon_search_aggregations(self, query="", page=1, page_size=20, instrument_type="stock", jurisdiction="DE",
                                       callback=print):
        """neonSearchAggregations request

        No login required

        :return: list of categories of instruments and number of instruments per category"""

        if instrument_type not in self.instrument_list:
            raise TRapiException(f"type must be either one of {self.instrument_list}")

        if jurisdiction not in self.jurisdiction_list:
            raise TRapiException(f"Jurisdiction must be either one of {self.jurisdiction_list}")

        filter = [{"key": "type", "value": instrument_type},
                  {"key": "jurisdiction", "value": jurisdiction},
                  # [{"key": "relativePerformance", "value": "VAL"}]  # todo: are there more filters?
                  ]
        data = {"q": query,
                "page": page,
                "pageSize": page_size,
                "filter": filter}
        await self.sub(
            "neonSearchAggregations",
            callback=callback,
            payload={"type": "neonSearchAggregations", "data": data},
            key=f"neonSearchAggregations {query} {page} {page_size} {filter}",
        )

    async def neon_search_suggested_tags(self, query="", callback=print):
        """neonSearchSuggestedTags request"""

        data = {"q": query,
                }
        await self.sub(
            "neonSearchSuggestedTags",
            callback=callback,
            payload={"type": "neonSearchSuggestedTags", "data": data},
            key=f"neonSearchSuggestedTags {query}",
        )

    async def neon_search_tags(self, callback=print):
        """neonSearchTags request

        No login required

        :return: available search tags
        """
        await self.sub("neonSearchTags", callback)

    async def neon_news(self, isin, callback=print):
        """neonNews request

        No login required

        :return: news articles about the company
        """
        await self.sub(
            "neonNews",
            callback=callback,
            payload={"type": "neonNews", "isin": isin},
            key=f"news {isin}"
        )

    # todo newsSubscriptions

    async def orders(self, terminated=False, callback=print):
        """orders request"""
        return await self.sub(
            "orders",
            callback=callback,
            payload={"type": "orders", "terminated": terminated},
            key=f"orders {terminated}")

    async def performance(self, isin, exchange="LSX", callback=print):
        """performance request

        No login required

        :param isin: the instrument's isin
        :param exchange: the exchange the instrument is traded at
        :param callback: callback function
        :return: the price changes over the usual reference periods
        """
        if exchange not in self.exchange_list:
            raise TRapiException(f"exchange must be either one of {self.exchange_list}")

        return await self.sub(
            "performance",
            payload={"type": "performance", "id": f"{isin}.{exchange}"},
            callback=callback,
            key=f"performance {isin} {exchange}",
        )

    @deprecated(reason="Removed by Trade Republic. Use function compact_portfolio_by_type")
    async def portfolio(self, callback=print):
        """portfolio request

        .. deprecated::
            The server answers with BAD_SUBSCRIPTION_TYPE. Use
            :meth:`compact_portfolio_by_type` instead.
        """
        await self.sub("portfolio", callback)

    @deprecated(reason="Removed by Trade Republic, the server answers with BAD_SUBSCRIPTION_TYPE")
    async def portfolio_aggregate_history(self, range="max", callback=print):
        """portfolioAggregateHistory request

        .. deprecated::
            Removed by Trade Republic. portfolioAggregateHistoryLight is gone
            as well and no websocket replacement could be found.
        """
        if range not in self.range_list:
            raise TRapiException(f"Range of time must be either one of {self.range_list}")
        return await self.sub(
            "portfolioAggregateHistory",
            payload={"type": "portfolioAggregateHistory", "range": range},
            callback=callback,
            key=f"portfolioAggregateHistory {range}",
        )

    # todo portfolioAggregateHistoryLight
    async def portfolio_status(self, callback=print):
        """portfolioStatus request"""
        return await self.sub("portfolioStatus", callback)

    async def price_alarms(self, callback=print):
        """priceAlarms request"""
        return await self.sub("priceAlarms", callback)

    # todo priceForOrder
    async def remove_from_watchlist(self, instrument_id, callback=print):
        """removeFromWatchlist request"""
        return await self.sub(
            "orders",
            callback=callback,
            payload={"type": "removeFromWatchlist", "instrumentId": instrument_id},
            key=f"removeFromWatchlist {instrument_id}")

    # todo savingsPlanParameters

    async def savings_plans(self, callback=print):
        """savingsPlans request

        Login required!

        :return: the customer's savings plans
        """
        return await self.sub("savingsPlans", callback)

    # The settings topic was removed by Trade Republic.

    async def simple_create_order(
            self,
            order_id,
            isin,
            order_type,
            size,
            limit,
            expiry,
            exchange="LSX",
            callback=print,
    ):
        """simpleCreateOrder request"""
        if expiry not in self.expiry_list:
            raise TRapiException(f"Expiry must be either of {self.expiry_list}")

        if order_type not in self.order_type_list:
            raise TRapiException(
                f"order_Type must be either of {self.order_type_list}"
            )

        if exchange not in self.exchange_list:
            raise TRapiException(f"exchange must be either one of {self.exchange_list}")

        payload = {
            "type": "simpleCreateOrder",
            "clientProcessId": order_id,
            "warningsShown": ["userExperience"],
            "acceptedWarnings": ["userExperience"],
            "parameters": {
                "instrumentId": isin,
                "exchangeId": exchange,
                "expiry": {"type": expiry},
                "limit": limit,
                "mode": "limit",
                "size": size,
                "type": order_type,
            },
        }

        return await self.sub(
            "simpleCreateOrder",
            payload=payload,
            callback=callback,
            key=f"simpleCreateOrder {order_id}",
        )

    async def stock_detail_dividends(self, isin, callback=print):
        """stockDetailDividends request

        Login required!

        :param: isin: the stock's isin
        :return: complete list of stock's past dividends
        """
        await self.sub(
            "stockDetailDividends",
            callback=callback,
            payload={"type": "stockDetailDividends", "id": isin},  # todo: variable jurisdiction , "jurisdiction": "DE"?
            key=f"stockDetailDividends {isin}",
        )

    async def stock_detail_kpis(self, isin, callback=print):
        """stockDetailKpis request

        Login required!

        :param: isin: the stock's isin
        :return: list of stock's past kpis per year
        """
        await self.sub(
            "stockDetailKpis",
            callback=callback,
            payload={"type": "stockDetailKpis", "id": isin},  # todo: variable jurisdiction , "jurisdiction": "DE"?
            key=f"stockDetailKpis {isin}",
        )

    async def stock_details(self, isin, callback=print):
        """stockDetails request

        Login required!

        Gets detailed summary about stock. For more information you might need to use stock_detail_dividends or stock_detail_kpis

        :param: isin: the stock's isin
        :return: more detailed information about stock than instrument request
        """
        await self.sub(
            "stockDetails",
            callback=callback,
            payload={"type": "stockDetails", "id": isin},  # todo: variable jurisdiction , "jurisdiction": "DE"?
            key=f"stockDetails {isin}",
        )

    # todo subscribeNews

    async def ticker(self, isin, exchange="LSX", callback=print):
        """ticker request"""

        if exchange not in self.exchange_list:
            raise TRapiException(f"exchange must be either one of {self.exchange_list}")

        await self.sub(
            "ticker",
            callback=callback,
            payload={"type": "ticker", "id": f"{isin}.{exchange}"},
            key=f"ticker {isin} {exchange}",
        )

    @deprecated(reason="Removed by Trade Republic. Use timeline_transactions or timeline_activity_log")
    async def timeline(self, after=None, callback=print):
        """timeline request

        .. deprecated::
            The server answers with BAD_SUBSCRIPTION_TYPE. The timeline was
            split into :meth:`timeline_transactions` (everything that moves
            money) and :meth:`timeline_activity_log` (everything else).
        """
        return await self.sub(
            "timeline",
            payload={"type": "timeline", "after": after},
            callback=callback,
            key=f"timeline {after}",
        )

    async def timeline_transactions(self, after=None, callback=print):
        """timelineTransactions request

        Login required!

        Returns the money-moving part of the former timeline: orders, savings
        plan executions, dividends, deposits and payouts.

        :param after: cursor of the previous page, None for the first page
        :param callback: callback function
        """
        return await self.sub(
            "timelineTransactions",
            payload={"type": "timelineTransactions", "after": after},
            callback=callback,
            key=f"timelineTransactions {after}",
        )

    async def timeline_activity_log(self, after=None, callback=print):
        """timelineActivityLog request

        Login required!

        Returns the non-transactional part of the former timeline, e.g.
        account changes and notifications.

        :param after: cursor of the previous page, None for the first page
        :param callback: callback function
        """
        return await self.sub(
            "timelineActivityLog",
            payload={"type": "timelineActivityLog", "after": after},
            callback=callback,
            key=f"timelineActivityLog {after}",
        )

    @deprecated(reason="Removed by Trade Republic. Use function timeline_actions_v2")
    async def timeline_actions(self, callback=print):
        """timelineActions request

        .. deprecated::
            The server answers with BAD_SUBSCRIPTION_TYPE. Use
            :meth:`timeline_actions_v2` instead.
        """
        return await self.sub("timelineActions", callback)

    async def timeline_actions_v2(self, callback=print):
        """timelineActionsV2 request

        Login required!

        :return: the actions Trade Republic currently suggests to the customer
        """
        return await self.sub("timelineActionsV2", callback)

    async def timeline_detail(self, id, callback=print):
        """timelineDetailV2 request

        Login required!

        The timelineDetail topic was replaced by timelineDetailV2.

        :param id: the id of a timeline entry
        :param callback: callback function
        """
        return await self.sub(
            "timelineDetailV2",
            payload={"type": "timelineDetailV2", "id": id},
            callback=callback,
            key=f"timelineDetailV2 {id}",
        )

    async def trading_perk_condition_status(self, callback=print):
        """tradingPerkConditionStatus request

        Login required!
        """
        return await self.sub("tradingPerkConditionStatus", callback)

    #  todo unfollowWatchlist
    # The subscribeNews / unsubscribeNews topics were removed by Trade Republic.

    async def watchlist(self, callback=print):
        """watchlist request"""
        return await self.sub("watchlist", callback)

    async def watchlists(self, callback=print):
        """watchlists request

        Login required!

        :return: all watchlists of the customer
        """
        return await self.sub("watchlists", callback)

    # -----------------------------------------------------------
    # old names of functions

    @deprecated(reason="Use function neon_news")
    async def news(self, isin, callback=print):
        await self.neon_news(isin, callback=callback)

    @deprecated(reason="Use function instrument")
    async def derivativ_details(self, isin, callback=print):
        await self.instrument(isin, callback=callback)

    @deprecated(reason="Use function portfolio_aggregate_history")
    async def port_hist(self, range="max", callback=print):
        await self.portfolio_aggregate_history(range=range, callback=callback)

    @deprecated(reason="Use function orders")
    async def curr_orders(self, callback=print):
        await self.orders(callback=callback)

    @deprecated(reason="Use function timeline")
    async def hist(self, after=None, callback=print):
        await self.timeline(after=after, callback=callback)

    @deprecated(reason="Use function timeline_detail")
    async def hist_event(self, id, callback=print):
        await self.timeline_detail(id, callback=callback)

    @deprecated(reason="Use function orders")
    async def all_orders(self, callback=print):
        await self.orders(callback=callback)

    @deprecated(reason="Use function cancel_order")
    async def order_cancel(self, id, callback=print):
        await self.cancel_order(id, callback=callback)

    @deprecated(reason="Use function simple_create_order")
    async def limit_order(
            self,
            order_id,
            isin,
            order_type,
            size,
            limit,
            expiry,
            exchange="LSX",
            callback=print,
    ):
        await self.simple_create_order(order_id, isin, order_type, size, limit, expiry, exchange=exchange,
                                       callback=callback)

    @deprecated(reason="Use function aggregate_history_light")
    async def stock_history(self, isin, range="max", callback=print):
        await self.aggregate_history_light(isin, range=range, callback=callback)

    # -----------------------------------------------------------

    async def start(self, receive_one=False):
        async with self.mu:
            if self.started:
                raise TRapiException("TrApi has already been started")

            self.started = True

        while True:
            data_a = await self.get_data()

            # Frames look like "<id> <state> <payload>". Splitting on every run
            # of whitespace and re-joining with a single space used to corrupt
            # payloads that contain consecutive spaces, so limit the split.
            parts = str(data_a).split(" ", 2)

            id, state = parts[:2]

            data = parts[2] if len(parts) > 2 else ""

            if state == "D":
                data = self.decode_updates(id, data.split())
            elif state == "A":
                pass
            elif state == "C":
                continue
            elif state == "E":
                sErr = f"ERROR state: {state} data: {data}"
                # print(sErr)
                if receive_one:  # cleanup
                    self.started = False
                    self.callbacks = {}
                    self.latest_response = {}
                    # return None
                raise TRapiExcServerErrorState(
                    f"Error during server access\n\tServer-side Object probably expired...\n\t{sErr}")
                # continue
            else:
                sErr = f"ERROR UNKNOWN state: {state} data: {data}"
                print(sErr)
                raise TRapiExcServerUnknownState(f"Error during server access\n\t{sErr}")
                # continue

            self.latest_response[id] = data
            obj = json.loads(data)

            key = None
            for k, v in self.dict.items():
                if v == id:
                    key = k
                    break

            if isinstance(obj, list):
                # if it is a list just add the key to every element
                for i in range(0, len(obj)):
                    obj[i]["key"] = key
            elif isinstance(obj, dict):
                obj["key"] = key

            if receive_one:
                self.started = False
                self.callbacks = {}

                self.latest_response = {}
                return obj
            self.callbacks[id](obj)

    @classmethod
    def all_isins(cls):
        folder = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(folder, "isins.txt")
        with open(path) as f:
            isins = f.read().splitlines()

        return isins

    def type_to_id(self, t: str) -> str:
        return self.dict.get(t, None)

    def decode_updates(self, key, payload):
        # Let's take an example, the first payload is the initial response we go
        # and the second one is update, meaning there are new values.
        #
        # The second one looks kinda strange but we will get to it.
        #
        # 1. {"bid":{"time":1611928659702,"price":13.873,"size":3615},"ask":{"time":1611928659702,"price":13.915,
        # "size":3615},"last":{"time":1611928659702,"price":13.873,"size":3615},"pre":{"time":1611855712255,
        # "price":13.756,"size":0},"open":{"time":1611901151053,"price":13.743,"size":0},"qualityId":"realtime",
        # "leverage":null,"delta":null}
        #
        # 2. ['=23', '-5', '+64895', '=14', '-1', '+5', '=36', '-5', '+64895', '=14',
        # '-1', '+3', '=37', '-5', '+64895', '=14', '-1', '+5', '=173']
        #
        # The payload is in json format but to update the payload we have to treat it as a string.
        # Lets name the 1 payload fst. We treat fst as a string and in the second payload
        # we have instructions which values to keep and which to update.
        #   +23 => Keep 23 chars of the previous payload
        #   -5 => Replace the next 5 chars
        #   +64895 => Replace those 5 chars with 64895
        #   =14 => Keep 14 chars of the previous payload

        latest = self.latest_response[key]

        cur = 0

        rsp = ""
        for x in payload:

            instruction = x[0]
            rst = x[1:]

            if instruction == "=":
                num = int(rst)
                rsp += latest[cur: (cur + num)]
                cur += num
            elif instruction == "-":
                cur += int(rst)
            elif instruction == "+":
                rsp += rst
            else:
                raise TRapiException("Error in decode_updates()")

        return rsp


class TrBlockingApi(TRApi):
    def __init__(self, number, pin, timeout=20.0, locale="en", connect_version=None):
        self.timeout = timeout
        super().__init__(number, pin, locale, connect_version=connect_version)

    async def get_one(self, f):
        await f
        res = None
        try:
            res = await asyncio.wait_for(
                super().start(receive_one=True), timeout=self.timeout
            )
            return res
        except Exception as e:
            raise e
            # return None

    # -----------------------------------------------------------

    def aggregate_history_light(self, isin, range="max", resolution=None, exchange="LSX"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().aggregate_history_light(isin, range=range, resolution=resolution, exchange=exchange))
        )

    def available_cash(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().available_cash())
        )

    def available_cash_for_payout(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().available_cash_for_payout())
        )

    def cash(self):
        return asyncio.get_event_loop().run_until_complete(self.get_one(super().cash()))

    def compact_portfolio_by_type(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().compact_portfolio_by_type())
        )

    def crypto_details(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().crypto_details(id))
        )

    def etf_composition(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().etf_composition(id))
        )

    def etf_details(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().etf_details(id))
        )

    def instrument(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().instrument(id))
        )

    def performance(self, isin, exchange="LSX"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().performance(isin, exchange=exchange))
        )

    def neon_search(self, query="", page=1, page_size=20, instrument_type="stock", jurisdiction="DE", ):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(
                super().neon_search(query=query, page=page, page_size=page_size, instrument_type=instrument_type,
                                    jurisdiction=jurisdiction))
        )

    def neon_news(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().neon_news(isin))
        )

    def orders(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().orders())
        )

    def portfolio(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().portfolio())
        )

    def portfolio_aggregate_history(self, range="max"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().portfolio_aggregate_history(range=range))
        )

    def stock_detail_dividends(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().stock_detail_dividends(isin))
        )

    def stock_detail_kpis(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().stock_detail_kpis(isin))
        )

    def stock_details(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().stock_details(isin))
        )

    def ticker(self, isin, exchange="LSX"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().ticker(isin, exchange))
        )

    def timeline(self, after=None):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().timeline(after=after))
        )

    def timeline_transactions(self, after=None):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().timeline_transactions(after=after))
        )

    def timeline_activity_log(self, after=None):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().timeline_activity_log(after=after))
        )

    def timeline_detail(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().timeline_detail(id=id))
        )

    # -----------------------------------------------------------
    # old names of functions

    @deprecated(reason="Use function timeline")
    def hist(self, after=None):
        return self.timeline(after=after)

    @deprecated(reason="Use function neon_news")
    def news(self, isin):
        return self.neon_news(isin)

    @deprecated(reason="Use function orders")
    def curr_orders(self):
        self.orders()

    @deprecated(reason="Use function portfolio_aggregate_history")
    def port_hist(self, range="max"):
        return self.portfolio_aggregate_history(range=range)

    @deprecated(reason="Use function instrument")
    def derivativ_details(self, isin):
        return self.instrument(isin)

    @deprecated(reason="Use function aggregate_history_light")
    def stock_history(self, isin, range="max"):
        return self.aggregate_history_light(isin, range=range)

    @deprecated(reason="Use function neon_news")
    def hist_event(self, id):
        return self.timeline_detail(id)
