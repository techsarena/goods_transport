import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	conditions = " AND t.docstatus = 1 AND t.transporter IS NOT NULL AND t.transporter != ''"
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
			t.transporter,
			COUNT(*) AS trip_count,
			SUM(t.agreed_vehicle_hire) AS total_hire,
			AVG(t.agreed_vehicle_hire) AS avg_hire,
			SUM(t.loaded_weight) AS total_weight,
			SUM(CASE WHEN t.status = 'Delivered' OR t.status = 'Settled' OR t.status = 'Closed' THEN 1 ELSE 0 END) AS delivered_count,
			SUM(CASE WHEN t.completion_time IS NOT NULL THEN 1 ELSE 0 END) AS completed_with_time
		FROM `tabTransport Trip` t
		WHERE 1=1 {conditions}
		GROUP BY t.transporter
		ORDER BY total_hire DESC
		""",
		values, as_dict=1,
	)

	# Add exceptions count (bilties with short_quantity or damaged_quantity > 0)
	transporters = tuple(r["transporter"] for r in rows) if rows else None
	exceptions_by_transporter = {}
	if transporters:
		exc_rows = frappe.db.sql(
			"""
			SELECT t.transporter, COUNT(*) AS n
			FROM `tabProof of Delivery` pod
			INNER JOIN `tabBilty` b ON b.name = pod.bilty
			INNER JOIN `tabTransport Trip` t ON t.name = b.transport_trip
			WHERE pod.docstatus = 1
			  AND (pod.short_quantity > 0 OR pod.damaged_quantity > 0)
			  AND t.transporter IN %(ts)s
			GROUP BY t.transporter
			""",
			{"ts": transporters}, as_dict=1,
		)
		exceptions_by_transporter = {r["transporter"]: r["n"] for r in exc_rows}

	for r in rows:
		r["delivery_percent"] = (r["delivered_count"] / r["trip_count"] * 100) if r["trip_count"] else 0
		r["exceptions"] = exceptions_by_transporter.get(r["transporter"], 0)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Transporter"), "fieldname": "transporter", "fieldtype": "Link", "options": "Supplier", "width": 200},
		{"label": _("Trips"), "fieldname": "trip_count", "fieldtype": "Int", "width": 70},
		{"label": _("Delivered %"), "fieldname": "delivery_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Exceptions"), "fieldname": "exceptions", "fieldtype": "Int", "width": 90},
		{"label": _("Total Hire"), "fieldname": "total_hire", "fieldtype": "Currency", "width": 130},
		{"label": _("Avg Hire"), "fieldname": "avg_hire", "fieldtype": "Currency", "width": 130},
		{"label": _("Total Weight (kg)"), "fieldname": "total_weight", "fieldtype": "Float", "width": 130},
	]
