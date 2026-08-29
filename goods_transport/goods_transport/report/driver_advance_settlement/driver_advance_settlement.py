"""One row per Trip Advance showing paid vs consumed via Trip Expenses,
plus any Trip Settlement cash-returned figure."""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND adv.docstatus = 1"
	values = {}
	if filters.get("company"):
		conditions += " AND adv.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("recipient_type"):
		conditions += " AND adv.recipient_type = %(recipient_type)s"
		values["recipient_type"] = filters["recipient_type"]
	if filters.get("driver"):
		conditions += " AND adv.driver = %(driver)s"
		values["driver"] = filters["driver"]
	if filters.get("outstanding_only"):
		# leave placeholder — filter in Python since it depends on aggregate
		pass

	rows = frappe.db.sql(
		f"""
		SELECT
			adv.name AS advance, adv.advance_date, adv.trip,
			adv.recipient_type, adv.driver, adv.employee, adv.supplier, adv.receiver_name,
			adv.amount AS paid,
			COALESCE((
				SELECT SUM(te.amount) FROM `tabTrip Expense` te
				WHERE te.trip_advance = adv.name AND te.docstatus = 1
			), 0) AS consumed,
			COALESCE(ts.cash_returned, 0) AS cash_returned,
			ts.name AS settlement
		FROM `tabTrip Advance` adv
		LEFT JOIN `tabTrip Settlement` ts ON ts.trip = adv.trip AND ts.docstatus = 1
		WHERE 1=1 {conditions}
		ORDER BY adv.advance_date DESC, adv.name DESC
		""",
		values, as_dict=1,
	)
	out = []
	for r in rows:
		r["balance"] = (r["paid"] or 0) - (r["consumed"] or 0)
		r["outstanding"] = max(r["balance"] - (r["cash_returned"] or 0), 0)
		if filters.get("outstanding_only") and r["outstanding"] <= 0:
			continue
		out.append(r)
	return _columns(), out


def _columns():
	return [
		{"label": _("Advance"), "fieldname": "advance", "fieldtype": "Link", "options": "Trip Advance", "width": 140},
		{"label": _("Date"), "fieldname": "advance_date", "fieldtype": "Date", "width": 100},
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 140},
		{"label": _("Type"), "fieldname": "recipient_type", "fieldtype": "Data", "width": 90},
		{"label": _("Receiver"), "fieldname": "receiver_name", "fieldtype": "Data", "width": 160},
		{"label": _("Paid"), "fieldname": "paid", "fieldtype": "Currency", "width": 120},
		{"label": _("Consumed"), "fieldname": "consumed", "fieldtype": "Currency", "width": 120},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
		{"label": _("Cash Returned"), "fieldname": "cash_returned", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
		{"label": _("Settlement"), "fieldname": "settlement", "fieldtype": "Link", "options": "Trip Settlement", "width": 140},
	]
