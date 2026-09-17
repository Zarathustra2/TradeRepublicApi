"""Turning the timeline into something you can work with.

Trade Republic replaced the timeline in 2024. Two things changed for anyone
who processed it:

* The events themselves became structured. Where the old format carried a
  German sentence in ``body`` and a number in ``cashChangeAmount``, an event
  now has ``eventType``, ``status`` and ``amount``.

* The details went the other way. ``timelineDetailV2`` no longer describes a
  transaction, it describes a screen: a list of ``sections``, most of them
  tables whose rows are a label and a rendered value. The share count of a
  trade is not a field any more, it is the row labelled "Anteile".

So the values have to be read out of labelled rows. :data:`LABELS` says which
labels to look for and is the one place to touch when Trade Republic renames
something or you run the API in another language.
"""

import csv
import re
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal, InvalidOperation

__all__ = [
    "LABELS",
    "EVENT_TYPES",
    "Transaction",
    "detail_documents",
    "document_url",
    "detail_isin",
    "detail_row",
    "detail_rows",
    "parse_decimal",
    "parse_quantity_and_price",
    "parse_timestamp",
    "sections_of",
    "transaction_of",
    "write_csv",
]


# ---------------------------------------------------------------- parsing

_NUMBER = re.compile(r"-?\d[\d.,\s\u00a0']*\d|-?\d")
_CURRENCY = re.compile(r"[\u20ac$\u00a3\u00a5]|\b[A-Z]{3}\b")
_TIMES = re.compile(r"\s*[\u00d7xX*]\s*")


def parse_decimal(text, decimal_separator=None):
    """Reads the number out of a rendered value.

    The API delivers values the way it shows them, so they carry a currency
    symbol and locale specific separators - and it is not consistent about it.
    One and the same response mixes "\u20ac26.55" with "9,99 \u20ac", so which
    separator means what is worked out per value instead of being assumed:

    * with both separators present the rightmost one is the decimal one
    * with only one, three digits behind it mean grouping when the value is an
      amount of money, because money is rendered with two decimals. Without a
      currency it is a decimal separator, which keeps share counts such as
      "0.347" intact.

    :param text: the rendered value
    :param decimal_separator: "," or "." to skip the detection
    :return: the number, or None when there is none
    """
    if text is None:
        return None
    if isinstance(text, (int, float, Decimal)):
        return Decimal(str(text))

    text = str(text)
    match = _NUMBER.search(text)
    if not match:
        return None

    number = re.sub(r"[\s\u00a0']", "", match.group(0))

    if decimal_separator is None:
        decimal_separator = _detect_separator(number, text)

    if decimal_separator:
        grouping = "." if decimal_separator == "," else ","
        number = number.replace(grouping, "").replace(decimal_separator, ".")
    else:
        number = number.replace(".", "").replace(",", "")

    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def _detect_separator(number, text):
    """Which of the separators in a rendered number is the decimal one.

    :return: "," or "." , or None when every separator groups digits
    """
    last_dot = number.rfind(".")
    last_comma = number.rfind(",")

    if last_dot >= 0 and last_comma >= 0:
        return "." if last_dot > last_comma else ","

    position = max(last_dot, last_comma)
    if position < 0:
        return None

    digits_behind = len(number) - position - 1

    # Money carries two decimals, so three digits behind the separator group
    # thousands. Without a currency the value is a count, and there the
    # separator is a decimal one - share counts have more than two digits.
    if digits_behind == 3 and _CURRENCY.search(text):
        return None
    return number[position]


def parse_quantity_and_price(text):
    """Splits a transaction row into how many and at what price.

    The detail has no row per value. It renders a trade as
    "0.347123 \u00d7 \u20ac26.55" in a single row, so both numbers come from there.

    :return: (quantity, price), either of them None when it is not there
    """
    if not text:
        return None, None

    parts = _TIMES.split(str(text), 1)
    if len(parts) != 2:
        # Some events render an amount without a quantity.
        return None, parse_decimal(text)
    return parse_decimal(parts[0]), parse_decimal(parts[1])


def parse_timestamp(value):
    """Reads an event timestamp.

    The timeline switched from milliseconds since the epoch to an ISO string,
    so both are accepted.

    :return: a datetime, or None when the value makes no sense
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0)

    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000.0)

    # "2026-08-13T09:41:02.123+0000" - Python wants the colon in the offset
    # and cannot do more than six digits of fraction.
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# ------------------------------------------------------------- detail access

def sections_of(detail, section_type=None):
    """The sections of a timelineDetailV2 response.

    :param section_type: only sections of this type, e.g. "table"
    """
    if not isinstance(detail, dict):
        return []
    sections = detail.get("sections") or []
    if not isinstance(sections, list):
        return []
    sections = [s for s in sections if isinstance(s, dict)]
    if section_type is None:
        return sections
    return [s for s in sections if s.get("type") == section_type]


def _row_text(row):
    detail = row.get("detail")
    if not isinstance(detail, dict):
        return None
    display = detail.get("displayValue")
    if isinstance(display, dict) and display.get("text") is not None:
        return display["text"]
    return detail.get("text")


def detail_rows(detail):
    """Every labelled row of every table, as label -> rendered value.

    Later rows win when a label appears twice, which is what the app shows
    last as well.
    """
    rows = OrderedDict()
    for section in sections_of(detail, "table"):
        data = section.get("data")
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            label = row.get("title")
            if not label:
                continue
            rows[label] = _row_text(row)
    return rows


def detail_row(detail, *labels):
    """The value of the first row whose label matches.

    Matching ignores case and surrounding whitespace, so "Gebühr" also finds
    a row labelled "GEBÜHR ".
    """
    rows = detail_rows(detail)
    normalised = {str(k).strip().casefold(): v for k, v in rows.items()}
    for label in labels:
        value = normalised.get(str(label).strip().casefold())
        if value is not None:
            return value
    return None


_LOGO_ISIN = re.compile(r"logos/([A-Z]{2}[A-Z0-9]{9}\d)/")


def detail_isin(detail):
    """The isin of the instrument a detail belongs to.

    The header links to the instrument, which is where the isin the events
    themselves never carried finally comes from. When the link is missing the
    logo of the instrument still carries it in its path.
    """
    for section in sections_of(detail, "header"):
        action = section.get("action")
        if isinstance(action, dict) and action.get("type") == "instrumentDetail":
            payload = action.get("payload")
            if payload:
                return str(payload)

    for section in sections_of(detail, "header"):
        data = section.get("data")
        if not isinstance(data, dict):
            continue
        icon = data.get("icon")
        asset = icon.get("asset") if isinstance(icon, dict) else None
        match = _LOGO_ISIN.search(str(asset or ""))
        if match:
            return match.group(1)
    return None


def detail_documents(detail):
    """The documents of a detail.

    Trade Republic attaches them in two different ways and only one of them
    is a plain link:

    * ``browserModal`` carries a ready to use URL in its payload
    * ``authenticatedBrowserModal`` carries an object with a ``path`` that
      has to be fetched with the cookies of the session

    :return: a list of dicts with "title", "id" and either "url" or "path".
        Both keys are always present, the one that does not apply is None.
    """
    documents = []
    for section in sections_of(detail):
        if section.get("type") not in ("documents", "documentGroup"):
            continue
        data = section.get("data")
        if not isinstance(data, list):
            continue

        for row in data:
            if not isinstance(row, dict):
                continue
            action = row.get("action")
            if not isinstance(action, dict):
                continue

            payload = action.get("payload")
            url, path = None, None

            if isinstance(payload, str) and payload.startswith("http"):
                url = payload
            elif isinstance(payload, dict):
                candidate = payload.get("path")
                if isinstance(candidate, str) and candidate:
                    path = candidate
            if url is None and path is None:
                continue

            documents.append({
                "title": row.get("title") or "",
                "url": url,
                "path": path,
                "id": row.get("id"),
            })
    return documents


def document_url(document, host="https://api.traderepublic.com"):
    """The address a document is fetched from.

    A document that came as a path needs the session, so fetch that one
    through the requests session of a logged in client rather than plainly.
    """
    if document.get("url"):
        return document["url"]
    path = document.get("path")
    if not path:
        return None
    return host.rstrip("/") + "/" + str(path).lstrip("/")


# ------------------------------------------------------------------ mapping

#: Labels of the rows the export reads, as the API renders them. It answers
#: in the language it was asked for, so both are listed. A detail has no row
#: per value: a trade renders as one "transaction" row holding quantity and
#: price together, which is why there is no label for either on its own.
LABELS = {
    "transaction": ("Transaction", "Transaktion", "Ausf\u00fchrung"),
    "fee": ("Fee", "Fees", "Geb\u00fchr", "Geb\u00fchren",
            "Fremdkostenzuschlag"),
    "tax": ("Tax", "Taxes", "Steuer", "Steuern", "Kapitalertragsteuer"),
    "total": ("Total", "Gesamt", "Summe"),
    "accrued": ("Accrued", "Angefallen", "Erhalten"),
}

#: eventType of an event -> what it means for the export. "trade" takes its
#: direction from the sign of the amount, everything else is fixed.
#:
#: Recorded against a real account in August 2026. Events that are not listed
#: are reported by the converter instead of being dropped, so a new kind shows
#: up rather than going missing.
EVENT_TYPES = {
    # Securities. ORDER_EXECUTED and SAVINGS_PLAN_EXECUTED are the older
    # names and still appear on entries from back then.
    "TRADING_TRADE_EXECUTED": "trade",
    "ORDER_EXECUTED": "trade",
    "TRADING_SAVINGSPLAN_EXECUTED": "buy",
    "SAVINGS_PLAN_EXECUTED": "buy",
    # Round-ups and the saveback bonus end in a purchase as well, and their
    # detail carries the instrument and a transaction row like a trade does.
    "SPARE_CHANGE_AGGREGATE": "buy",
    "SAVEBACK_AGGREGATE": "buy",
    # Cash
    "BANK_TRANSACTION_INCOMING": "deposit",
    "PAYMENT_INBOUND_SEPA_DIRECT_DEBIT": "deposit",
    "BANK_TRANSACTION_OUTGOING": "removal",
    "PAYMENT_OUTBOUND": "removal",
    "CARD_TRANSACTION": "removal",
    # Income
    "INTEREST_PAYOUT": "interest",
    "SSP_CORPORATE_ACTION_CASH": "dividend",
}

#: Events deliberately left out, with the reason. They are listed here rather
#: than only in EVENT_TYPES so that the next person does not have to work out
#: why they are missing.
NOT_EXPORTED = {
    # The invoice for a trade that is already in the export under its own
    # event. Exporting both would count the same trade twice.
    "TRADE_INVOICE": "the trade itself is already exported",
    "SAVINGS_PLAN_INVOICE_CREATED": "the execution itself is already exported",
    # Announces a payout that arrives as INTEREST_PAYOUT.
    "INTEREST_PAYOUT_CREATED": "the payout itself is already exported",
    # Card housekeeping rather than money that moved.
    "CARD_VERIFICATION": "no money moves",
    "CARD_AFT": "unclear which way the money goes, needs checking",
}

#: Column titles, kept as they were so existing import profiles still match.
COLUMNS = {
    "de": ["Datum", "Typ", "Stück", "Kurs", "Wert", "Gebühren", "Steuern",
           "ISIN", "Name", "Buchungswährung"],
    "en": ["Date", "Type", "Shares", "Price", "Value", "Fees", "Taxes",
           "ISIN", "Name", "Currency"],
}

KINDS = {
    "de": {"buy": "Kauf", "sell": "Verkauf", "deposit": "Einlage",
           "removal": "Entnahme", "dividend": "Dividende",
           "interest": "Zinsen"},
    "en": {"buy": "Buy", "sell": "Sell", "deposit": "Deposit",
           "removal": "Removal", "dividend": "Dividend",
           "interest": "Interest"},
}


class Transaction(object):
    """One row of the export."""

    __slots__ = ("date", "kind", "shares", "price", "value", "fee", "tax",
                 "isin", "name", "currency", "event_type", "event_id")

    def __init__(self, **fields):
        for slot in self.__slots__:
            setattr(self, slot, fields.get(slot))

    def as_row(self, locale="de"):
        kinds = KINDS.get(locale, KINDS["en"])
        return [
            self.date.strftime("%Y-%m-%d") if self.date else "",
            kinds.get(self.kind, self.kind or ""),
            _plain(self.shares),
            _plain(self.price),
            _plain(self.value),
            _plain(self.fee),
            _plain(self.tax),
            self.isin or "",
            self.name or "",
            self.currency or "",
        ]

    def __repr__(self):
        return "<Transaction %s %s %s>" % (self.date, self.kind, self.value)


def _plain(value):
    return "" if value is None else str(value)


def transaction_of(event, detail=None, decimal_separator=None):
    """Turns a timeline event and its detail into a :class:`Transaction`.

    :param event: one entry of a timelineTransactions response
    :param detail: the matching timelineDetailV2 response, optional. Without
        it there is no quantity, no price and no isin, because the event does
        not carry them.
    :param decimal_separator: "," or "." to skip the per value detection
    :return: the transaction, or None when the event is not one. Cancelled
        events, deleted ones and events whose type is not in
        :data:`EVENT_TYPES` are skipped.
    """
    if not isinstance(event, dict):
        return None
    if event.get("deleted"):
        return None

    status = (event.get("status") or "").upper()
    if status in ("CANCELED", "CANCELLED", "REJECTED", "FAILED"):
        return None

    kind = EVENT_TYPES.get(event.get("eventType"))
    if kind is None:
        return None

    amount = event.get("amount") or {}
    value = parse_decimal(amount.get("value"), decimal_separator)

    if kind == "trade":
        if value is None:
            return None
        # Money leaving the account pays for something.
        kind = "buy" if value < 0 else "sell"

    def value_of(key):
        return parse_decimal(detail_row(detail, *LABELS[key]), decimal_separator)

    quantity, price = None, None
    if detail is not None:
        quantity, price = parse_quantity_and_price(
            detail_row(detail, *LABELS["transaction"]))
        if value is None:
            value = value_of("total")

    return Transaction(
        date=parse_timestamp(event.get("timestamp")),
        kind=kind,
        shares=quantity,
        price=price,
        value=abs(value) if value is not None else None,
        fee=value_of("fee") if detail is not None else None,
        tax=value_of("tax") if detail is not None else None,
        isin=detail_isin(detail) if detail is not None else None,
        name=event.get("title"),
        currency=amount.get("currency"),
        event_type=event.get("eventType"),
        event_id=event.get("id"),
    )


def write_csv(transactions, stream, locale="de"):
    """Writes the transactions in the format the old exporter produced.

    Unlike that one this goes through the csv module, so a name containing a
    semicolon no longer breaks the file apart.
    """
    writer = csv.writer(stream, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS.get(locale, COLUMNS["en"]))
    for transaction in transactions:
        writer.writerow(transaction.as_row(locale))
