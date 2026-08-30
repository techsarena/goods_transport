"""Custom fields that join payroll figures onto goods_transport documents.

`Trip Settlement.total_cost` is deliberately left alone: goods_transport
defines it as vehicle hire + trip expenses, which is exactly what the GL
holds against the Trip accounting dimension, so the settlement keeps
reconciling with the Trip Profitability report.

Driver trip pay is a payroll cost — it reaches the GL through a monthly
Salary Slip that covers many trips and carries no Trip dimension. It is
therefore shown alongside as a fully-loaded view, never folded into
total_cost.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Trip Settlement": [
		{
			"fieldname": "driver_pay_section",
			"label": "Driver Pay (Payroll)",
			"fieldtype": "Section Break",
			"insert_after": "margin_percent",
			"collapsible": 0,
		},
		{
			"fieldname": "driver_trip_pay",
			"label": "Driver Trip Pay",
			"fieldtype": "Currency",
			"options": "currency",
			"read_only": 1,
			"insert_after": "driver_pay_section",
			"description": "Trip-based driver earning for this Trip. Paid through the "
			"monthly Salary Slip, so it is NOT part of Total Cost above (which "
			"matches the Trip's GL entries).",
		},
		{
			"fieldname": "driver_pay_col_break",
			"fieldtype": "Column Break",
			"insert_after": "driver_trip_pay",
		},
		{
			"fieldname": "profit_after_driver_pay",
			"label": "Profit After Driver Pay",
			"fieldtype": "Currency",
			"options": "currency",
			"read_only": 1,
			"bold": 1,
			"insert_after": "driver_pay_col_break",
			"description": "Gross Profit less the driver's trip pay — the fully loaded "
			"trip margin.",
		},
	],
	"Transport Trip": [
		{
			"fieldname": "driver_trip_pay",
			"label": "Driver Trip Pay",
			"fieldtype": "Currency",
			"options": "currency",
			"read_only": 1,
			"insert_after": "driver_allowance",
			"allow_on_submit": 1,
			"description": "Computed from the Driver Pay Rule once the Trip is delivered.",
		},
	],
}


def install_payroll_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)
	frappe.clear_cache()
