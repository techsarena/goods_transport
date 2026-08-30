"""Seed standard masters this app expects to exist on any fresh install:

Freight-service side (customer invoice + trip expense lines):
- Supplier Group 'Transporter'
- Item Group 'Freight Services'
- Freight-charge Items (Freight, Loading, Unloading, Toll Recovery,
  Detention, Documentation, Weighbridge, Labour, Night Delivery, Handling,
  Vehicle Hire)

Cargo-classification side (physical goods carried, never invoiced as-is):
- Item Group 'Cargo Items'
- 10 broad cargo classifications (Container, Steel Coil, Transformer,
  Machine, Vehicle, Cement, Chemicals, Textile Goods, Food Products,
  General Cargo). Shipment-specific detail goes in each row's Description.

Cargo Items are intentionally non-stock, non-sales, non-purchase — they
describe what is being moved, not something we sell or buy. They are
enforced as the only allowable Item Group for Transport Order.commodity
and Bilty Cargo rows (see services/cargo.py).

Idempotent. Safe to re-run on migrate. Skips any record that already
exists so user modifications to seeded records are preserved.
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


CARGO_ITEM_GROUP = "Cargo Items"

CARGO_ITEMS = [
	{"code": "CARGO-CONTAINER", "name": "Container", "uom": "Nos"},
	{"code": "CARGO-STEEL-COIL", "name": "Steel Coil", "uom": "Nos"},
	{"code": "CARGO-TRANSFORMER", "name": "Transformer", "uom": "Nos"},
	{"code": "CARGO-MACHINE", "name": "Machine", "uom": "Nos"},
	{"code": "CARGO-VEHICLE", "name": "Vehicle", "uom": "Nos"},
	{"code": "CARGO-CEMENT", "name": "Cement", "uom": "Kg"},
	{"code": "CARGO-CHEMICALS", "name": "Chemicals", "uom": "Kg"},
	{"code": "CARGO-TEXTILE-GOODS", "name": "Textile Goods", "uom": "Kg"},
	{"code": "CARGO-FOOD-PRODUCTS", "name": "Food Products", "uom": "Kg"},
	{"code": "CARGO-GENERAL", "name": "General Cargo", "uom": "Kg"},
]

CARGO_ITEM_DESCRIPTION = (
	"Transport cargo classification — represents a category of physical goods carried by a vehicle. "
	"Enter shipment-specific details (serial number, container number, dimensions, hazardous class, "
	"loading instructions, etc.) in the Description field of each Bilty Cargo row. "
	"This Item is NOT a freight-service or invoice line."
)


DEFAULT_TRIP_EXPENSE_TYPES = [
	# (name, requires_receipt, billable_by_default, description)
	{
		"name": "Fuel",
		"requires_receipt": 1,
		"billable_by_default": 0,
		"description": "Diesel, petrol, CNG, or other vehicle fuel.",
	},
	{
		"name": "Driver Food",
		"requires_receipt": 0,
		"billable_by_default": 0,
		"description": "Meals and food provided during the Trip.",
	},
	{
		"name": "Tyre Repair",
		"requires_receipt": 1,
		"billable_by_default": 0,
		"description": "Puncture repair, tyre replacement, tube, or tyre-related work.",
	},
	{
		"name": "Vehicle Repair",
		"requires_receipt": 1,
		"billable_by_default": 0,
		"description": "Mechanical, electrical, roadside, or workshop repair.",
	},
	{
		"name": "Traffic Challan",
		"requires_receipt": 1,
		"billable_by_default": 0,
		"description": (
			"Traffic fines or challans incurred during the Trip. Not billable to customer by default; "
			"cost allocation between company, driver, or transporter follows company policy."
		),
	},
	{
		"name": "Driver Allowance",
		"requires_receipt": 0,
		"billable_by_default": 0,
		"description": (
			"Actual allowance paid or consumed for the Trip. Distinct from the planned "
			"driver_allowance field on Transport Trip which is informational only — Trip "
			"Settlement's total_cost sums actual Trip Expenses, not the planned value, so "
			"recording an actual Driver Allowance here does not double-count."
		),
	},
	{
		"name": "Other Trip Expense",
		"requires_receipt": 1,
		"billable_by_default": 0,
		"description": "Exceptional Trip expenses not covered by another type.",
	},
]


def install_transport_masters():
	_ensure_supplier_group()
	_ensure_item_group()
	_ensure_freight_items()
	install_cargo_item_group_and_items()
	install_trip_expense_types()
	frappe.db.commit()


def install_trip_expense_types():
	"""Idempotent seeder for the seven default Trip Expense Type records.

	Exposed as a standalone entry point so migration patches can call it
	without re-touching other masters. Skips any name that already exists —
	user modifications and user-created types are preserved untouched."""
	_ensure_trip_expense_types()
	frappe.db.commit()


def install_cargo_item_group_and_items():
	"""Idempotent installer for the Cargo Items group and its seeded items.

	Exposed as a separate function so it can be called on its own from a
	migration patch without re-touching the freight-side masters."""
	_ensure_cargo_item_group()
	_ensure_cargo_items()
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


def _ensure_cargo_item_group():
	if not frappe.db.exists("Item Group", "All Item Groups"):
		return
	if not frappe.db.exists("Item Group", CARGO_ITEM_GROUP):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": CARGO_ITEM_GROUP,
				"parent_item_group": "All Item Groups",
				# is_group=1 so users can add sub-classifications (e.g.
				# 'Perishable Food' under 'Food Products') without breaking
				# the cargo filter, which matches root + descendants.
				"is_group": 1,
			}
		).insert(ignore_permissions=True)


def _ensure_trip_expense_types():
	if not frappe.db.exists("DocType", "Trip Expense Type"):
		# Fresh install order: caller must run the DocType sync first. Skip
		# quietly rather than error out during a partial migrate.
		return
	for spec in DEFAULT_TRIP_EXPENSE_TYPES:
		if frappe.db.exists("Trip Expense Type", spec["name"]):
			# Preserve user modifications — do not overwrite requires_receipt,
			# billable_by_default, or default account/item once the record exists.
			continue
		frappe.get_doc(
			{
				"doctype": "Trip Expense Type",
				"expense_type_name": spec["name"],
				"is_active": 1,
				"requires_receipt": spec["requires_receipt"],
				"billable_by_default": spec["billable_by_default"],
				"description": spec["description"],
				# default_expense_account / default_item intentionally left
				# empty — company-specific and require a valid account for the
				# Trip's company; users pick per-company on the Expense Type
				# record after install.
			}
		).insert(ignore_permissions=True)


def _ensure_cargo_items():
	if not frappe.db.exists("Item Group", CARGO_ITEM_GROUP):
		return
	for spec in CARGO_ITEMS:
		if frappe.db.exists("Item", spec["code"]):
			# Preserve any user modifications — do not overwrite.
			continue
		if not frappe.db.exists("UOM", spec["uom"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": spec["code"],
				"item_name": spec["name"],
				"item_group": CARGO_ITEM_GROUP,
				"stock_uom": spec["uom"],
				"description": CARGO_ITEM_DESCRIPTION,
				# Cargo classifications never appear on our own SI/PI:
				"is_stock_item": 0,
				"is_sales_item": 0,
				"is_purchase_item": 0,
				"disabled": 0,
			}
		).insert(ignore_permissions=True)
