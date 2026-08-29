import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND o.docstatus = 1"
	values = {}
	if filters.get("company"):
		conditions += " AND o.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("customer"):
		conditions += " AND o.customer = %(customer)s"
		values["customer"] = filters["customer"]
	if filters.get("status"):
		conditions += " AND o.status = %(status)s"
		values["status"] = filters["status"]
	if filters.get("open_only"):
		conditions += " AND o.status NOT IN ('Delivered', 'Closed', 'Cancelled')"

	rows = frappe.db.sql(
		f"""
		SELECT
			o.name AS order_name, o.booking_date, o.customer, o.customer_name,
			o.origin, o.destination, o.commodity, o.uom,
			o.quantity AS ordered_qty,
			o.dispatched_quantity AS dispatched_qty,
			o.delivered_quantity AS delivered_qty,
			o.remaining_quantity AS remaining_qty,
			o.grand_total AS est_total,
			o.billed_amount AS billed,
			o.currency, o.status
		FROM `tabTransport Order` o
		WHERE 1=1 {conditions}
		ORDER BY o.booking_date DESC, o.name DESC
		""",
		values, as_dict=1,
	)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Order"), "fieldname": "order_name", "fieldtype": "Link", "options": "Transport Order", "width": 150},
		{"label": _("Booked"), "fieldname": "booking_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 130},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Commodity"), "fieldname": "commodity", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Ordered"), "fieldname": "ordered_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Dispatched"), "fieldname": "dispatched_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Delivered"), "fieldname": "delivered_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Remaining"), "fieldname": "remaining_qty", "fieldtype": "Float", "width": 100},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Estimated"), "fieldname": "est_total", "fieldtype": "Currency", "options": "currency", "width": 130},
		{"label": _("Billed"), "fieldname": "billed", "fieldtype": "Currency", "options": "currency", "width": 130},
	]
