"""Register Transport Trip as an ERPNext Accounting Dimension.

Creating the Accounting Dimension record makes ERPNext auto-add a
`transport_trip` custom field on every accounting transaction DocType
(Sales Invoice, Purchase Invoice, Journal Entry, Payment Entry, and their
child rows), and tags every GL Entry posted from those documents with the
dimension so Trip P&L is queryable from the GL directly.
"""

import frappe


DIMENSION_DOCTYPES = ["Transport Trip"]


def install_transport_accounting_dimensions():
	# ERPNext's Accounting Dimension DocType only exists if the erpnext app
	# is installed on the site.
	if not frappe.db.exists("DocType", "Accounting Dimension"):
		return

	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
		make_dimension_in_accounting_doctypes,
	)

	for target in DIMENSION_DOCTYPES:
		existing = frappe.db.get_value("Accounting Dimension", {"document_type": target}, "name")
		if existing:
			doc = frappe.get_doc("Accounting Dimension", existing)
		else:
			doc = frappe.new_doc("Accounting Dimension")
			doc.document_type = target
			doc.insert(ignore_permissions=True)
		# on_update enqueues field creation for the background worker; do it
		# synchronously so a fresh site / migrate leaves the fields in place.
		make_dimension_in_accounting_doctypes(doc=doc)
	frappe.db.commit()
