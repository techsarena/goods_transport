"""Wipe every transaction the demo seeder created, keeping master data.

Deletes in dependency order, cancelling submitted documents first. Master
records (customers, vehicles, drivers, routes, pay rules, salary structures)
are left alone so re-seeding is fast.

	bench --site <site> execute goods_transport.demo.reset.run
"""

import frappe

# Child-most first.
ORDER = [
	"Salary Slip",
	"Payroll Entry",
	"Additional Salary",
	"Driver Payroll Run",
	"Driver Trip Earning",
	"Trip Settlement",
	"Sales Invoice",
	"Purchase Invoice",
	"Proof of Delivery",
	"Trip Expense",
	"Trip Advance",
	"Journal Entry",
	"Bilty",
	"Transport Trip",
	"Transport Order",
	"GL Entry",
	"Payment Ledger Entry",
]


def _sweep(report=True):
	"""One pass over every doctype, cancelling then deleting."""
	remaining = {}
	for doctype in ORDER:
		if not frappe.db.table_exists(doctype):
			continue
		names = frappe.get_all(doctype, pluck="name")
		for name in names:
			try:
				doc = frappe.get_doc(doctype, name)
				if getattr(doc, "docstatus", 0) == 1:
					doc.flags.ignore_permissions = True
					doc.flags.ignore_links = True
					doc.cancel()
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True,
					delete_permanently=True)
			except Exception:
				pass
		frappe.db.commit()
		left = frappe.db.count(doctype) if frappe.db.table_exists(doctype) else 0
		if names and report:
			print(f"  · cleared {len(names) - left} {doctype}" + (f" ({left} left)" if left else ""))
		if left:
			remaining[doctype] = left
	return remaining


def run():
	# Two passes: a document can refuse deletion until whatever links to it is
	# gone, and the first pass is what removes those links.
	frappe.flags.ignore_links = True
	_sweep(report=False)
	remaining = _sweep(report=True)
	if remaining:
		print(f"  ! still present: {remaining}")
	print("demo transactions cleared")
