"""Bilty → Sales Invoice consolidation service.

One customer's delivered / unbilled Bilties are consolidated into a single draft
Sales Invoice with one row per Bilty freight line plus one row per billable
Bilty Charge. Each source Bilty is back-linked via the `bilty_references` child
table on Sales Invoice and marked `Billed`.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, today


@frappe.whitelist()
def create_sales_invoice_from_bilties(bilties: str | list[str]) -> str:
	"""Create a draft Sales Invoice consolidating the given Bilties.

	Args:
	    bilties: List (or JSON-encoded list) of Bilty names.

	Returns:
	    Name of the newly created Sales Invoice.
	"""
	names = _parse_names(bilties)
	if not names:
		frappe.throw(_("No Bilties supplied."))

	docs = [frappe.get_doc("Bilty", n) for n in names]
	_validate_billable(docs)

	head = docs[0]
	si = frappe.new_doc("Sales Invoice")
	si.customer = head.billing_customer or head.customer
	si.company = head.company
	si.currency = head.currency
	si.posting_date = today()
	si.due_date = today()
	si.set("bilty_references", [])
	si.set("items", [])

	# If every consolidated Bilty belongs to the same Trip, propagate the
	# Trip to the SI header so the accounting dimension is set and every
	# resulting GL Entry is tagged.
	trips = {d.transport_trip for d in docs if d.transport_trip}
	if len(trips) == 1:
		trip = next(iter(trips))
		if si.meta.has_field("transport_trip"):
			si.transport_trip = trip

	for bilty in docs:
		_append_freight_row(si, bilty)
		for charge in bilty.charges or []:
			if not charge.billable_to_customer:
				continue
			_append_charge_row(si, bilty, charge)
		si.append(
			"bilty_references",
			{
				"bilty": bilty.name,
				"bilty_date": bilty.bilty_date,
				"customer": bilty.customer,
				"origin": bilty.origin,
				"destination": bilty.destination,
				"amount": bilty.grand_total,
			},
		)

	si.flags.ignore_permissions = False
	si.insert()

	for bilty in docs:
		frappe.db.set_value("Bilty", bilty.name, {"sales_invoice": si.name, "status": "Billed"})

	frappe.db.commit()
	return si.name


# ---------------------------------------------------------------------------


def _parse_names(bilties: str | list[str]) -> list[str]:
	if isinstance(bilties, str):
		try:
			parsed = json.loads(bilties)
		except json.JSONDecodeError:
			parsed = [bilties]
	else:
		parsed = list(bilties)
	# Deduplicate while preserving order.
	seen: set[str] = set()
	out: list[str] = []
	for n in parsed:
		if n and n not in seen:
			seen.add(n)
			out.append(n)
	return out


def _validate_billable(docs: list) -> None:
	billing_customers = {(d.billing_customer or d.customer) for d in docs}
	if len(billing_customers) > 1:
		frappe.throw(
			_("Selected Bilties belong to different billing customers: {0}").format(
				", ".join(sorted(billing_customers))
			)
		)
	companies = {d.company for d in docs}
	if len(companies) > 1:
		frappe.throw(_("Selected Bilties belong to different companies: {0}").format(", ".join(sorted(companies))))
	currencies = {d.currency for d in docs}
	if len(currencies) > 1:
		frappe.throw(_("Selected Bilties have different currencies: {0}").format(", ".join(sorted(currencies))))

	for d in docs:
		if d.docstatus != 1:
			frappe.throw(_("Bilty {0} is not submitted.").format(d.name))
		if d.sales_invoice:
			frappe.throw(
				_("Bilty {0} is already linked to Sales Invoice {1}.").format(d.name, d.sales_invoice)
			)
		if not d.freight_item:
			frappe.throw(_("Bilty {0} has no Freight Item set.").format(d.name))


def _append_freight_row(si, bilty) -> None:
	description = _("Freight for Bilty {0}: {1} → {2}").format(
		bilty.name, bilty.origin or "", bilty.destination or ""
	)
	row = si.append(
		"items",
		{
			"item_code": bilty.freight_item,
			"description": description,
			"qty": 1,
			"rate": flt(bilty.freight_amount),
		},
	)
	_set_row_trip_dimension(row, bilty.transport_trip)


def _append_charge_row(si, bilty, charge) -> None:
	description = charge.description or charge.item
	if bilty.name:
		description = f"{description} (Bilty {bilty.name})"
	row = si.append(
		"items",
		{
			"item_code": charge.item,
			"description": description,
			"qty": flt(charge.quantity) or 1,
			"rate": flt(charge.rate),
		},
	)
	_set_row_trip_dimension(row, bilty.transport_trip)


def _set_row_trip_dimension(row, trip: str | None) -> None:
	"""Per-row Trip dimension: needed when one SI consolidates Bilties from
	different Trips so each GL line ends up tagged with the right Trip."""
	if trip and row.meta.has_field("transport_trip"):
		row.transport_trip = trip


@frappe.whitelist()
def get_billable_bilties(customer: str | None = None, company: str | None = None) -> list[dict]:
	"""Convenience wrapper used by the Bilty list-view action."""
	from goods_transport.goods_transport.doctype.bilty.bilty import get_unbilled_bilties

	return get_unbilled_bilties(customer=customer, company=company)
