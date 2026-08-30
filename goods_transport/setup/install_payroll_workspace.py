"""Idempotent installer for the Driver Payroll workspace."""

import json

import frappe

WORKSPACE_NAME = "Driver Payroll"

LINKS = [
	{"type": "Card Break", "label": "Driver Payroll"},
	{"type": "Link", "label": "Driver Payroll Run", "link_type": "DocType", "link_to": "Driver Payroll Run"},
	{"type": "Link", "label": "Driver Trip Earning", "link_type": "DocType", "link_to": "Driver Trip Earning"},
	{"type": "Link", "label": "Driver Pay Rule", "link_type": "DocType", "link_to": "Driver Pay Rule"},
	{"type": "Card Break", "label": "Salary Processing"},
	{"type": "Link", "label": "Payroll Entry", "link_type": "DocType", "link_to": "Payroll Entry"},
	{"type": "Link", "label": "Salary Slip", "link_type": "DocType", "link_to": "Salary Slip"},
	{"type": "Link", "label": "Additional Salary", "link_type": "DocType", "link_to": "Additional Salary"},
	{"type": "Link", "label": "Salary Structure", "link_type": "DocType", "link_to": "Salary Structure"},
	{"type": "Link", "label": "Salary Structure Assignment", "link_type": "DocType", "link_to": "Salary Structure Assignment"},
	{"type": "Link", "label": "Salary Component", "link_type": "DocType", "link_to": "Salary Component"},
	{"type": "Card Break", "label": "People"},
	{"type": "Link", "label": "Employee", "link_type": "DocType", "link_to": "Employee"},
	{"type": "Link", "label": "Driver", "link_type": "DocType", "link_to": "Driver"},
	{"type": "Link", "label": "Attendance", "link_type": "DocType", "link_to": "Attendance"},
	{"type": "Link", "label": "Leave Application", "link_type": "DocType", "link_to": "Leave Application"},
	{"type": "Card Break", "label": "Reports"},
	{"type": "Link", "label": "Driver Earnings Register", "link_type": "Report", "link_to": "Driver Earnings Register", "is_query_report": 1},
	{"type": "Link", "label": "Driver Advance Recovery Status", "link_type": "Report", "link_to": "Driver Advance Recovery Status", "is_query_report": 1},
	{"type": "Link", "label": "Driver Cost Per Trip", "link_type": "Report", "link_to": "Driver Cost Per Trip", "is_query_report": 1},
	{"type": "Link", "label": "Salary Register", "link_type": "Report", "link_to": "Salary Register", "is_query_report": 1},
]

SHORTCUTS = [
	{"label": "New Driver Payroll Run", "type": "DocType", "link_to": "Driver Payroll Run", "color": "Blue"},
	{"label": "Driver Trip Earning", "type": "DocType", "link_to": "Driver Trip Earning", "color": "Green"},
	{"label": "Payroll Entry", "type": "DocType", "link_to": "Payroll Entry", "color": "Yellow"},
	{"label": "Driver Earnings Register", "type": "Report", "link_to": "Driver Earnings Register", "color": "Grey"},
]

CONTENT = [
	{"id": "tp-hdr", "type": "header", "data": {"text": "<span class='h4'><b>Driver Payroll</b></span>", "col": 12}},
	{"id": "tp-para", "type": "paragraph", "data": {"text": "Trip earnings flow into standard HRMS payroll: <b>Trip → Driver Trip Earning → Driver Payroll Run → Additional Salary → Salary Slip</b>.", "col": 12}},
	{"id": "tp-sc1", "type": "shortcut", "data": {"shortcut_name": "New Driver Payroll Run", "col": 3}},
	{"id": "tp-sc2", "type": "shortcut", "data": {"shortcut_name": "Driver Trip Earning", "col": 3}},
	{"id": "tp-sc3", "type": "shortcut", "data": {"shortcut_name": "Payroll Entry", "col": 3}},
	{"id": "tp-sc4", "type": "shortcut", "data": {"shortcut_name": "Driver Earnings Register", "col": 3}},
	{"id": "tp-spc", "type": "spacer", "data": {"col": 12}},
	{"id": "tp-cd1", "type": "card", "data": {"card_name": "Driver Payroll", "col": 4}},
	{"id": "tp-cd2", "type": "card", "data": {"card_name": "Salary Processing", "col": 4}},
	{"id": "tp-cd3", "type": "card", "data": {"card_name": "People", "col": 4}},
	{"id": "tp-cd4", "type": "card", "data": {"card_name": "Reports", "col": 4}},
]


def install_payroll_workspace():
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
	ws.icon = "users"
	ws.indicator_color = "green"
	ws.sequence_id = 16.0
	ws.content = json.dumps(CONTENT)

	ws.set("links", [])
	for item in LINKS:
		ws.append("links", {**item, "hidden": 0, "onboard": 0})

	ws.set("shortcuts", [])
	for item in SHORTCUTS:
		ws.append("shortcuts", {**item})

	ws.save(ignore_permissions=True)
	frappe.db.commit()
