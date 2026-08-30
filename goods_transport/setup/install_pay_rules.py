"""A company-wide default Driver Pay Rule so earnings work out of the box.

Rates ship at zero — a rule with no rates earns nothing, which is the safe
default. Set the rates (or add a more specific rule per driver / vehicle type /
route) before running payroll.
"""

import frappe


def install_default_pay_rules():
	for company in frappe.get_all("Company", fields=["name", "abbr"]):
		name = f"Default Driver Pay - {company.abbr}"
		if frappe.db.exists("Driver Pay Rule", name):
			continue
		doc = frappe.new_doc("Driver Pay Rule")
		doc.rule_name = name
		doc.company = company.name
		doc.is_active = 1
		doc.trip_component = "Trip Allowance"
		doc.km_component = "Distance Allowance"
		doc.tonnage_component = "Tonnage Allowance"
		doc.commission_component = "Freight Commission"
		doc.recover_advances = 1
		doc.recovery_component = "Driver Advance Recovery"
		doc.max_recovery_per_month = 0
		doc.flags.ignore_permissions = True
		doc.insert()
