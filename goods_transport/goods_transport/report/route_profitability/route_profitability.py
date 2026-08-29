import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND t.docstatus = 1"
	values = {}
	if filters.get("company"):
		conditions += " AND t.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions += " AND t.trip_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND t.trip_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(
		f"""
		SELECT
			COALESCE(t.origin, '(unspecified)') AS origin,
			COALESCE(t.destination, '(unspecified)') AS destination,
			COUNT(DISTINCT t.name) AS trip_count,
			COALESCE(SUM(CASE WHEN acc.root_type='Income'  THEN gle.credit - gle.debit ELSE 0 END), 0) AS revenue,
			COALESCE(SUM(CASE WHEN acc.root_type='Expense' THEN gle.debit  - gle.credit ELSE 0 END), 0) AS cost,
			AVG(t.actual_distance) AS avg_distance
		FROM `tabTransport Trip` t
		LEFT JOIN `tabGL Entry` gle ON gle.transport_trip = t.name AND gle.is_cancelled = 0
		LEFT JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE 1=1 {conditions}
		GROUP BY origin, destination
		ORDER BY revenue DESC
		""",
		values, as_dict=1,
	)
	for r in rows:
		r["profit"] = (r["revenue"] or 0) - (r["cost"] or 0)
		r["margin_percent"] = (r["profit"] / r["revenue"] * 100) if r["revenue"] else 0
		r["avg_revenue"] = (r["revenue"] or 0) / r["trip_count"] if r["trip_count"] else 0
		r["avg_cost"] = (r["cost"] or 0) / r["trip_count"] if r["trip_count"] else 0
	return _columns(), rows


def _columns():
	return [
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Data", "width": 150},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 150},
		{"label": _("Trips"), "fieldname": "trip_count", "fieldtype": "Int", "width": 70},
		{"label": _("Avg Distance"), "fieldname": "avg_distance", "fieldtype": "Float", "width": 100},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 130},
		{"label": _("Avg Revenue"), "fieldname": "avg_revenue", "fieldtype": "Currency", "width": 130},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Avg Cost"), "fieldname": "avg_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
	]
