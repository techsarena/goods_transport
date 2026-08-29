import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions, values = _build_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			b.name              AS bilty,
			b.bilty_date        AS bilty_date,
			b.status            AS status,
			b.customer          AS customer,
			b.customer_name     AS customer_name,
			b.origin            AS origin,
			b.destination       AS destination,
			b.vehicle           AS vehicle,
			b.vehicle_license_plate AS license_plate,
			b.driver            AS driver,
			b.transporter       AS transporter,
			b.total_gross_weight AS gross_weight,
			b.total_packages    AS packages,
			b.freight_amount    AS freight,
			b.additional_charges_total AS additional,
			b.grand_total       AS grand_total,
			b.currency          AS currency,
			b.pod_status        AS pod_status,
			b.sales_invoice     AS sales_invoice
		FROM `tabBilty` b
		WHERE b.docstatus < 2 {conditions}
		ORDER BY b.bilty_date DESC, b.name DESC
		""",
		values,
		as_dict=1,
	)
	return _columns(), rows


def _build_conditions(filters):
	conditions = ""
	values = {}
	if filters.get("company"):
		conditions += " AND b.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions += " AND b.bilty_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions += " AND b.bilty_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]
	if filters.get("customer"):
		conditions += " AND b.customer = %(customer)s"
		values["customer"] = filters["customer"]
	if filters.get("vehicle"):
		conditions += " AND b.vehicle = %(vehicle)s"
		values["vehicle"] = filters["vehicle"]
	if filters.get("transporter"):
		conditions += " AND b.transporter = %(transporter)s"
		values["transporter"] = filters["transporter"]
	if filters.get("status"):
		conditions += " AND b.status = %(status)s"
		values["status"] = filters["status"]
	return conditions, values


def _columns():
	return [
		{"label": _("Bilty"), "fieldname": "bilty", "fieldtype": "Link", "options": "Bilty", "width": 140},
		{"label": _("Date"), "fieldname": "bilty_date", "fieldtype": "Date", "width": 95},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 110},
		{"label": _("Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 90},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 110},
		{"label": _("Transporter"), "fieldname": "transporter", "fieldtype": "Link", "options": "Supplier", "width": 130},
		{"label": _("Gross Wt"), "fieldname": "gross_weight", "fieldtype": "Float", "width": 90},
		{"label": _("Pkgs"), "fieldname": "packages", "fieldtype": "Int", "width": 70},
		{"label": _("Freight"), "fieldname": "freight", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Additional"), "fieldname": "additional", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("POD"), "fieldname": "pod_status", "fieldtype": "Data", "width": 90},
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 140},
	]
