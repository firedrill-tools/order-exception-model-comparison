"""Coherence checks for fictional imported business history, not provider observations."""

from datetime import datetime
from .schema import OrderCase, Expectation


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("fixture history requires explicit timezone timestamps")
    return parsed


def validate_bundle(bundle):
    cases = [OrderCase.model_validate(row) for row in bundle["cases"]]
    if (
        not 1 <= len(cases) <= 64
        or len({row.case_id for row in cases}) != len(cases)
        or len({row.order_id for row in cases}) != len(cases)
    ):
        raise ValueError("fixture cases/orders must be bounded and unique")
    if set(bundle["expectations"]) != {case.case_id for case in cases}:
        raise ValueError("fixture needs exactly one external expectation per case")
    for value in bundle["expectations"].values():
        Expectation.model_validate(value)
    customers = bundle["customers"]
    ids = [row["customer_id"] for row in customers]
    if len(set(ids)) != len(ids) or any(
        set(row) != {"customer_id", "name"}
        or not isinstance(row["name"], str)
        or not row["name"].strip()
        for row in customers
    ):
        raise ValueError("invalid fictional customer directory")
    history = bundle["source_history"]
    if len(history) != len(cases) or {row["case_id"] for row in history} != {
        case.case_id for case in cases
    }:
        raise ValueError("source history does not match case population")
    by_case = {case.case_id: case for case in cases}
    event_ids = set()
    as_of = instant(bundle["as_of"])
    for row in history:
        case = by_case[row["case_id"]]
        if (
            row["order_id"] != case.order_id
            or row["customer_id"] not in ids
            or row["provenance"] != "fictional_imported_business_facts"
        ):
            raise ValueError("source history identity/provenance mismatch")
        request = row["request"]
        requested = instant(request["received_at"])
        if request["text"] != case.customer_request or requested > as_of:
            raise ValueError("source request differs from current facts")
        captured = refunded = 0
        last = None
        for payment in row["payments"]:
            if (
                set(payment)
                != {"event_id", "kind", "amount_cents", "occurred_at", "provenance"}
                or payment["event_id"] in event_ids
                or payment["kind"] not in {"capture", "refund"}
                or payment["provenance"] != "fictional_imported_business_facts"
                or type(payment["amount_cents"]) is not int
                or not 0 < payment["amount_cents"] <= 2**53 - 1
            ):
                raise ValueError("invalid source payment event")
            event_ids.add(payment["event_id"])
            occurred = instant(payment["occurred_at"])
            if occurred > requested or last is not None and occurred < last:
                raise ValueError("payment history chronology is inconsistent")
            last = occurred
            if payment["kind"] == "capture":
                captured += payment["amount_cents"]
            else:
                refunded += payment["amount_cents"]
            if refunded > captured:
                raise ValueError("source refund precedes available capture")
        if captured != case.captured_cents or refunded != case.refunded_cents:
            raise ValueError("source ledger differs from captured/refunded case facts")
        shipping = row["shipping"]
        if shipping["shipped"] is not case.shipped or shipping["status"] not in {
            "pending",
            "in_transit",
            "delivered",
        }:
            raise ValueError("source shipping status mismatch")
        if case.shipped:
            if (
                shipping["status"] == "pending"
                or instant(shipping["shipped_at"]) > requested
            ):
                raise ValueError("shipping history differs from request chronology")
            if (
                shipping["delivered_at"] is not None
                and not instant(shipping["shipped_at"])
                <= instant(shipping["delivered_at"])
                <= requested
            ):
                raise ValueError("invalid delivery chronology")
        elif (
            shipping["status"] != "pending"
            or shipping["shipped_at"] is not None
            or shipping["delivered_at"] is not None
        ):
            raise ValueError("unshipped source invents shipment")
        stock = row["stock_snapshot"]
        if (
            stock["available"] != case.replacement_stock
            or instant(stock["observed_at"]) > as_of
        ):
            raise ValueError("source stock snapshot mismatch")
    return cases
