import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND b.docstatus = 1 AND b.pod_required = 1 AND b.pod_status = 'Pending'"
	values = {}
	if filters.get("company"):
		conditions += " AND b.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("customer"):
		conditions += " AND b.customer = %(customer)s"
		values["customer"] = filters["customer"]
	if filters.get("days_since"):
		conditions += " AND DATEDIFF(CURDATE(), b.bilty_date) >= %(days_since)s"
		values["days_since"] = filters["days_since"]

	rows = frappe.db.sql(
		f"""
		SELECT
			b.name AS bilty, b.bilty_date, b.status,
			b.customer, b.customer_name, b.consignee,
			b.origin, b.destination,
			b.vehicle_license_plate AS plate, b.driver_name AS driver,
			b.transport_trip AS trip,
			b.total_quantity, b.grand_total, b.currency,
			DATEDIFF(CURDATE(), b.bilty_date) AS days_open
		FROM `tabBilty` b
		WHERE 1=1 {conditions}
		ORDER BY days_open DESC, b.bilty_date ASC
		""",
		values, as_dict=1,
	)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Bilty"), "fieldname": "bilty", "fieldtype": "Link", "options": "Bilty", "width": 140},
		{"label": _("Date"), "fieldname": "bilty_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Open"), "fieldname": "days_open", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": _("Consignee"), "fieldname": "consignee", "fieldtype": "Data", "width": 160},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Vehicle"), "fieldname": "plate", "fieldtype": "Data", "width": 90},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Data", "width": 130},
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 140},
		{"label": _("Quantity"), "fieldname": "total_quantity", "fieldtype": "Float", "width": 90},
		{"label": _("Amount"), "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 130},
	]
