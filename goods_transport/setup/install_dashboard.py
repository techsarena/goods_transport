"""Idempotent installer for Goods Transport dashboard widgets:
- 5 Number Cards (KPIs)
- 1 Dashboard Chart (Trip Revenue by month)

Called from after_install and a post-model-sync patch."""

import json

import frappe


NUMBER_CARDS = [
	{
		"name": "GT — Active Trips",
		"label": "Active Trips",
		"document_type": "Transport Trip",
		"function": "Count",
		"filters_json": json.dumps(
			[
				["Transport Trip", "docstatus", "=", 1],
				[
					"Transport Trip",
					"status",
					"in",
					["Planned", "Vehicle Assigned", "At Loading Point", "Loaded", "In Transit", "Arrived", "Unloading"],
				],
			]
		),
		"color": "#2490EF",
	},
	{
		"name": "GT — Pending POD",
		"label": "Pending POD",
		"document_type": "Bilty",
		"function": "Count",
		"filters_json": json.dumps(
			[
				["Bilty", "docstatus", "=", 1],
				["Bilty", "pod_required", "=", 1],
				["Bilty", "pod_status", "=", "Pending"],
			]
		),
		"color": "#F8814F",
	},
	{
		"name": "GT — Unbilled Bilties",
		"label": "Unbilled Bilties",
		"document_type": "Bilty",
		"function": "Count",
		"filters_json": json.dumps(
			[
				["Bilty", "docstatus", "=", 1],
				["Bilty", "sales_invoice", "is", "not set"],
			]
		),
		"color": "#7574F1",
	},
	{
		"name": "GT — Unsettled Trips",
		"label": "Unsettled Trips",
		"document_type": "Transport Trip",
		"function": "Count",
		"filters_json": json.dumps(
			[
				["Transport Trip", "docstatus", "=", 1],
				["Transport Trip", "status", "=", "Delivered"],
				["Transport Trip", "trip_settlement", "is", "not set"],
			]
		),
		"color": "#FFC107",
	},
	{
		"name": "GT — MTD Trip Revenue",
		"label": "MTD Trip Revenue",
		"document_type": "Sales Invoice",
		"function": "Sum",
		"aggregate_function_based_on": "base_grand_total",
		"filters_json": json.dumps(
			[
				["Sales Invoice", "docstatus", "=", 1],
				["Sales Invoice", "transport_trip", "is", "set"],
				["Sales Invoice", "posting_date", "Timespan", "this month"],
			]
		),
		"color": "#29CD42",
	},
]


CHART = {
	"name": "GT — Trip Revenue by Month",
	"chart_name": "GT — Trip Revenue by Month",
	"chart_type": "Sum",
	"document_type": "Sales Invoice",
	"based_on": "posting_date",
	"value_based_on": "base_grand_total",
	"timeseries": 1,
	"time_interval": "Monthly",
	"timespan": "Last Year",
	"type": "Bar",
	"filters_json": json.dumps(
		[
			["Sales Invoice", "docstatus", "=", 1],
			["Sales Invoice", "transport_trip", "is", "set"],
		]
	),
	"color": "#2490EF",
	"is_public": 1,
	"module": "Goods Transport",
}


def install_transport_dashboard():
	if not frappe.db.exists("DocType", "Number Card"):
		return
	for spec in NUMBER_CARDS:
		payload = {
			"label": spec["label"],
			"document_type": spec["document_type"],
			"function": spec["function"],
			"aggregate_function_based_on": spec.get("aggregate_function_based_on"),
			"filters_json": spec["filters_json"],
			"color": spec.get("color"),
			"is_public": 1,
			"module": "Goods Transport",
			"type": "Document Type",
		}
		if frappe.db.exists("Number Card", spec["name"]):
			frappe.db.set_value("Number Card", spec["name"], payload)
		else:
			doc = frappe.new_doc("Number Card")
			doc.name = spec["name"]
			doc.update(payload)
			doc.insert(ignore_permissions=True)

	if frappe.db.exists("DocType", "Dashboard Chart"):
		if frappe.db.exists("Dashboard Chart", CHART["name"]):
			payload = {k: v for k, v in CHART.items() if k not in ("name",)}
			frappe.db.set_value("Dashboard Chart", CHART["name"], payload)
		else:
			doc = frappe.new_doc("Dashboard Chart")
			for k, v in CHART.items():
				setattr(doc, k, v)
			doc.insert(ignore_permissions=True)
	frappe.db.commit()
