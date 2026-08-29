import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	group_by = filters.get("group_by") or "Expense Type"
	group_col = {
		"Expense Type": "COALESCE(te.expense_type, '(untyped)')",
		"Payment Mode": "te.payment_mode",
		"Trip": "te.trip",
		"Vehicle": "COALESCE(t.vehicle_license_plate, t.vehicle, '(no vehicle)')",
		"Driver": "COALESCE(te.driver, t.driver, '(no driver)')",
	}.get(group_by, "COALESCE(te.expense_type, '(untyped)')")

	conditions = " AND te.docstatus = 1"
	values = {}
	if filters.get("company"):
		conditions += " AND te.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions += " AND te.expense_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND te.expense_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]
	if filters.get("trip"):
		conditions += " AND te.trip = %(trip)s"
		values["trip"] = filters["trip"]

	rows = frappe.db.sql(
		f"""
		SELECT
			{group_col} AS bucket,
			COUNT(*) AS entries,
			SUM(te.amount) AS total_amount,
			MIN(te.amount) AS min_amount,
			MAX(te.amount) AS max_amount,
			AVG(te.amount) AS avg_amount,
			SUM(CASE WHEN te.billable_to_customer = 1 THEN te.recoverable_amount ELSE 0 END) AS recoverable
		FROM `tabTrip Expense` te
		LEFT JOIN `tabTransport Trip` t ON t.name = te.trip
		WHERE 1=1 {conditions}
		GROUP BY bucket
		ORDER BY total_amount DESC
		""",
		values, as_dict=1,
	)
	return _columns(group_by), rows


def _columns(group_by):
	return [
		{"label": _(group_by), "fieldname": "bucket", "fieldtype": "Data", "width": 220},
		{"label": _("Entries"), "fieldname": "entries", "fieldtype": "Int", "width": 80},
		{"label": _("Total"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Avg"), "fieldname": "avg_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Min"), "fieldname": "min_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Max"), "fieldname": "max_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Recoverable"), "fieldname": "recoverable", "fieldtype": "Currency", "width": 130},
	]
