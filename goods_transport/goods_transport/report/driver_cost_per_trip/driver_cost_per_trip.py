"""Driver Cost Per Trip — what each completed trip cost in driver pay.

Joins the trip-based earning to the trip's freight revenue so the operations
manager can see driver pay as a percentage of what the trip billed.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 150},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 95},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 120},
		{"label": _("Driver"), "fieldname": "driver_name", "fieldtype": "Data", "width": 150},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Transport Route", "width": 150},
		{"label": _("Freight Revenue"), "fieldname": "trip_revenue", "fieldtype": "Currency", "width": 140},
		{"label": _("Driver Pay"), "fieldname": "total_earning", "fieldtype": "Currency", "width": 130},
		{"label": _("Advance Issued"), "fieldname": "advance", "fieldtype": "Currency", "width": 140},
		{"label": _("Driver Pay %"), "fieldname": "pay_percent", "fieldtype": "Percent", "width": 120},
	]


def get_data(filters):
	conditions = ["1 = 1"]
	values = {}
	if filters.get("company"):
		conditions.append("e.company = %(company)s")
		values["company"] = filters.company
	if filters.get("from_date"):
		conditions.append("e.trip_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("e.trip_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	rows = frappe.db.sql(
		f"""SELECT e.trip, e.trip_date, e.vehicle, e.driver_name, e.route,
			e.total_earning,
			(SELECT COALESCE(SUM(b.freight_amount), 0) FROM `tabBilty` b
				WHERE b.transport_trip = e.trip AND b.docstatus = 1) AS trip_revenue,
			(SELECT COALESCE(SUM(a.amount), 0) FROM `tabTrip Advance` a
				WHERE a.trip = e.trip AND a.docstatus = 1) AS advance
		FROM `tabDriver Trip Earning` e
		WHERE {" AND ".join(conditions)}
		ORDER BY e.trip_date DESC""",
		values,
		as_dict=True,
	)
	for r in rows:
		r["pay_percent"] = (flt(r.total_earning) / flt(r.trip_revenue) * 100) if flt(r.trip_revenue) else 0
	return rows
