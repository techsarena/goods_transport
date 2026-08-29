"""Vehicle Trip History — one row per trip for the selected vehicle(s).
Revenue and cost are read from the GL by transport_trip dimension so numbers
match Trip Profitability."""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND t.docstatus = 1"
	values = {}
	if filters.get("company"):
		conditions += " AND t.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("vehicle"):
		conditions += " AND t.vehicle = %(vehicle)s"
		values["vehicle"] = filters["vehicle"]
	if filters.get("from_date"):
		conditions += " AND t.trip_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND t.trip_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(
		f"""
		SELECT
			t.name AS trip, t.trip_date, t.status,
			t.vehicle, t.vehicle_license_plate AS plate, t.driver_name AS driver,
			t.origin, t.destination,
			t.planned_distance, t.actual_distance,
			t.loaded_weight, t.bilty_count,
			COALESCE(SUM(CASE WHEN acc.root_type='Income'  THEN gle.credit - gle.debit ELSE 0 END), 0) AS revenue,
			COALESCE(SUM(CASE WHEN acc.root_type='Expense' THEN gle.debit  - gle.credit ELSE 0 END), 0) AS cost,
			COALESCE(SUM(CASE WHEN acc.root_type='Income'  THEN gle.credit - gle.debit ELSE 0 END), 0) -
			COALESCE(SUM(CASE WHEN acc.root_type='Expense' THEN gle.debit  - gle.credit ELSE 0 END), 0) AS profit
		FROM `tabTransport Trip` t
		LEFT JOIN `tabGL Entry` gle
		  ON gle.transport_trip = t.name AND gle.is_cancelled = 0
		LEFT JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE 1=1 {conditions}
		GROUP BY t.name
		ORDER BY t.vehicle, t.trip_date DESC, t.name DESC
		""",
		values, as_dict=1,
	)
	for r in rows:
		r["margin_percent"] = (r["profit"] / r["revenue"] * 100) if r["revenue"] else 0
	return _columns(), rows


def _columns():
	return [
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 110},
		{"label": _("Plate"), "fieldname": "plate", "fieldtype": "Data", "width": 90},
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 150},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Data", "width": 130},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Planned km"), "fieldname": "planned_distance", "fieldtype": "Float", "width": 90},
		{"label": _("Actual km"), "fieldname": "actual_distance", "fieldtype": "Float", "width": 90},
		{"label": _("Bilties"), "fieldname": "bilty_count", "fieldtype": "Int", "width": 70},
		{"label": _("Loaded (kg)"), "fieldname": "loaded_weight", "fieldtype": "Float", "width": 100},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
	]
