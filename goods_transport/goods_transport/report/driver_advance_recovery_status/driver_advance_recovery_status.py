"""Driver Advance Recovery Status — open trip advances per driver."""

import frappe
from frappe import _
from frappe.utils import flt

from goods_transport.goods_transport.services import advances as advance_service


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		filters.company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 140},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 160},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Advance"), "fieldname": "trip_advance", "fieldtype": "Link", "options": "Trip Advance", "width": 150},
		{"label": _("Date"), "fieldname": "advance_date", "fieldtype": "Date", "width": 95},
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 140},
		{"label": _("Advanced"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Spent on Trip"), "fieldname": "consumed", "fieldtype": "Currency", "width": 130},
		{"label": _("Recovered from Salary"), "fieldname": "recovered", "fieldtype": "Currency", "width": 170},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	drivers = frappe.get_all("Driver", fields=["name", "full_name", "employee"])
	if filters.get("driver"):
		drivers = [d for d in drivers if d.name == filters.driver]

	rows = []
	for driver in drivers:
		open_rows = advance_service.get_driver_outstanding_advances(driver.name, filters.company)
		for adv in open_rows:
			rows.append({
				"driver": driver.name,
				"driver_name": driver.full_name,
				"employee": driver.employee,
				"trip_advance": adv["name"],
				"advance_date": adv["advance_date"],
				"trip": adv["trip"],
				"amount": flt(adv["amount"]),
				"consumed": advance_service.get_consumed(adv["name"]),
				"recovered": advance_service.get_recovered(adv["name"]),
				"outstanding": flt(adv["outstanding"]),
			})
	rows.sort(key=lambda r: (r["driver_name"] or "", r["advance_date"]))
	return rows
