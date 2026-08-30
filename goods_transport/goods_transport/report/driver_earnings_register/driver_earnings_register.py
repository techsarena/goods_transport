"""Driver Earnings Register — every trip-based earning in a period."""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Earning"), "fieldname": "name", "fieldtype": "Link", "options": "Driver Trip Earning", "width": 150},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 95},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 130},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 150},
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 140},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Transport Route", "width": 150},
		{"label": _("KM"), "fieldname": "distance_km", "fieldtype": "Float", "width": 80},
		{"label": _("Tons"), "fieldname": "loaded_tons", "fieldtype": "Float", "precision": 3, "width": 80},
		{"label": _("Trip Amt"), "fieldname": "trip_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Distance Amt"), "fieldname": "km_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Tonnage Amt"), "fieldname": "tonnage_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Commission"), "fieldname": "commission_amount", "fieldtype": "Currency", "width": 115},
		{"label": _("Total Earning"), "fieldname": "total_earning", "fieldtype": "Currency", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 95},
		{"label": _("Payroll Run"), "fieldname": "payroll_run", "fieldtype": "Link", "options": "Driver Payroll Run", "width": 150},
	]


def get_data(filters):
	conditions = ["1 = 1"]
	values = {}
	for key, column in (("company", "company"), ("driver", "driver"), ("status", "status")):
		if filters.get(key):
			conditions.append(f"e.{column} = %({key})s")
			values[key] = filters.get(key)
	if filters.get("from_date"):
		conditions.append("e.trip_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("e.trip_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	return frappe.db.sql(
		f"""SELECT e.name, e.trip_date, e.driver, e.driver_name, e.trip, e.route,
			e.distance_km, e.loaded_tons, e.trip_amount, e.km_amount,
			e.tonnage_amount, e.commission_amount, e.total_earning, e.status,
			e.payroll_run
		FROM `tabDriver Trip Earning` e
		WHERE {" AND ".join(conditions)}
		ORDER BY e.trip_date DESC, e.driver""",
		values,
		as_dict=True,
	)
