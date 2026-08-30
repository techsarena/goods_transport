"""Salary components, their accounts, and the default driver salary structure.

Accounting shape
----------------
	Driver Trip Earnings  (Expense)  <- every trip-based earning component
	Driver Advances       (Asset)    <- Trip Advance debits it; the
	                                    "Driver Advance Recovery" deduction
	                                    credits it back through the Salary Slip

Because the recovery deduction posts to the same asset account the Trip
Advance debited, recovering an advance from salary clears the driver's
balance in the GL with no manual Journal Entry.

Every function is idempotent and safe on `bench migrate`.
"""

import frappe
from frappe import _

#: (component name, abbreviation, type, depends_on_payment_days)
DRIVER_COMPONENTS = [
	("Driver Basic Salary", "DBS", "Earning", 1),
	("Trip Allowance", "TA", "Earning", 0),
	("Distance Allowance", "DA", "Earning", 0),
	("Tonnage Allowance", "TNA", "Earning", 0),
	("Freight Commission", "FC", "Earning", 0),
	("Driver Advance Recovery", "DAR", "Deduction", 0),
]

EARNING_ACCOUNT = "Driver Trip Earnings"
ADVANCE_ACCOUNT = "Driver Advances"
SALARY_STRUCTURE_PREFIX = "Driver Salary Structure"


def _companies():
	return frappe.get_all("Company", fields=["name", "abbr", "default_currency"])


def _find_parent(company, candidates, root_type):
	"""First existing group account among candidates, else any group of that root type."""
	for parent in candidates:
		name = frappe.db.get_value(
			"Account", {"company": company, "account_name": parent, "is_group": 1}, "name"
		)
		if name:
			return name
	return frappe.db.get_value(
		"Account", {"company": company, "root_type": root_type, "is_group": 1}, "name"
	)


def _ensure_account(company, abbr, account_name, root_type, parent_candidates):
	existing = frappe.db.get_value(
		"Account", {"company": company, "account_name": account_name}, "name"
	)
	if existing:
		return existing

	parent = _find_parent(company, parent_candidates, root_type)
	if not parent:
		return None

	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.company = company
	acc.parent_account = parent
	acc.root_type = root_type
	acc.report_type = "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"
	acc.is_group = 0
	acc.account_currency = frappe.get_cached_value("Company", company, "default_currency")
	acc.insert(ignore_permissions=True)
	return acc.name


def install_driver_advance_accounts():
	"""Create the Driver Advances (asset) and Driver Trip Earnings (expense) accounts."""
	for company in _companies():
		_ensure_account(
			company.name, company.abbr, ADVANCE_ACCOUNT, "Asset",
			["Loans and Advances (Assets)", "Current Assets", "Application of Funds (Assets)"],
		)
		_ensure_account(
			company.name, company.abbr, EARNING_ACCOUNT, "Expense",
			["Indirect Expenses", "Expenses"],
		)


def _component_accounts(component_doc, company, account_name):
	account = frappe.db.get_value(
		"Account", {"company": company, "account_name": account_name}, "name"
	)
	if not account:
		return
	for row in component_doc.accounts:
		if row.company == company:
			if not row.account:
				row.account = account
			return
	component_doc.append("accounts", {"company": company, "account": account})


def _account_for(component_name: str) -> str:
	"""Recovery credits the advance asset; base salary uses the company's
	existing Salary account when the chart has one; trip pay is its own line."""
	if component_name == "Driver Advance Recovery":
		return ADVANCE_ACCOUNT
	if component_name == "Driver Basic Salary" and frappe.db.exists(
		"Account", {"account_name": "Salary", "is_group": 0}
	):
		return "Salary"
	return EARNING_ACCOUNT


def install_driver_salary_components():
	"""Seed the six driver components and point each at the right account."""
	for name, abbr, ctype, dopd in DRIVER_COMPONENTS:
		if frappe.db.exists("Salary Component", name):
			doc = frappe.get_doc("Salary Component", name)
		else:
			doc = frappe.new_doc("Salary Component")
			doc.salary_component = name
			doc.salary_component_abbr = abbr
			doc.type = ctype
			doc.description = _("Created by Transporter Payroll.")

		doc.depends_on_payment_days = dopd
		doc.remove_if_zero_valued = 1
		doc.is_tax_applicable = 1 if ctype == "Earning" else 0

		account_name = _account_for(name)
		for company in _companies():
			_component_accounts(doc, company.name, account_name)

		doc.flags.ignore_permissions = True
		doc.save()


def install_driver_salary_structure():
	"""One submitted monthly structure per company: Basic = base."""
	for company in _companies():
		name = f"{SALARY_STRUCTURE_PREFIX} - {company.abbr}"
		if frappe.db.exists("Salary Structure", name):
			continue

		doc = frappe.new_doc("Salary Structure")
		doc.name = name
		doc.company = company.name
		doc.currency = company.default_currency
		doc.is_active = "Yes"
		doc.payroll_frequency = "Monthly"
		doc.append("earnings", {
			"salary_component": "Driver Basic Salary",
			"abbr": "DBS",
			"amount_based_on_formula": 1,
			"formula": "base",
			"depends_on_payment_days": 1,
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
