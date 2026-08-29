"""Seed standard masters this app expects to exist on any fresh install:

- Supplier Group 'Transporter'
- Item Group 'Freight Services'
- Freight-charge Items (Freight, Loading, Unloading, Toll Recovery,
  Detention, Documentation, Weighbridge, Labour, Night Delivery, Handling,
  Vehicle Hire)

Idempotent. Safe to re-run on migrate. Skips any record that already exists.
"""

import frappe


FREIGHT_ITEMS = [
	{"code": "Freight", "name": "Freight"},
	{"code": "Loading", "name": "Loading"},
	{"code": "Unloading", "name": "Unloading"},
	{"code": "Toll Recovery", "name": "Toll Recovery"},
	{"code": "Detention", "name": "Detention"},
	{"code": "Documentation", "name": "Documentation"},
	{"code": "Weighbridge", "name": "Weighbridge"},
	{"code": "Labour", "name": "Labour"},
	{"code": "Night Delivery", "name": "Night Delivery"},
	{"code": "Handling", "name": "Handling"},
	{"code": "Vehicle Hire", "name": "Vehicle Hire"},
]


def install_transport_masters():
	_ensure_supplier_group()
	_ensure_item_group()
	_ensure_freight_items()
	frappe.db.commit()


def _ensure_supplier_group():
	if not frappe.db.exists("Supplier Group", "All Supplier Groups"):
		return  # No CoA yet on this site; caller should install ERPNext defaults first.
	if not frappe.db.exists("Supplier Group", "Transporter"):
		frappe.get_doc(
			{
				"doctype": "Supplier Group",
				"supplier_group_name": "Transporter",
				"parent_supplier_group": "All Supplier Groups",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)


def _ensure_item_group():
	if not frappe.db.exists("Item Group", "All Item Groups"):
		return
	if not frappe.db.exists("Item Group", "Freight Services"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "Freight Services",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)


def _ensure_freight_items():
	if not frappe.db.exists("Item Group", "Freight Services"):
		return
	if not frappe.db.exists("UOM", "Nos"):
		return
	for spec in FREIGHT_ITEMS:
		if frappe.db.exists("Item", spec["code"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": spec["code"],
				"item_name": spec["name"],
				"item_group": "Freight Services",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_sales_item": 1,
				"is_purchase_item": 1,
			}
		).insert(ignore_permissions=True)
