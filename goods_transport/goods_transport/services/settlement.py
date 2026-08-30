"""Show driver trip pay on the Trip Settlement without disturbing its cost model."""

import frappe
from frappe.utils import flt


def _trip_pay(trip: str) -> float:
	return flt(
		frappe.db.get_value(
			"Driver Trip Earning",
			{"trip": trip, "status": ["!=", "Cancelled"]},
			"total_earning",
		)
	)


def attach_driver_pay(doc, method=None):
	"""Trip Settlement validate hook — runs after the controller's own validate,
	so gross_profit is already computed."""
	if not doc.meta.has_field("driver_trip_pay"):
		return
	doc.driver_trip_pay = _trip_pay(doc.trip)
	doc.profit_after_driver_pay = flt(doc.gross_profit) - flt(doc.driver_trip_pay)


def refresh_after_earning(trip: str):
	"""Called once the earning exists (created on Trip Settlement submit)."""
	pay = _trip_pay(trip)
	frappe.db.set_value("Transport Trip", trip, "driver_trip_pay", pay, update_modified=False)

	settlement = frappe.db.get_value(
		"Trip Settlement", {"trip": trip, "docstatus": ["<", 2]}, ["name", "gross_profit"], as_dict=True
	)
	if settlement:
		frappe.db.set_value(
			"Trip Settlement",
			settlement.name,
			{
				"driver_trip_pay": pay,
				"profit_after_driver_pay": flt(settlement.gross_profit) - pay,
			},
			update_modified=False,
		)
