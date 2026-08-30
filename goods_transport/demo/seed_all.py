"""One-command demo dataset.

	bench --site <site> execute goods_transport.demo.seed_all.run

Wipes existing transactions first (masters are kept and reused), then seeds
three months of operations and two months of processed payroll. The current
month is left unprocessed so the payroll flow can be run live in front of the
client.

To clear the transactions without re-seeding:

	bench --site <site> execute goods_transport.demo.reset.run
"""

import frappe

from goods_transport.demo import (
	reset,
	seed_collections,
	seed_masters,
	seed_operations,
	seed_payroll,
)


def run(skip_reset: bool = False):
	if not skip_reset:
		print("\n[0/4] Clearing existing demo transactions")
		reset.run()

	seed_masters.run()
	seed_operations.run()
	seed_collections.run()
	seed_payroll.run()

	print("\n[4/4] Summary")
	counts = {
		"Customers": frappe.db.count("Customer"),
		"Vehicles": frappe.db.count("Vehicle"),
		"Drivers": frappe.db.count("Driver"),
		"Transport Orders": frappe.db.count("Transport Order", {"docstatus": 1}),
		"Trips": frappe.db.count("Transport Trip", {"docstatus": 1}),
		"Bilties": frappe.db.count("Bilty", {"docstatus": 1}),
		"Sales Invoices": frappe.db.count("Sales Invoice", {"docstatus": 1}),
		"Purchase Invoices": frappe.db.count("Purchase Invoice", {"docstatus": 1}),
		"Trip Settlements": frappe.db.count("Trip Settlement", {"docstatus": 1}),
		"Driver Trip Earnings": frappe.db.count("Driver Trip Earning"),
		"Driver Payroll Runs": frappe.db.count("Driver Payroll Run", {"docstatus": 1}),
		"Salary Slips": frappe.db.count("Salary Slip", {"docstatus": 1}),
		"Payment Entries": frappe.db.count("Payment Entry", {"docstatus": 1}),
	}
	for label, value in counts.items():
		print(f"  {label:24} {value}")
	frappe.db.commit()
	return counts
