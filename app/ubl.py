from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

INVOICE_NAMESPACE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NAMESPACES = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


class UblReadError(ValueError):
    pass


class Severity(StrEnum):
    ERROR = "error"


@dataclass(frozen=True)
class Anomaly:
    code: str
    field: str
    message: str
    severity: Severity = Severity.ERROR


def _text(root: Element, path: str) -> str | None:
    element = root.find(path, NAMESPACES)
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _decimal(
    root: Element,
    path: str,
    field: str,
    anomalies: list[Anomaly],
) -> Decimal | None:
    raw_value = _text(root, path)
    if raw_value is None:
        anomalies.append(
            Anomaly("required_field_missing", field, f"{field} is required.")
        )
        return None
    try:
        return Decimal(raw_value)
    except InvalidOperation:
        anomalies.append(
            Anomaly("invalid_decimal", field, f"{field} must be a decimal number.")
        )
        return None


def _required_text(
    root: Element,
    path: str,
    field: str,
    anomalies: list[Anomaly],
) -> str | None:
    value = _text(root, path)
    if value is None:
        anomalies.append(
            Anomaly("required_field_missing", field, f"{field} is required.")
        )
    return value


def _decimal_as_string(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def read_ubl_invoice(path: Path) -> dict[str, Any]:
    try:
        root = ElementTree.parse(path).getroot()
    except (ParseError, DefusedXmlException) as error:
        raise UblReadError("The document is not well-formed XML.") from error

    if root.tag != f"{{{INVOICE_NAMESPACE}}}Invoice":
        raise UblReadError("The XML root is not a UBL Invoice document.")

    anomalies: list[Anomaly] = []
    invoice_number = _required_text(root, "cbc:ID", "invoice.number", anomalies)
    issue_date = _required_text(root, "cbc:IssueDate", "invoice.issue_date", anomalies)
    currency = _required_text(
        root, "cbc:DocumentCurrencyCode", "invoice.currency", anomalies
    )
    supplier_name = _required_text(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
        "supplier.name",
        anomalies,
    )
    customer_name = _required_text(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name",
        "customer.name",
        anomalies,
    )
    net_amount = _decimal(
        root,
        "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
        "amounts.net",
        anomalies,
    )
    tax_amount = _decimal(
        root, "cac:TaxTotal/cbc:TaxAmount", "amounts.tax", anomalies
    )
    gross_amount = _decimal(
        root,
        "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
        "amounts.gross",
        anomalies,
    )
    payable_amount = _decimal(
        root,
        "cac:LegalMonetaryTotal/cbc:PayableAmount",
        "amounts.payable",
        anomalies,
    )

    if issue_date is not None:
        try:
            date.fromisoformat(issue_date)
        except ValueError:
            anomalies.append(
                Anomaly(
                    "invalid_date",
                    "invoice.issue_date",
                    "invoice.issue_date must use the YYYY-MM-DD format.",
                )
            )

    if currency is not None and (len(currency) != 3 or not currency.isalpha()):
        anomalies.append(
            Anomaly(
                "invalid_currency",
                "invoice.currency",
                "invoice.currency must be a three-letter alphabetic code.",
            )
        )

    if None not in (net_amount, tax_amount, gross_amount):
        assert net_amount is not None
        assert tax_amount is not None
        assert gross_amount is not None
        if net_amount + tax_amount != gross_amount:
            anomalies.append(
                Anomaly(
                    "amounts_do_not_balance",
                    "amounts.gross",
                    "For this demonstrator, gross must equal net plus tax.",
                )
            )

    return {
        "format": "ubl",
        "validation_status": "valid" if not anomalies else "invalid",
        "invoice": {
            "number": invoice_number,
            "issue_date": issue_date,
            "currency": currency.upper() if currency else None,
            "supplier": {"name": supplier_name},
            "customer": {"name": customer_name},
            "amounts": {
                "net": _decimal_as_string(net_amount),
                "tax": _decimal_as_string(tax_amount),
                "gross": _decimal_as_string(gross_amount),
                "payable": _decimal_as_string(payable_amount),
            },
        },
        "anomalies": [asdict(anomaly) for anomaly in anomalies],
    }
