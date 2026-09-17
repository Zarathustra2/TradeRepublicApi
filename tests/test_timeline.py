"""Tests for the timeline parsing.

The fixtures follow the shape timelineTransactions and timelineDetailV2
actually answer with, recorded against the live API in August 2026.
"""

import io
import unittest
from datetime import datetime
from decimal import Decimal

from trapi.timeline import (
    EVENT_TYPES,
    NOT_EXPORTED,
    Transaction,
    detail_documents,
    detail_isin,
    document_url,
    detail_row,
    detail_rows,
    parse_decimal,
    parse_quantity_and_price,
    parse_timestamp,
    sections_of,
    transaction_of,
    write_csv,
)


def trade_detail(rows=None, isin="US0378331005", documents=True, logo=True):
    """A trade detail in the shape the API answers with.

    Recorded against the live API in August 2026: values are rendered, the
    quantity and the price share one row, and the sections are more than the
    tables the export reads.
    """
    header = {
        "type": "header",
        "title": "Apple Inc",
        "data": {
            "icon": {"asset": "logos/%s/v2" % isin if logo else "logos/x/v2",
                     "badge": None},
            "subtitleText": "6 Aug \u00b7 9:41\u202fam",
            "status": "executed",
        },
    }
    if isin:
        header["action"] = {"type": "instrumentDetail", "payload": isin}

    sections = [
        header,
        {
            "type": "table",
            "title": "Overview",
            "data": rows if rows is not None else [
                {"title": "Sell",
                 "detail": {"text": "Executed", "type": "status"},
                 "style": "plain"},
                {"title": "Asset",
                 "detail": {"text": "Apple Inc", "type": "text"},
                 "style": "plain"},
                {"title": "Transaction",
                 "detail": {"text": "0.347123 \u00d7  \u20ac26.55",
                            "type": "text"},
                 "style": "plain"},
                {"title": "Tax",
                 "detail": {"text": "\u20ac0.42", "type": "text"},
                 "style": "plain"},
                {"title": "Fee",
                 "detail": {"text": "\u20ac1.00", "type": "text"},
                 "style": "plain"},
                {"title": "Total",
                 "detail": {"text": "\u20ac92.13", "type": "text"},
                 "style": "plain"},
            ],
        },
        {
            "type": "horizontalTable",
            "title": "Performance",
            "data": [{"title": "Profit",
                      "detail": {"text": "3.21 %", "type": "text"}}],
        },
        {"type": "text", "text": "Some note.", "style": "regular"},
        # A row without a label, which the app renders as a list item.
        {"type": "table", "title": "",
         "data": [{"title": None, "detail": {"type": "listItem"}}]},
    ]

    if documents:
        sections.append({
            "type": "documents",
            "title": "Documents",
            "data": [
                # A ready to use link
                {"title": "Invoice", "id": "doc-1",
                 "action": {"type": "browserModal",
                            "payload": "https://tr.example/invoice.pdf"}},
                # One that needs the session
                {"title": "Statement", "id": "doc-2",
                 "action": {"type": "authenticatedBrowserModal",
                            "payload": {"path": "api/v2/documents/abc",
                                        "title": "Statement",
                                        "shareable": True}}},
                # Not a document at all
                {"title": "Instrument",
                 "action": {"type": "instrumentDetail", "payload": "US123"}},
                {"title": "Without an action"},
            ],
        })
    return {"id": "detail-id", "sections": sections, "key": "irrelevant"}


def interest_detail():
    """An interest payout: no instrument, no quantity, German rendering."""
    return {"id": "detail-id", "sections": [
        {"type": "header", "title": "Zinsen",
         "data": {"icon": {"asset": "logos/interest/v2"}, "status": "executed"}},
        {"type": "table", "title": "\u00dcbersicht", "data": [
            {"title": "Zinsen",
             "detail": {"text": "Erhalten", "type": "status"}},
            {"title": "Angefallen",
             "detail": {"text": "9,99 \u20ac", "type": "text"}},
            {"title": "Steuern",
             "detail": {"text": "2,64 \u20ac", "type": "text"}},
            {"title": "Gesamt",
             "detail": {"text": "7,35 \u20ac", "type": "text"}},
        ]},
    ]}


def event(**overrides):
    base = {
        "id": "event-id",
        "timestamp": "2026-08-13T09:41:02.123+0000",
        "title": "Apple Inc",
        "subtitle": "Sell order",
        "amount": {"currency": "EUR", "value": -92.13, "fractionDigits": 2},
        "status": "EXECUTED",
        "action": {"type": "timelineDetail", "payload": "detail-id"},
        "eventType": "TRADING_TRADE_EXECUTED",
        "hidden": False,
        "deleted": False,
    }
    base.update(overrides)
    return base


class ParseDecimalTest(unittest.TestCase):
    def test_german_rendering(self):
        self.assertEqual(parse_decimal("1.234,56 €"), Decimal("1234.56"))
        self.assertEqual(parse_decimal("0,347"), Decimal("0.347"))
        self.assertEqual(parse_decimal("-9,99 EUR"), Decimal("-9.99"))

    def test_english_rendering(self):
        self.assertEqual(parse_decimal("1,234.56", decimal_separator="."),
                         Decimal("1234.56"))

    def test_grouping_with_spaces(self):
        self.assertEqual(parse_decimal("1 234,56 €"), Decimal("1234.56"))

    def test_numbers_pass_through(self):
        self.assertEqual(parse_decimal(-92.13), Decimal("-92.13"))
        self.assertEqual(parse_decimal(5), Decimal("5"))

    def test_nothing_to_read(self):
        self.assertIsNone(parse_decimal(None))
        self.assertIsNone(parse_decimal(""))
        self.assertIsNone(parse_decimal("Ausgeführt"))


class ParseTimestampTest(unittest.TestCase):
    def test_iso_with_offset(self):
        parsed = parse_timestamp("2026-08-13T09:41:02.123+0000")
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 8)
        self.assertEqual(parsed.day, 13)

    def test_iso_with_z(self):
        self.assertIsNotNone(parse_timestamp("2026-08-13T09:41:02Z"))

    def test_epoch_milliseconds_still_work(self):
        # The old timeline delivered these, and exported files still hold them.
        parsed = parse_timestamp(1616811300786)
        self.assertEqual(parsed.year, 2021)
        self.assertEqual(parse_timestamp("1616811300786"), parsed)

    def test_nonsense(self):
        self.assertIsNone(parse_timestamp("morgen"))
        self.assertIsNone(parse_timestamp(None))


class DetailAccessTest(unittest.TestCase):
    def test_sections_can_be_filtered(self):
        detail = trade_detail()
        self.assertEqual(len(sections_of(detail, "header")), 1)
        self.assertEqual(len(sections_of(detail, "table")), 2)
        self.assertEqual(len(sections_of(detail, "documents")), 1)

    def test_only_tables_contribute_rows(self):
        # A detail also holds horizontalTable and text sections, whose
        # entries are not values of the transaction.
        rows = detail_rows(trade_detail())
        self.assertIn("Transaction", rows)
        self.assertNotIn("Profit", rows)

    def test_rows_without_a_label_are_ignored(self):
        self.assertNotIn(None, detail_rows(trade_detail()))

    def test_lookup_ignores_case_and_spacing(self):
        self.assertEqual(detail_row(trade_detail(), " fEe "), "\u20ac1.00")

    def test_lookup_takes_the_first_label_that_matches(self):
        detail = interest_detail()
        self.assertEqual(detail_row(detail, "Tax", "Steuern"), "2,64 \u20ac")
        self.assertIsNone(detail_row(detail, "does not exist"))

    def test_isin_comes_from_the_header_link(self):
        # The events themselves never carried it.
        self.assertEqual(detail_isin(trade_detail()), "US0378331005")

    def test_isin_falls_back_to_the_logo_path(self):
        # Some details link nowhere but still show the logo of the
        # instrument, and its path holds the isin.
        detail = trade_detail(isin=None)
        detail["sections"][0]["data"]["icon"]["asset"] = "logos/DE0007236101/v2"
        self.assertEqual(detail_isin(detail), "DE0007236101")

    def test_no_isin_when_there_is_no_instrument(self):
        self.assertIsNone(detail_isin(interest_detail()))

    def test_both_kinds_of_document_are_returned(self):
        # Most documents are not plain links but a path that needs the
        # session, and skipping those loses nearly everything.
        documents = detail_documents(trade_detail())
        self.assertEqual([d["title"] for d in documents],
                         ["Invoice", "Statement"])

        self.assertEqual(documents[0]["url"], "https://tr.example/invoice.pdf")
        self.assertIsNone(documents[0]["path"])

        self.assertIsNone(documents[1]["url"])
        self.assertEqual(documents[1]["path"], "api/v2/documents/abc")

    def test_address_of_a_document(self):
        documents = detail_documents(trade_detail())
        self.assertEqual(document_url(documents[0]),
                         "https://tr.example/invoice.pdf")
        self.assertEqual(document_url(documents[1]),
                         "https://api.traderepublic.com/api/v2/documents/abc")
        self.assertIsNone(document_url({"url": None, "path": None}))

    def test_a_leading_slash_does_not_double_up(self):
        self.assertEqual(document_url({"path": "/api/v2/x"}),
                         "https://api.traderepublic.com/api/v2/x")

    def test_no_documents_section(self):
        self.assertEqual(detail_documents(trade_detail(documents=False)), [])

    def test_survives_a_response_that_makes_no_sense(self):
        for junk in (None, {}, {"sections": None}, {"sections": ["x", 3]}):
            self.assertEqual(detail_rows(junk), {})
            self.assertIsNone(detail_isin(junk))
            self.assertEqual(detail_documents(junk), [])


class QuantityAndPriceTest(unittest.TestCase):
    """A trade renders quantity and price in one row, not one row each."""

    def test_the_row_is_split(self):
        quantity, price = parse_quantity_and_price("0.347123 \u00d7  \u20ac26.55")
        self.assertEqual(quantity, Decimal("0.347123"))
        self.assertEqual(price, Decimal("26.55"))

    def test_a_plain_x_works_too(self):
        # The multiplication sign is not used everywhere.
        quantity, price = parse_quantity_and_price("2 x 10,00 \u20ac")
        self.assertEqual(quantity, Decimal("2"))
        self.assertEqual(price, Decimal("10.00"))

    def test_a_row_without_a_quantity(self):
        quantity, price = parse_quantity_and_price("9,99 \u20ac")
        self.assertIsNone(quantity)
        self.assertEqual(price, Decimal("9.99"))

    def test_nothing_at_all(self):
        self.assertEqual(parse_quantity_and_price(None), (None, None))
        self.assertEqual(parse_quantity_and_price(""), (None, None))


class TransactionTest(unittest.TestCase):
    def test_money_leaving_the_account_is_a_buy(self):
        tx = transaction_of(event(), trade_detail())
        self.assertEqual(tx.kind, "buy")
        self.assertEqual(tx.shares, Decimal("0.347123"))
        self.assertEqual(tx.price, Decimal("26.55"))
        self.assertEqual(tx.fee, Decimal("1.00"))
        self.assertEqual(tx.tax, Decimal("0.42"))
        self.assertEqual(tx.value, Decimal("92.13"))
        self.assertEqual(tx.isin, "US0378331005")
        self.assertEqual(tx.currency, "EUR")

    def test_money_arriving_is_a_sell(self):
        tx = transaction_of(
            event(amount={"currency": "EUR", "value": 92.13}), trade_detail())
        self.assertEqual(tx.kind, "sell")
        self.assertEqual(tx.value, Decimal("92.13"))

    def test_value_is_reported_without_a_sign(self):
        # The kind already says which way the money went.
        self.assertGreater(transaction_of(event(), trade_detail()).value, 0)

    def test_german_rendering_in_the_same_shape(self):
        # The API mixes "\u20ac26.55" and "9,99 \u20ac", so the separator is
        # worked out per value.
        tx = transaction_of(event(eventType="INTEREST_PAYOUT",
                                  amount={"currency": "EUR", "value": 7.35}),
                            interest_detail())
        self.assertEqual(tx.kind, "interest")
        self.assertEqual(tx.tax, Decimal("2.64"))
        self.assertEqual(tx.value, Decimal("7.35"))

    def test_round_ups_and_saveback_are_purchases(self):
        for event_type in ("SPARE_CHANGE_AGGREGATE", "SAVEBACK_AGGREGATE"):
            tx = transaction_of(event(eventType=event_type), trade_detail())
            self.assertEqual(tx.kind, "buy", event_type)
            self.assertEqual(tx.shares, Decimal("0.347123"))

    def test_savings_plans_under_both_names(self):
        for event_type in ("TRADING_SAVINGSPLAN_EXECUTED",
                           "SAVINGS_PLAN_EXECUTED"):
            self.assertEqual(
                transaction_of(event(eventType=event_type)).kind, "buy")

    def test_deposits_and_payouts(self):
        deposit = transaction_of(event(eventType="BANK_TRANSACTION_INCOMING",
                                       amount={"currency": "EUR", "value": 500}))
        self.assertEqual(deposit.kind, "deposit")
        self.assertIsNone(deposit.isin)

        payout = transaction_of(event(eventType="BANK_TRANSACTION_OUTGOING",
                                      amount={"currency": "EUR", "value": -20}))
        self.assertEqual(payout.kind, "removal")
        self.assertEqual(payout.value, Decimal("20"))

    def test_cancelled_and_deleted_events_are_left_out(self):
        self.assertIsNone(transaction_of(event(status="CANCELED")))
        self.assertIsNone(transaction_of(event(status="REJECTED")))
        self.assertIsNone(transaction_of(event(deleted=True)))

    def test_events_that_would_count_twice_stay_out(self):
        # The invoice of a trade that is already exported under its own event.
        for event_type in NOT_EXPORTED:
            self.assertIsNone(transaction_of(event(eventType=event_type)),
                              event_type)
            self.assertNotIn(event_type, EVENT_TYPES)

    def test_an_entry_without_an_event_type(self):
        # Real timelines contain them, and status is None there as well.
        self.assertIsNone(transaction_of(event(eventType=None, status=None)))
        without = dict(event())
        del without["eventType"]
        self.assertIsNone(transaction_of(without))

    def test_unknown_event_types_are_left_out(self):
        # Silently dropping them was how the old converter lost entries, so
        # callers get None and can report it.
        self.assertIsNone(transaction_of(event(eventType="SOMETHING_NEW")))

    def test_works_without_a_detail(self):
        tx = transaction_of(event())
        self.assertEqual(tx.kind, "buy")
        self.assertIsNone(tx.shares)
        self.assertIsNone(tx.isin)

    def test_junk_in_junk_out(self):
        self.assertIsNone(transaction_of(None))
        self.assertIsNone(transaction_of("nope"))


class WriteCsvTest(unittest.TestCase):
    def rows_of(self, transactions, locale="de"):
        stream = io.StringIO()
        write_csv(transactions, stream, locale=locale)
        return stream.getvalue().splitlines()

    def test_header_matches_the_old_export(self):
        lines = self.rows_of([])
        self.assertTrue(lines[0].startswith("Datum;Typ;Stück;"))
        self.assertTrue(lines[0].endswith("Buchungswährung"))

    def test_english_header_lines_up_with_the_german_one(self):
        # The old exporter wrote Amount/Value/Price against
        # Stück/Wechselkurs/Wert, so the two did not describe the same columns.
        de = self.rows_of([], locale="de")[0].split(";")
        en = self.rows_of([], locale="en")[0].split(";")
        self.assertEqual(len(de), len(en))
        self.assertEqual(en[2], "Shares")
        self.assertEqual(en[4], "Value")

    def test_a_transaction_becomes_one_line(self):
        tx = transaction_of(event(), trade_detail())
        lines = self.rows_of([tx])
        self.assertEqual(len(lines), 2)
        fields = lines[1].split(";")
        self.assertEqual(fields[1], "Kauf")
        self.assertEqual(fields[2], "0.347123")
        self.assertEqual(fields[7], "US0378331005")

    def test_a_semicolon_in_a_name_does_not_split_the_line(self):
        # The old exporter formatted the line by hand and broke on this.
        tx = transaction_of(event(title="Rheinmetall; AG"), trade_detail())
        stream = io.StringIO()
        write_csv([tx], stream)
        line = stream.getvalue().splitlines()[1]
        self.assertIn('"Rheinmetall; AG"', line)

        import csv
        parsed = list(csv.reader(io.StringIO(line), delimiter=";"))[0]
        self.assertEqual(len(parsed), 10)
        self.assertEqual(parsed[8], "Rheinmetall; AG")

    def test_missing_values_stay_empty(self):
        tx = Transaction(date=datetime(2026, 8, 13), kind="deposit",
                         value=Decimal("500"), currency="EUR")
        fields = self.rows_of([tx])[1].split(";")
        self.assertEqual(fields[0], "2026-08-13")
        self.assertEqual(fields[2], "")
        self.assertEqual(fields[7], "")


if __name__ == "__main__":
    unittest.main()
