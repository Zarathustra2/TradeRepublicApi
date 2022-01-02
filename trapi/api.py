from ecdsa import NIST256p, SigningKey
from ecdsa.util import sigencode_der
import base64
import hashlib
import time
import requests
import asyncio
import websockets

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

    def __init__(self, number, pin, locale='en'):
        self.number = number
        self.pin = pin
        self.locale = locale
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

            # TODO: Error handling

            processId = r.json()["processId"]
            print(f"The process id is: {processId}")

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
            msg = json.dumps({"locale": self.locale})
            await self.ws.send(f"connect 21 {msg}")
            response = await self.ws.recv()

            if not response == "connected":
                raise  TRapiException(f"Connection Error: {response}") # ValueError(f"Connection Error: {response}")

        payload = kwargs.get("payload", {"type": payload_key})
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

    async def cash(self, callback=print):
        await self.sub("cash", callback)

    async def portfolio(self, callback=print):
        await self.sub("portfolio", callback)

    async def ticker(self, isin, callback=print):
        await self.sub(
            "ticker",
            callback=callback,
            payload={"type": "ticker", "id": f"{isin}.LSX"},
            key=f"ticker {isin}",
        )

    async def stock_details(self, isin, callback=print):
        await self.sub(
            "stockDetails",
            callback=callback,
            payload={"type": "stockDetails", "id": isin},
            key=f"stockDetails {isin}",
        )

    async def news(self, isin, callback=print):
        await self.sub(
            "neonNews",
            callback=callback,
            payload={"type": "neonNews", "isin": isin},
            key=f"news {isin}",
        )

    async def available_cash(self, callback=print):
        await self.sub("availableCash", callback)

    async def derivativ_details(self, isin, callback=print):
        return await self.sub(
            "instrument",
            payload={"type": "instrument", "id": isin},
            callback=callback,
            key=f"instrument {isin}",
        )

    async def port_hist(self, range="max", callback=print):
        l = ["1d", "5d", "1m", "3m", "1y", "max"]
        if range not in l:
            raise TRapiException(f"Range of time must be either one of {l}")
        return await self.sub(
            "portfolioAggregateHistory",
            payload={"type": "portfolioAggregateHistory", "range": range},
            callback=callback,
            key=f"portfolioAggregateHistory {range}",
        )

    async def curr_orders(self, callback=print):
        return await self.sub("orders", callback)

    async def hist(self, after=None, callback=print):
        return await self.sub(
            "timeline",
            payload={"type": "timeline", "after": after},
            callback=callback,
            key=f"timeline {after}",
        )

    async def hist_event(self, id, callback=print):
        return await self.sub(
            "timelineDetail",
            payload={"type": "timelineDetail", "id": id},
            callback=callback,
            key=f"timelineDetail {id}",
        )

    async def all_orders(self, callback=print):
        return await self.sub("orders", callback=callback)

    async def order_cancel(self, id, callback=print):
        return await self.sub(
            "cancelOrder",
            payload={"type": "cancelOrder", "orderId": id},
            callback=callback,
            key=f"cancelOrder {id}",
        )

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

        if expiry not in ["gfd", "gtd", "gtc"]:
            raise TRapiException(f"Expiry should be one of gfd, gtd, gtc, was {expiry}")

        if order_type not in ["buy", "sell"]:
            raise TRapiException(
                f"order_Type should be either buy or sell, was: {order_type}"
            )

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

    async def price_alarms(self, callback=print):
        return await self.sub("priceAlarms", callback)

    async def create_price_alarm(self, isin, target_price, callback=print):
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

    async def stock_history(self, isin, range="max", callback=print):
        l = ["1d", "5d", "1m", "3m", "1y", "max"]
        if range not in l:
            raise TRapiException(f"Range of time must be either one of {l}")

        return await self.sub(
            "aggregateHistory",
            payload={"type": "aggregateHistory", "range": range, "id": f"{isin}.LSX"},
            callback=callback,
            key=f"aggregateHistory {isin} {range}",
        )

    async def start(self, receive_one=False):
        async with self.mu:
            if self.started:
                raise TRapiException("TrApi has already been started")

            self.started = True

        while True:
            data_a = await self.get_data()

            data = str(data_a).split()

            id, state = data[:2]

            # Initial response
            if len(data[2:]) == 1:
                data = data[2:][0]
            else:
                data = data[2:]

            if state == "D":
                data = self.decode_updates(id, data)
            elif state == "A":
                pass
            elif state == "C":
                continue
            elif state == "E":
                sErr = f"ERROR state: {state} data: {data}"
                #print(sErr)
                if receive_one: #cleanup
                    self.started = False
                    self.callbacks = {}
                    self.latest_response = {}
                    #return None
                raise TRapiExcServerErrorState(f"Error during server access\n\tServer-side Object probably expired...\n\t{sErr}")
                #continue
            else:
                sErr = f"ERROR UNKNOWN state: {state} data: {data}"
                print(sErr)
                raise TRapiExcServerUnknownState(f"Error during server access\n\t{sErr}")
                #continue

            if isinstance(data, list):
                data = " ".join(data)

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
                rsp += latest[cur : (cur + num)]
                cur += num
            elif instruction == "-":
                cur += int(rst)
            elif instruction == "+":
                rsp += rst
            else:
                raise TRapiException("Error in decode_updates()")

        return rsp


class TrBlockingApi(TRApi):
    def __init__(self, number, pin, timeout=20.0, locale="en"):
        self.timeout = timeout
        super().__init__(number, pin, locale)

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
            #return None

    def cash(self):
        return asyncio.get_event_loop().run_until_complete(self.get_one(super().cash()))

    def hist(self, after=None):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().hist(after=after))
        )

    def news(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().news(isin))
        )

    def curr_orders(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().curr_orders())
        )

    def port_hist(self, range="max"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().port_hist(range=range))
        )

    def derivativ_details(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().derivativ_details(isin))
        )

    def stock_details(self, isin):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().stock_details(isin))
        )

    def stock_history(self, isin, range="max"):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().stock_history(isin, range=range))
        )

    def hist_event(self, id):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().hist_event(id=id))
        )

    def portfolio(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().portfolio())
        )

    def cash(self):
        return asyncio.get_event_loop().run_until_complete(self.get_one(super().cash()))

    def available_cash(self):
        return asyncio.get_event_loop().run_until_complete(
            self.get_one(super().available_cash())
        )
