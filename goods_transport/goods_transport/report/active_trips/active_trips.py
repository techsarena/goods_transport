import frappe
from frappe import _


ACTIVE_STATUSES = (
	"Planned", "Vehicle Assigned", "At Loading Point", "Loaded",
	"In Transit", "Arrived", "Unloading",
)


def execute(filters=None):
	filters = filters or {}
	conditions = " AND t.docstatus = 1 AND t.status IN %(statuses)s"
	values = {"statuses": tuple(filters.get("statuses") or ACTIVE_STATUSES)}
	if filters.get("company"):
		conditions += " AND t.company = %(company)s"
		values["company"] = filters["company"]
	if filters.get("transporter"):
		conditions += " AND t.transporter = %(transporter)s"
		values["transporter"] = filters["transporter"]

	rows = frappe.db.sql(
		f"""
		SELECT
			t.name AS trip, t.trip_date, t.status,
			t.vehicle, t.vehicle_license_plate AS plate, t.driver_name AS driver, t.transporter,
			t.origin, t.destination,
			t.loaded_weight, t.vehicle_capacity, t.capacity_utilization,
			t.bilty_count, t.departure_time, t.arrival_time
		FROM `tabTransport Trip` t
		WHERE 1=1 {conditions}
		ORDER BY t.trip_date DESC, t.name DESC
		""",
		values, as_dict=1,
	)
	return _columns(), rows


def _columns():
	return [
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Transport Trip", "width": 150},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 110},
		{"label": _("Plate"), "fieldname": "plate", "fieldtype": "Data", "width": 90},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Data", "width": 130},
		{"label": _("Transporter"), "fieldname": "transporter", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Origin"), "fieldname": "origin", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Destination"), "fieldname": "destination", "fieldtype": "Link", "options": "Transport Location", "width": 120},
		{"label": _("Loaded (kg)"), "fieldname": "loaded_weight", "fieldtype": "Float", "width": 100},
		{"label": _("Capacity"), "fieldname": "vehicle_capacity", "fieldtype": "Float", "width": 100},
		{"label": _("Util %"), "fieldname": "capacity_utilization", "fieldtype": "Percent", "width": 80},
		{"label": _("Bilties"), "fieldname": "bilty_count", "fieldtype": "Int", "width": 70},
		{"label": _("Departure"), "fieldname": "departure_time", "fieldtype": "Datetime", "width": 140},
		{"label": _("Arrival"), "fieldname": "arrival_time", "fieldtype": "Datetime", "width": 140},
	]
