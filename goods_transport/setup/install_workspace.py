"""Idempotent installer for the Goods Transport workspace.

Runs from after_install and a post-model-sync patch, so both fresh installs
and upgrades converge to the same shipped workspace. Users can still edit
the workspace after install; re-running the installer overwrites the
shipped layout (safe: it targets a fixed, well-known name).
"""

import json

import frappe


WORKSPACE_NAME = "Goods Transport"

LINKS = [
	{"type": "Card Break", "label": "Operations"},
	{"type": "Link", "label": "Transport Order", "link_type": "DocType", "link_to": "Transport Order"},
	{"type": "Link", "label": "Transport Trip", "link_type": "DocType", "link_to": "Transport Trip"},
	{"type": "Link", "label": "Bilty", "link_type": "DocType", "link_to": "Bilty"},
	{"type": "Link", "label": "Proof of Delivery", "link_type": "DocType", "link_to": "Proof of Delivery"},
	{"type": "Card Break", "label": "Trip Finance"},
	{"type": "Link", "label": "Trip Advance", "link_type": "DocType", "link_to": "Trip Advance"},
	{"type": "Link", "label": "Trip Expense", "link_type": "DocType", "link_to": "Trip Expense"},
	{"type": "Link", "label": "Trip Settlement", "link_type": "DocType", "link_to": "Trip Settlement"},
	{"type": "Link", "label": "Trip Expense Type", "link_type": "DocType", "link_to": "Trip Expense Type"},
	{"type": "Card Break", "label": "Masters"},
	{"type": "Link", "label": "Vehicle", "link_type": "DocType", "link_to": "Vehicle"},
	{"type": "Link", "label": "Driver", "link_type": "DocType", "link_to": "Driver"},
	{"type": "Link", "label": "Vehicle Type", "link_type": "DocType", "link_to": "Vehicle Type"},
	{"type": "Link", "label": "Transport Location", "link_type": "DocType", "link_to": "Transport Location"},
	{"type": "Link", "label": "Transport Route", "link_type": "DocType", "link_to": "Transport Route"},
	{"type": "Card Break", "label": "Commercial"},
	{"type": "Link", "label": "Transport Rate Contract", "link_type": "DocType", "link_to": "Transport Rate Contract"},
	{"type": "Link", "label": "Customer", "link_type": "DocType", "link_to": "Customer"},
	{"type": "Link", "label": "Supplier (Transporters)", "link_type": "DocType", "link_to": "Supplier"},
	{"type": "Link", "label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice"},
	{"type": "Card Break", "label": "Reports"},
	{"type": "Link", "label": "Bilty Register", "link_type": "Report", "link_to": "Bilty Register", "is_query_report": 1},
	{"type": "Link", "label": "Unbilled Bilties", "link_type": "Report", "link_to": "Unbilled Bilties", "is_query_report": 1},
	{"type": "Link", "label": "Active Trips", "link_type": "Report", "link_to": "Active Trips", "is_query_report": 1},
	{"type": "Link", "label": "Transport Order Status", "link_type": "Report", "link_to": "Transport Order Status", "is_query_report": 1},
	{"type": "Link", "label": "Pending POD", "link_type": "Report", "link_to": "Pending POD", "is_query_report": 1},
	{"type": "Link", "label": "Vehicle Trip History", "link_type": "Report", "link_to": "Vehicle Trip History", "is_query_report": 1},
	{"type": "Link", "label": "Trip Profitability", "link_type": "Report", "link_to": "Trip Profitability", "is_query_report": 1},
	{"type": "Link", "label": "Customer Profitability", "link_type": "Report", "link_to": "Customer Profitability", "is_query_report": 1},
	{"type": "Link", "label": "Route Profitability", "link_type": "Report", "link_to": "Route Profitability", "is_query_report": 1},
	{"type": "Link", "label": "Transporter Performance", "link_type": "Report", "link_to": "Transporter Performance", "is_query_report": 1},
	{"type": "Link", "label": "Trip Expense Analysis", "link_type": "Report", "link_to": "Trip Expense Analysis", "is_query_report": 1},
	{"type": "Link", "label": "Driver Advance Settlement", "link_type": "Report", "link_to": "Driver Advance Settlement", "is_query_report": 1},
]

SHORTCUTS = [
	{"label": "New Bilty", "type": "DocType", "link_to": "Bilty", "color": "Blue"},
	{"label": "New Transport Order", "type": "DocType", "link_to": "Transport Order", "color": "Green"},
	{"label": "New Transport Trip", "type": "DocType", "link_to": "Transport Trip", "color": "Yellow"},
	{"label": "Bilty Register", "type": "Report", "link_to": "Bilty Register", "color": "Grey"},
	{"label": "Unbilled Bilties", "type": "Report", "link_to": "Unbilled Bilties", "color": "Grey"},
]

CONTENT = [
	{"id": "hdr-1", "type": "header", "data": {"text": "<span class='h4'><b>Goods Transport</b></span>", "col": 12}},
	{"id": "nc-1", "type": "number_card", "data": {"number_card_name": "GT — Active Trips", "col": 3}},
	{"id": "nc-2", "type": "number_card", "data": {"number_card_name": "GT — Pending POD", "col": 3}},
	{"id": "nc-3", "type": "number_card", "data": {"number_card_name": "GT — Unbilled Bilties", "col": 3}},
	{"id": "nc-4", "type": "number_card", "data": {"number_card_name": "GT — Unsettled Trips", "col": 3}},
	{"id": "nc-5", "type": "number_card", "data": {"number_card_name": "GT — MTD Trip Revenue", "col": 6}},
	{"id": "spc-nc", "type": "spacer", "data": {"col": 6}},
	{"id": "chart-1", "type": "chart", "data": {"chart_name": "GT — Trip Revenue by Month", "col": 12}},
	{"id": "spc-0", "type": "spacer", "data": {"col": 12}},
	{"id": "hdr-2", "type": "header", "data": {"text": "<span class='h5'><b>Quick Create</b></span>", "col": 12}},
	{"id": "sc-1", "type": "shortcut", "data": {"shortcut_name": "New Bilty", "col": 3}},
	{"id": "sc-2", "type": "shortcut", "data": {"shortcut_name": "New Transport Order", "col": 3}},
	{"id": "sc-3", "type": "shortcut", "data": {"shortcut_name": "New Transport Trip", "col": 3}},
	{"id": "sc-4", "type": "shortcut", "data": {"shortcut_name": "Bilty Register", "col": 3}},
	{"id": "spc-1", "type": "spacer", "data": {"col": 12}},
	{"id": "hdr-3", "type": "header", "data": {"text": "<span class='h5'><b>Modules</b></span>", "col": 12}},
	{"id": "cd-ops", "type": "card", "data": {"card_name": "Operations", "col": 4}},
	{"id": "cd-fin", "type": "card", "data": {"card_name": "Trip Finance", "col": 4}},
	{"id": "cd-mst", "type": "card", "data": {"card_name": "Masters", "col": 4}},
	{"id": "cd-com", "type": "card", "data": {"card_name": "Commercial", "col": 4}},
	{"id": "cd-rep", "type": "card", "data": {"card_name": "Reports", "col": 8}},
]


def install_goods_transport_workspace():
	if not frappe.db.exists("Module Def", "Goods Transport"):
		return

	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		ws = frappe.get_doc("Workspace", WORKSPACE_NAME)
	else:
		ws = frappe.new_doc("Workspace")
		ws.name = WORKSPACE_NAME

	ws.title = WORKSPACE_NAME
	ws.label = WORKSPACE_NAME
	ws.module = "Goods Transport"
	ws.public = 1
	ws.is_hidden = 0
	ws.icon = "truck"
	ws.indicator_color = "blue"
	ws.sequence_id = 15.0
	ws.content = json.dumps(CONTENT)

	ws.set("links", [])
	for item in LINKS:
		ws.append("links", {**item, "hidden": 0, "onboard": 0})

	ws.set("shortcuts", [])
	for item in SHORTCUTS:
		ws.append("shortcuts", {**item})

	ws.save(ignore_permissions=True)
	frappe.db.commit()
