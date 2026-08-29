"""Idempotent installer for goods_transport print formats.

Each format is a custom Jinja Print Format record. `standard='No'` so users
can duplicate + edit in the Print Format Builder. Re-running install
overwrites the shipped HTML.
"""

import os

import frappe


HERE = os.path.dirname(__file__)

FORMATS = [
	{"name": "Bilty (Standard)", "doctype": "Bilty", "file": "bilty_print_format.html"},
	{"name": "Trip Sheet (Standard)", "doctype": "Transport Trip", "file": "trip_sheet_print_format.html"},
	{"name": "Transport Order (Standard)", "doctype": "Transport Order", "file": "transport_order_print_format.html"},
	{"name": "Proof of Delivery (Standard)", "doctype": "Proof of Delivery", "file": "pod_print_format.html"},
	{"name": "Trip Settlement (Standard)", "doctype": "Trip Settlement", "file": "trip_settlement_print_format.html"},
]


def install_all_print_formats():
	for spec in FORMATS:
		html_path = os.path.join(HERE, spec["file"])
		if not os.path.exists(html_path):
			continue
		with open(html_path, encoding="utf-8") as f:
			html = f.read()
		_upsert(name=spec["name"], doctype=spec["doctype"], html=html)
	frappe.db.commit()


def install_bilty_print_format():
	# Kept for backwards compatibility with the v1 patch entry.
	install_all_print_formats()


def _upsert(name: str, doctype: str, html: str):
	payload = {"html": html, "custom_format": 1, "raw_printing": 0, "standard": "No", "print_format_type": "Jinja"}
	if frappe.db.exists("Print Format", name):
		frappe.db.set_value("Print Format", name, payload)
	else:
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": doctype,
				"module": "Goods Transport",
				"disabled": 0,
				**payload,
			}
		).insert(ignore_permissions=True)
