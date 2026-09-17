"""Offline tests for the websocket protocol handling.

These tests do not touch the network; they drive TRApi against a fake
websocket connection. Run them with::

    python -m unittest discover -s tests
"""

import asyncio
import json
import unittest
from unittest import mock

from trapi.api import TRApi, TrBlockingApi, TRapiException

# A single loop for the whole module: asyncio primitives created in TRApi
# bind to the loop that is current at construction time.
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def run(coro):
    return LOOP.run_until_complete(coro)


class FakeWebsocket:
    """Minimal stand-in for a websockets connection."""

    def __init__(self, handshake_response="connected", frames=()):
        self.handshake_response = handshake_response
        self.sent = []
        self._incoming = list(frames)
        self._handshake_done = False

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if not self._handshake_done:
            self._handshake_done = True
            return self.handshake_response
        if not self._incoming:
            raise AssertionError("no frames left to receive")
        return self._incoming.pop(0)


def connected(ws):
    """Patch websockets.connect so that TRApi picks up the fake connection."""

    async def fake_connect(*args, **kwargs):
        return ws

    return mock.patch("trapi.api.websockets.connect", fake_connect)


def api(**kwargs):
    return TRApi("+490000000000", "0000", **kwargs)


def sent_payload(ws, index=1):
    """The JSON body of the index-th frame the client sent."""
    return json.loads(ws.sent[index].split(" ", 2)[2])


class ConnectFrameTest(unittest.TestCase):
    def test_uses_a_protocol_version_the_server_still_accepts(self):
        # The server rejects everything outside this range with
        # "failed <latest supported version>".
        self.assertGreaterEqual(TRApi.connect_version, 26)
        self.assertLessEqual(TRApi.connect_version, 34)

    def test_connect_frame_carries_client_identification(self):
        tr, ws = api(locale="de"), FakeWebsocket()
        with connected(ws):
            run(tr.sub("cash", print))

        prefix, version, payload = ws.sent[0].split(" ", 2)
        self.assertEqual(prefix, "connect")
        self.assertEqual(int(version), tr.connect_version)

        payload = json.loads(payload)
        self.assertEqual(payload["locale"], "de")
        self.assertEqual(payload["clientId"], "app.traderepublic.com")
        self.assertIn("platformId", payload)

    def test_connect_version_is_configurable(self):
        tr, ws = api(connect_version=34), FakeWebsocket()
        with connected(ws):
            run(tr.sub("cash", print))
        self.assertTrue(ws.sent[0].startswith("connect 34 "))

    def test_rejected_handshake_reports_the_version_that_was_sent(self):
        tr, ws = api(), FakeWebsocket(handshake_response="failed 34")
        with connected(ws), self.assertRaises(TRapiException) as ctx:
            run(tr.sub("cash", print))
        self.assertIn(str(tr.connect_version), str(ctx.exception))


class SubscriptionPayloadTest(unittest.TestCase):
    def test_no_token_field_when_not_logged_in(self):
        # "token": null makes the server reject public topics such as
        # stockDetails with a JSON_PARSE_ERROR.
        tr, ws = api(), FakeWebsocket()
        with connected(ws):
            run(tr.sub("stockDetails", print,
                       payload={"type": "stockDetails", "id": "US0378331005"}))
        self.assertNotIn("token", sent_payload(ws))

    def test_token_is_sent_once_logged_in(self):
        tr, ws = api(), FakeWebsocket()
        tr.sessionToken = "session-token"
        with connected(ws):
            run(tr.sub("cash", print))
        self.assertEqual(sent_payload(ws)["token"], "session-token")


class AggregateHistoryLightTest(unittest.TestCase):
    def test_resolution_is_omitted_by_default(self):
        # The server silently discards subscriptions carrying a resolution,
        # so such a request is never answered.
        tr, ws = api(), FakeWebsocket()
        with connected(ws):
            run(tr.aggregate_history_light("US0378331005", range="1d"))

        payload = sent_payload(ws)
        self.assertNotIn("resolution", payload)
        self.assertEqual(payload["id"], "US0378331005.LSX")

    def test_resolution_is_forwarded_when_given(self):
        tr, ws = api(), FakeWebsocket()
        with connected(ws):
            run(tr.aggregate_history_light("US0378331005", range="1d",
                                           resolution=60000))
        self.assertEqual(sent_payload(ws)["resolution"], 60000)


class CurrentTopicNamesTest(unittest.TestCase):
    """These topics replaced ones that Trade Republic has removed."""

    def topic_of(self, request):
        tr, ws = api(), FakeWebsocket()
        with connected(ws):
            run(request(tr))
        return sent_payload(ws)["type"]

    def test_portfolio_replacement(self):
        self.assertEqual(self.topic_of(lambda tr: tr.compact_portfolio_by_type()),
                         "compactPortfolioByType")

    def test_timeline_transactions_replacement(self):
        self.assertEqual(self.topic_of(lambda tr: tr.timeline_transactions()),
                         "timelineTransactions")

    def test_timeline_activity_log_replacement(self):
        self.assertEqual(self.topic_of(lambda tr: tr.timeline_activity_log()),
                         "timelineActivityLog")

    def test_timeline_detail_uses_v2(self):
        self.assertEqual(self.topic_of(lambda tr: tr.timeline_detail("some-id")),
                         "timelineDetailV2")


class FrameParsingTest(unittest.TestCase):
    def receive(self, frame, latest=None):
        tr = api()
        tr.dict = {"ticker": "1"}
        if latest is not None:
            tr.latest_response["1"] = latest
        ws = FakeWebsocket(frames=[frame])
        with connected(ws):
            run(tr.sub("ticker", print))
            return run(tr.start(receive_one=True))

    def test_payload_with_consecutive_spaces_survives(self):
        headline = "a  double  spaced  headline"
        obj = self.receive('1 A {"body": "%s"}' % headline)
        self.assertEqual(obj["body"], headline)

    def test_delta_update_is_applied(self):
        obj = self.receive("1 D =9 -6 +99.999 =1", latest='{"price":13.873}')
        self.assertEqual(obj["price"], 99.999)

    def test_single_instruction_delta_is_applied(self):
        # A delta consisting of a single instruction used to be iterated
        # character by character.
        obj = self.receive("1 D =16", latest='{"price":13.873}')
        self.assertEqual(obj["price"], 13.873)


class BlockingApiLoopTest(unittest.TestCase):
    """TrBlockingApi owns its loop instead of calling asyncio.get_event_loop(),
    which is deprecated since 3.10 and stops creating a loop in 3.14."""

    def setUp(self):
        self.addCleanup(asyncio.set_event_loop, LOOP)

    def test_owns_a_usable_loop(self):
        tr = TrBlockingApi("+490000000000", "0000")
        self.addCleanup(tr.close)
        self.assertFalse(tr._loop.is_closed())
        self.assertIsNot(tr._loop, LOOP)

    def test_close_closes_the_loop(self):
        tr = TrBlockingApi("+490000000000", "0000")
        tr.close()
        self.assertTrue(tr._loop.is_closed())

    def test_can_be_used_as_a_context_manager(self):
        with TrBlockingApi("+490000000000", "0000") as tr:
            loop = tr._loop
            self.assertFalse(loop.is_closed())
        self.assertTrue(loop.is_closed())

    def test_closing_twice_is_harmless(self):
        tr = TrBlockingApi("+490000000000", "0000")
        tr.close()
        tr.close()


if __name__ == "__main__":
    unittest.main()
