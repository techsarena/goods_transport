"""Trip-based driver earnings: rule resolution and Driver Trip Earning creation.

A completed Trip earns the driver up to four amounts, each optional:

	per_trip_amount              flat amount for running the trip
	rate_per_km x distance       actual_distance, else planned_distance, else route distance
	rate_per_ton x tonnage       Trip.loaded_weight (kg) / 1000
	commission_percent x freight sum of submitted Bilty.freight_amount on the Trip

Rules are resolved most-specific-first, exactly like Transport Rate Contract:

	driver -> vehicle_type + route -> vehicle_type -> route -> company default
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

#: Trip statuses that mean the driver has finished the job and may be paid.
EARNABLE_TRIP_STATUS = ("Delivered", "Settled", "Closed")


def resolve_pay_rule(
	company: str,
	driver: str | None = None,
	vehicle_type: str | None = None,
	route: str | None = None,
	on_date: str | None = None,
) -> str | None:
	"""Return the name of the most specific active Driver Pay Rule that applies."""
	on_date = getdate(on_date) if on_date else frappe.utils.nowdate()

	base = ["is_active = 1", "company = %(company)s"]
	values = {"company": company, "on_date": on_date, "driver": driver,
		"vehicle_type": vehicle_type, "route": route}
	base.append("(valid_from IS NULL OR valid_from = '' OR valid_from <= %(on_date)s)")
	base.append("(valid_upto IS NULL OR valid_upto = '' OR valid_upto >= %(on_date)s)")

	def _blank(field):
		return f"({field} IS NULL OR {field} = '')"

	# Ordered most specific -> least specific.
	candidates = []
	if driver:
		candidates.append(["driver = %(driver)s"])
	if vehicle_type and route:
		candidates.append([_blank("driver"), "vehicle_type = %(vehicle_type)s",
			"route = %(route)s"])
	if vehicle_type:
		candidates.append([_blank("driver"), "vehicle_type = %(vehicle_type)s",
			_blank("route")])
	if route:
		candidates.append([_blank("driver"), _blank("vehicle_type"), "route = %(route)s"])
	candidates.append([_blank("driver"), _blank("vehicle_type"), _blank("route")])

	for extra in candidates:
		rows = frappe.db.sql(
			f"""SELECT name FROM `tabDriver Pay Rule`
			WHERE {" AND ".join(base + extra)}
			ORDER BY modified DESC LIMIT 1""",
			values,
		)
		if rows:
			return rows[0][0]
	return None


def get_trip_distance(trip) -> float:
	"""Actual distance, else planned, else the Route's standard distance."""
	if flt(trip.actual_distance):
		return flt(trip.actual_distance)
	if flt(trip.planned_distance):
		return flt(trip.planned_distance)
	if trip.route:
		return flt(frappe.db.get_value("Transport Route", trip.route, "distance_km"))
	return 0.0


def get_trip_freight_revenue(trip_name: str) -> float:
	"""Freight booked to customers on this Trip (submitted Bilties)."""
	return flt(
		frappe.db.sql(
			"""SELECT COALESCE(SUM(freight_amount), 0) FROM `tabBilty`
			WHERE transport_trip = %s AND docstatus = 1""",
			(trip_name,),
		)[0][0]
	)


def compute_earning(trip, rule_name: str) -> dict:
	"""Compute every earning component for a Trip under a given rule."""
	rule = frappe.get_cached_doc("Driver Pay Rule", rule_name)

	distance = get_trip_distance(trip)
	tons = flt(trip.loaded_weight) / 1000.0
	revenue = get_trip_freight_revenue(trip.name) if flt(rule.commission_percent) else 0.0

	trip_amount = flt(rule.per_trip_amount)
	km_amount = flt(rule.rate_per_km) * distance
	tonnage_amount = flt(rule.rate_per_ton) * tons
	commission_amount = revenue * flt(rule.commission_percent) / 100.0

	return {
		"pay_rule": rule.name,
		"distance_km": distance,
		"loaded_tons": tons,
		"trip_revenue": revenue,
		"trip_amount": trip_amount,
		"km_amount": km_amount,
		"tonnage_amount": tonnage_amount,
		"commission_amount": commission_amount,
		"total_earning": trip_amount + km_amount + tonnage_amount + commission_amount,
	}


def ensure_trip_earning(trip_name: str, throw: bool = False) -> str | None:
	"""Create or refresh the Driver Trip Earning for a Trip. Idempotent.

	Returns the earning name, or None when the Trip does not qualify.
	A Pending earning is recomputed in place; a Processed one is never touched.
	"""
	trip = frappe.get_doc("Transport Trip", trip_name)

	def _skip(msg):
		if throw:
			frappe.throw(msg)
		return None

	if trip.docstatus != 1:
		return _skip(_("Trip {0} is not submitted.").format(trip_name))
	if trip.status not in EARNABLE_TRIP_STATUS:
		return _skip(
			_("Trip {0} is {1} — driver earnings are generated once it reaches {2}.").format(
				trip_name, trip.status, " / ".join(EARNABLE_TRIP_STATUS)
			)
		)
	if not trip.driver:
		return _skip(_("Trip {0} has no Driver.").format(trip_name))

	# Only drivers on our payroll earn trip pay. A market-vehicle driver is
	# paid by the vehicle owner out of the hire we pay them, so they have no
	# Employee record and must not produce payroll input.
	employee = frappe.db.get_value("Driver", trip.driver, "employee")
	if not employee:
		return _skip(
			_("Driver {0} has no linked Employee, so no payroll earning is generated. "
			  "Link an Employee on the Driver record if this driver is on our payroll.").format(
				frappe.db.get_value("Driver", trip.driver, "full_name") or trip.driver
			)
		)

	vehicle_type = frappe.db.get_value("Vehicle", trip.vehicle, "vehicle_type") if trip.vehicle else None
	rule_name = resolve_pay_rule(
		company=trip.company, driver=trip.driver, vehicle_type=vehicle_type,
		route=trip.route, on_date=trip.trip_date,
	)
	if not rule_name:
		return _skip(
			_("No active Driver Pay Rule matches Trip {0}. Create a company-wide default rule.").format(trip_name)
		)

	values = compute_earning(trip, rule_name)
	if values["total_earning"] <= 0:
		return _skip(_("Pay Rule {0} yields no earning for Trip {1}.").format(rule_name, trip_name))

	existing = frappe.db.get_value(
		"Driver Trip Earning", {"trip": trip_name}, ["name", "status"], as_dict=True
	)
	if existing and existing.status == "Processed":
		return existing.name

	values.update({
		"driver": trip.driver,
		"employee": employee,
		"company": trip.company,
		"trip": trip.name,
		"trip_date": trip.trip_date,
		"route": trip.route,
		"vehicle": trip.vehicle,
		"currency": trip.currency,
		"status": "Pending",
	})

	if existing:
		doc = frappe.get_doc("Driver Trip Earning", existing.name)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.new_doc("Driver Trip Earning")
	doc.update(values)
	doc.insert(ignore_permissions=True)
	return doc.name


def generate_earnings_for_period(company: str, from_date: str, to_date: str) -> dict:
	"""Scan completed Trips in a window and make sure each has an earning row."""
	trips = frappe.get_all(
		"Transport Trip",
		filters={
			"company": company,
			"docstatus": 1,
			"status": ["in", EARNABLE_TRIP_STATUS],
			"trip_date": ["between", [from_date, to_date]],
			"driver": ["is", "set"],
		},
		pluck="name",
	)
	created, skipped = [], []
	for name in trips:
		try:
			if ensure_trip_earning(name):
				created.append(name)
			else:
				skipped.append(name)
		except Exception:
			frappe.log_error(
				title="Driver trip earning failed", message=frappe.get_traceback()
			)
			skipped.append(name)
	return {"trips": len(trips), "earned": len(created), "skipped": len(skipped)}


# --- document hooks ----------------------------------------------------------

def on_trip_settlement_submit(doc, method=None):
	"""Trip Settlement submit locks the Trip as Settled — earn the driver then."""
	from goods_transport.goods_transport.services import settlement as settlement_service

	try:
		if ensure_trip_earning(doc.trip):
			settlement_service.refresh_after_earning(doc.trip)
	except Exception:
		frappe.log_error(title="Driver trip earning failed", message=frappe.get_traceback())


def on_trip_cancel(doc, method=None):
	"""Cancelling a Trip voids a Pending earning; a Processed one blocks the cancel."""
	rows = frappe.get_all(
		"Driver Trip Earning", filters={"trip": doc.name}, fields=["name", "status"]
	)
	for row in rows:
		if row.status == "Processed":
			frappe.throw(
				_("Trip {0} has driver earnings already paid through a Driver Payroll Run. "
				  "Cancel that run first.").format(doc.name)
			)
		frappe.db.set_value("Driver Trip Earning", row.name, "status", "Cancelled")


@frappe.whitelist()
def generate_for_trip(trip: str) -> str | None:
	"""Whitelisted button target on the Transport Trip form."""
	from goods_transport.goods_transport.services import settlement as settlement_service

	name = ensure_trip_earning(trip, throw=True)
	settlement_service.refresh_after_earning(trip)
	frappe.msgprint(_("Driver Trip Earning {0} created.").format(name), alert=True)
	return name
