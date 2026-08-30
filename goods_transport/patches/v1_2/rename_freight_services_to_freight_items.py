"""Rename the Item Group 'Freight Services' → 'Freight Items'.

The 11 freight-charge Items already sitting in the group keep their
item_code untouched. Their `item_group` field is updated automatically by
`frappe.rename_doc` because Item Group uses `autoname: field:item_group_name`,
so its name IS its display name and Frappe's rename machinery walks every
Link → Item Group across the DB to update the referenced value.

Idempotent:
- If 'Freight Services' does not exist (fresh install or already renamed), do nothing.
- If 'Freight Items' already exists AND 'Freight Services' also exists (unlikely,
  hand-created), we do not merge automatically — leave both and let the admin
  resolve.
"""

import frappe


OLD_NAME = "Freight Services"
NEW_NAME = "Freight Items"


def execute():
	if not frappe.db.exists("Item Group", OLD_NAME):
		# Nothing to rename — either fresh install (seeder already used the new
		# name) or a prior run renamed it.
		return
	if frappe.db.exists("Item Group", NEW_NAME):
		# Both exist. Do not auto-merge — that would risk collapsing distinct
		# user-created groups. Log and skip; the admin can merge in the desk.
		frappe.log_error(
			f"Both '{OLD_NAME}' and '{NEW_NAME}' Item Groups exist; "
			"skipping rename patch. Merge them manually in Item Group tree.",
			"goods_transport rename_freight_services_to_freight_items",
		)
		return
	# rename_doc runs under Administrator during a patch, so no permissions kwarg.
	frappe.rename_doc("Item Group", OLD_NAME, NEW_NAME, force=True, show_alert=False)
	frappe.db.commit()
