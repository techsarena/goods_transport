"""Idempotent installer for goods_transport custom fields on standard DocTypes.

Called from install.py (after_install) and from patches/v1_0/install_transport_custom_fields.py
so both fresh installs and existing sites converge to the same schema on `bench migrate`.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_transport_custom_fields():
	custom_fields = {
		"Vehicle": [
			{
				"fieldname": "transport_section",
				"label": "Transport Details",
				"fieldtype": "Section Break",
				"insert_after": "amended_from",
				"collapsible": 0,
			},
			{
				"fieldname": "ownership_type",
				"label": "Ownership Type",
				"fieldtype": "Select",
				"options": "\nCompany Owned\nContracted\nAttached\nMarket Vehicle",
				"insert_after": "transport_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "vehicle_type",
				"label": "Vehicle Type",
				"fieldtype": "Link",
				"options": "Vehicle Type",
				"insert_after": "ownership_type",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "current_status",
				"label": "Current Status",
				"fieldtype": "Select",
				"options": "Available\nIn Trip\nUnder Maintenance\nIdle\nOut of Service",
				"default": "Available",
				"insert_after": "vehicle_type",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "transport_col_break",
				"fieldtype": "Column Break",
				"insert_after": "current_status",
			},
			{
				"fieldname": "transporter",
				"label": "Transporter",
				"fieldtype": "Link",
				"options": "Supplier",
				"insert_after": "transport_col_break",
				"description": "Party responsible for the vehicle in operations (for hire vehicles).",
			},
			{
				"fieldname": "vehicle_owner",
				"label": "Vehicle Owner",
				"fieldtype": "Link",
				"options": "Supplier",
				"insert_after": "transporter",
				"description": "Legal / financial owner of the vehicle. May differ from Transporter.",
			},
			{
				"fieldname": "default_driver",
				"label": "Default Driver",
				"fieldtype": "Link",
				"options": "Driver",
				"insert_after": "vehicle_owner",
			},
			{
				"fieldname": "capacity_section",
				"label": "Capacity",
				"fieldtype": "Section Break",
				"insert_after": "default_driver",
				"collapsible": 1,
			},
			{
				"fieldname": "payload_capacity",
				"label": "Payload Capacity (kg)",
				"fieldtype": "Float",
				"insert_after": "capacity_section",
				"non_negative": 1,
			},
			{
				"fieldname": "capacity_col_break",
				"fieldtype": "Column Break",
				"insert_after": "payload_capacity",
			},
			{
				"fieldname": "volume_capacity",
				"label": "Volume Capacity (m³)",
				"fieldtype": "Float",
				"insert_after": "capacity_col_break",
				"non_negative": 1,
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "transport_section",
				"label": "Transport",
				"fieldtype": "Section Break",
				"insert_after": "remarks",
				"collapsible": 1,
			},
			{
				"fieldname": "bilty_references",
				"label": "Bilty References",
				"fieldtype": "Table",
				"options": "Bilty Reference",
				"insert_after": "transport_section",
				"read_only": 1,
				"no_copy": 1,
				"description": "Bilties consolidated into this invoice. Populated by the Create Sales Invoice action on Bilty.",
			},
		],
	}
	create_custom_fields(custom_fields, update=True)
