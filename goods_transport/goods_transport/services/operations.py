"""Cross-document actions for the operational spine:
Transport Order → Transport Trip → Bilty → Proof of Delivery.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today


@frappe.whitelist()
def create_trip_from_order(transport_order: str, vehicle: str, quantity: float | None = None) -> str:
	"""Create a draft Transport Trip prefilled from the given Transport Order.

	The Trip itself has no direct link to the Order — the relationship is
	established when Bilties are created under the Trip referencing the Order.
	"""
	order = frappe.get_doc("Transport Order", transport_order)
	if order.docstatus != 1:
		frappe.throw(_("Transport Order {0} must be submitted first.").format(order.name))

	trip = frappe.new_doc("Transport Trip")
	trip.company = order.company
	trip.trip_date = today()
	trip.vehicle = vehicle
	trip.origin = order.origin
	trip.destination = order.destination
	trip.currency = order.currency
	trip.insert(ignore_permissions=False)
	return trip.name


@frappe.whitelist()
def create_bilty_from_trip(
	transport_trip: str,
	customer: str,
	transport_order: str | None = None,
	freight_item: str | None = None,
	rate: float | None = None,
	rate_basis: str | None = None,
	freight_quantity: float | None = None,
) -> str:
	"""Create a draft Bilty against a Trip. Fills origin/destination/vehicle
	from the Trip and, when given, the Order."""
	trip = frappe.get_doc("Transport Trip", transport_trip)
	if trip.docstatus == 2:
		frappe.throw(_("Cannot create Bilty against a cancelled Trip."))

	bilty = frappe.new_doc("Bilty")
	bilty.company = trip.company
	bilty.bilty_date = today()
	bilty.customer = customer
	bilty.transport_trip = trip.name
	bilty.transport_order = transport_order
	bilty.origin = trip.origin
	bilty.destination = trip.destination
	bilty.vehicle = trip.vehicle
	bilty.driver = trip.driver
	bilty.transporter = trip.transporter
	bilty.currency = trip.currency

	if freight_item:
		bilty.freight_item = freight_item
	if rate is not None:
		bilty.rate = flt(rate)
	if rate_basis:
		bilty.rate_basis = rate_basis
	if freight_quantity is not None:
		bilty.freight_quantity = flt(freight_quantity)

	bilty.insert(ignore_permissions=False)
	return bilty.name


@frappe.whitelist()
def create_pod_from_bilty(bilty: str, delivered_quantity: float, receiver_name: str) -> str:
	"""Convenience: create+submit a POD in one call from a Bilty form action."""
	source = frappe.get_doc("Bilty", bilty)
	if source.docstatus != 1:
		frappe.throw(_("Bilty must be submitted before recording POD."))
	if frappe.db.exists("Proof of Delivery", {"bilty": bilty, "docstatus": ["!=", 2]}):
		frappe.throw(_("A Proof of Delivery already exists for Bilty {0}.").format(bilty))

	pod = frappe.new_doc("Proof of Delivery")
	pod.bilty = bilty
	pod.delivery_date = today()
	pod.delivered_quantity = flt(delivered_quantity)
	pod.receiver_name = receiver_name
	pod.insert()
	pod.submit()
	return pod.name


@frappe.whitelist()
def get_order_bilties(transport_order: str) -> list[dict]:
	return frappe.get_all(
		"Bilty",
		filters={"transport_order": transport_order},
		fields=[
			"name",
			"bilty_date",
			"status",
			"transport_trip",
			"total_quantity",
			"pod_status",
			"sales_invoice",
		],
		order_by="bilty_date",
	)


@frappe.whitelist()
def create_transporter_purchase_invoice(
	transport_trip: str,
	hire_item: str,
	expense_account: str,
	amount: float | None = None,
) -> str:
	"""Draft a Purchase Invoice to the Trip's transporter for the agreed vehicle hire.

	If `amount` is not supplied, uses `Transport Trip.agreed_vehicle_hire`. The PI is
	created in draft state — user reviews / adds taxes / submits it themselves."""
	trip = frappe.get_doc("Transport Trip", transport_trip)
	if trip.docstatus != 1:
		frappe.throw(_("Trip {0} must be submitted first.").format(trip.name))
	if not trip.transporter:
		frappe.throw(_("Trip {0} has no Transporter set.").format(trip.name))
	if trip.purchase_invoice:
		existing = trip.purchase_invoice
		if frappe.db.get_value("Purchase Invoice", existing, "docstatus") != 2:
			frappe.throw(
				_("Trip {0} is already linked to Purchase Invoice {1}.").format(trip.name, existing)
			)

	from frappe.utils import flt, today

	hire_amount = flt(amount) if amount is not None else flt(trip.agreed_vehicle_hire)
	if hire_amount <= 0:
		frappe.throw(_("Vehicle hire amount must be greater than zero."))

	cost_center = frappe.get_cached_value("Company", trip.company, "cost_center")
	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = trip.transporter
	pi.company = trip.company
	pi.currency = trip.currency
	pi.posting_date = today()
	pi.set_posting_time = 1
	if pi.meta.has_field("transport_trip"):
		pi.transport_trip = trip.name
	row = pi.append(
		"items",
		{
			"item_code": hire_item,
			"description": _("Vehicle hire — {0} ({1} → {2})").format(
				trip.vehicle_license_plate or trip.vehicle, trip.origin or "", trip.destination or ""
			),
			"qty": 1,
			"rate": hire_amount,
			"expense_account": expense_account,
			"cost_center": cost_center,
		},
	)
	if row.meta.has_field("transport_trip"):
		row.transport_trip = trip.name
	pi.insert()
	trip.db_set("purchase_invoice", pi.name)
	return pi.name


@frappe.whitelist()
def get_trip_bilties(transport_trip: str) -> list[dict]:
	return frappe.get_all(
		"Bilty",
		filters={"transport_trip": transport_trip},
		fields=[
			"name",
			"customer",
			"customer_name",
			"origin",
			"destination",
			"total_gross_weight",
			"grand_total",
			"status",
			"pod_status",
		],
		order_by="bilty_date",
	)
