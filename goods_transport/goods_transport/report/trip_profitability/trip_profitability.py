"""Trip Profitability — direct read from the General Ledger via the
transport_trip accounting dimension. Numbers match Trip Settlement
figures because both derive from the same posted documents."""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND gle.is_cancelled = 0 AND gle.transport_trip IS NOT NULL AND gle.transport_trip != ''"
	values = {}
	if filters.get("company"):
		conditions += " AND gle.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions += " AND gle.posting_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND gle.posting_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]
	if filters.get("trip"):
		conditions += " AND gle.transport_trip = %(trip)s"
		values["trip"] = filters["trip"]

	rows = frappe.db.sql(
		f"""
		SELECT
			gle.transport_trip                                                     AS trip,
			COALESCE(t.trip_date, MIN(gle.posting_date))                           AS trip_date,
			t.vehicle_license_plate                                                AS vehicle,
			t.status                                                               AS status,
			SUM(CASE WHEN acc.root_type = 'Income'   THEN gle.credit - gle.debit ELSE 0 END) AS revenue,
			SUM(CASE WHEN acc.root_type = 'Expense'  THEN gle.debit  - gle.credit ELSE 0 END) AS cost,
			SUM(CASE WHEN acc.root_type = 'Income'   THEN gle.credit - gle.debit ELSE 0 END) -
			SUM(CASE WHEN acc.root_type = 'Expense'  THEN gle.debit  - gle.credit ELSE 0 END) AS gross_profit,
			gle.company                                                            AS company
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		LEFT JOIN `tabTransport Trip` t ON t.name = gle.transport_trip
		WHERE 1=1 {conditions}
		GROUP BY gle.transport_trip
		ORDER BY trip_date DESC, gle.transport_trip DESC
		""",
		values,
		as_dict=1,
	)
	for r in rows:
		r["margin_percent"] = (r["gross_profit"] / r["revenue"] * 100) if r["revenue"] else 0

	return _columns(), rows


def _columns():
	return [
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 150},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 100},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Data", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 100},
	]
