"""Customer Profitability — revenue from Sales Invoices tagged with
transport_trip, cost from GL Expense rows on those same trips, apportioned
by revenue share when a single trip carries multiple customers."""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions_si = " AND si.docstatus = 1 AND si.transport_trip IS NOT NULL AND si.transport_trip != ''"
	values = {}
	if filters.get("company"):
		conditions_si += " AND si.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions_si += " AND si.posting_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions_si += " AND si.posting_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	# Revenue per customer per trip
	revenue_rows = frappe.db.sql(
		f"""
		SELECT si.customer, si.transport_trip AS trip, SUM(si.base_grand_total) AS revenue
		FROM `tabSales Invoice` si
		WHERE 1=1 {conditions_si}
		GROUP BY si.customer, si.transport_trip
		""",
		values, as_dict=1,
	)

	# Total revenue per trip (denominator for cost apportionment)
	trip_revenue = {}
	for r in revenue_rows:
		trip_revenue[r["trip"]] = trip_revenue.get(r["trip"], 0) + (r["revenue"] or 0)

	# Cost per trip from GL
	trip_ids = list(trip_revenue.keys())
	trip_cost = {}
	if trip_ids:
		gl_conditions = ""
		gl_values = {"trips": tuple(trip_ids)}
		if filters.get("company"):
			gl_conditions += " AND gle.company = %(company)s"
			gl_values["company"] = filters["company"]
		cost_rows = frappe.db.sql(
			f"""
			SELECT gle.transport_trip AS trip,
			       SUM(CASE WHEN acc.root_type='Expense' THEN gle.debit - gle.credit ELSE 0 END) AS cost
			FROM `tabGL Entry` gle
			INNER JOIN `tabAccount` acc ON acc.name = gle.account
			WHERE gle.is_cancelled = 0 AND gle.transport_trip IN %(trips)s {gl_conditions}
			GROUP BY gle.transport_trip
			""",
			gl_values, as_dict=1,
		)
		trip_cost = {r["trip"]: r["cost"] or 0 for r in cost_rows}

	# Aggregate by customer, apportioning trip cost by revenue share
	agg = {}
	for r in revenue_rows:
		trip = r["trip"]
		total_trip_rev = trip_revenue.get(trip) or 0
		share = (r["revenue"] or 0) / total_trip_rev if total_trip_rev else 0
		cust_cost = (trip_cost.get(trip) or 0) * share
		bucket = agg.setdefault(r["customer"], {"revenue": 0, "cost": 0, "trips": set()})
		bucket["revenue"] += r["revenue"] or 0
		bucket["cost"] += cust_cost
		bucket["trips"].add(trip)

	rows = []
	for customer, v in agg.items():
		profit = v["revenue"] - v["cost"]
		rows.append(
			{
				"customer": customer,
				"customer_name": frappe.db.get_value("Customer", customer, "customer_name"),
				"trips": len(v["trips"]),
				"revenue": v["revenue"],
				"cost": v["cost"],
				"profit": profit,
				"margin_percent": (profit / v["revenue"] * 100) if v["revenue"] else 0,
			}
		)
	rows.sort(key=lambda r: r["profit"], reverse=True)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
		{"label": _("Trips"), "fieldname": "trips", "fieldtype": "Int", "width": 70},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 140},
		{"label": _("Cost (apportioned)"), "fieldname": "cost", "fieldtype": "Currency", "width": 150},
		{"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 140},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 90},
	]
