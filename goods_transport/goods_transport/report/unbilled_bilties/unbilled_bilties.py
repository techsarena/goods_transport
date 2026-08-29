import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND b.docstatus = 1 AND (b.sales_invoice IS NULL OR b.sales_invoice = '')"
	values = {}
	if filters.get("company"):
		conditions += " AND b.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("billing_customer"):
		conditions += " AND b.billing_customer = %(billing_customer)s"
		values["billing_customer"] = filters["billing_customer"]
	if filters.get("to_date"):
		conditions += " AND b.bilty_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(
		f"""
		SELECT
			b.name              AS bilty,
			b.bilty_date        AS bilty_date,
			b.billing_customer  AS billing_customer,
			b.customer_name     AS customer_name,
			b.origin            AS origin,
			b.destination       AS destination,
			b.pod_status        AS pod_status,
			b.freight_amount    AS freight,
			b.additional_charges_total AS additional,
			b.grand_total       AS amount,
			b.currency          AS currency
		FROM `tabBilty` b
		WHERE 1=1 {conditions}
		ORDER BY b.billing_customer, b.bilty_date, b.name
		""",
		values,
		as_dict=1,
	)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Bilty"), "fieldname": "bilty", "fieldtype": "Link", "options": "Bilty", "width": 140},
		{"label": _("Date"), "fieldname": "bilty_date", "fieldtype": "Date", "width": 100},
		{"label": _("Billing Customer"), "fieldname": "billing_customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 130},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 130},
		{"label": _("POD"), "fieldname": "pod_status", "fieldtype": "Data", "width": 100},
		{"label": _("Freight"), "fieldname": "freight", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Additional"), "fieldname": "additional", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 130},
	]
