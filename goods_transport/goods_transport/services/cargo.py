"""Cargo Item classification helpers.

Transport Order commodity and Bilty Cargo rows must reference physical-cargo
Items only — Items whose Item Group is `Cargo Items` or any descendant group.
Freight, Labour, Vehicle Hire, etc. are service Items that belong on
Sales/Purchase Invoices, not in the cargo section.

The helpers here are used by:
- Link-field `get_query` on both DocTypes (client-side hint for users)
- validate() on both DocTypes (server-side enforcement — the source of truth)
"""

from __future__ import annotations

import frappe
from frappe import _


CARGO_ROOT_ITEM_GROUP = "Cargo Items"


def get_cargo_item_groups() -> list[str]:
	"""Return the Item Group names that count as cargo: the root plus every
	descendant in the nested set. Returns [] if the root group has not been
	installed yet (fresh install before the master seeder runs)."""
	if not frappe.db.exists("Item Group", CARGO_ROOT_ITEM_GROUP):
		return []
	descendants = frappe.db.get_descendants("Item Group", CARGO_ROOT_ITEM_GROUP) or []
	return [CARGO_ROOT_ITEM_GROUP] + list(descendants)


def is_cargo_item(item_code: str | None) -> bool:
	if not item_code:
		return False
	item_group = frappe.db.get_value("Item", item_code, "item_group")
	if not item_group:
		return False
	return item_group in get_cargo_item_groups()


def validate_cargo_item(item_code: str | None, row_idx: int | None = None) -> None:
	"""Raise a ValidationError with a clear message when a non-cargo Item
	is used in a cargo context."""
	if not item_code:
		return
	if is_cargo_item(item_code):
		return
	prefix = _("Row {0}: ").format(row_idx) if row_idx else ""
	frappe.throw(
		prefix
		+ _(
			"Item {0} is not a Cargo Item. Select an Item from the Cargo Items group for physical cargo. "
			"Freight and additional services belong in the Freight or Additional Charges sections."
		).format(frappe.bold(item_code))
	)


@frappe.whitelist()
def cargo_item_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query returning only enabled Items in Cargo Items or a descendant.

	Columns returned: name, item_name, item_group, stock_uom — Frappe will render
	all of them in the Link picker so users see the classification and UOM."""
	groups = get_cargo_item_groups()
	if not groups:
		return []
	search = f"%{txt}%" if txt else "%"
	return frappe.db.sql(
		"""
		SELECT name, item_name, item_group, stock_uom
		FROM `tabItem`
		WHERE disabled = 0
		  AND item_group IN %(groups)s
		  AND (name LIKE %(s)s OR item_name LIKE %(s)s OR item_group LIKE %(s)s)
		ORDER BY name
		LIMIT %(start)s, %(page_len)s
		""",
		{"groups": tuple(groups), "s": search, "start": start, "page_len": page_len},
	)
