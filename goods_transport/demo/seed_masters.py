"""Stage 1 — prerequisites and master data for the transporter demo.

Idempotent: every helper checks for an existing record first, so the whole
seeder can be re-run safely.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_years, flt, getdate

from goods_transport.demo import data as D

COMPANY = "Techs Arena"
HOLIDAY_LIST = "Techs Arena Holidays 2026"


def log(msg):
	print(f"  · {msg}")


# --------------------------------------------------------------- prerequisites
def ensure_fiscal_years():
	"""Trips start in June 2026, which falls in FY 2025-2026."""
	for start, end, name in (
		("2025-07-01", "2026-06-30", "2025-2026"),
		("2026-07-01", "2027-06-30", "2026-2027"),
	):
		if frappe.db.exists("Fiscal Year", name):
			continue
		fy = frappe.new_doc("Fiscal Year")
		fy.year = name
		fy.year_start_date = start
		fy.year_end_date = end
		fy.insert(ignore_permissions=True)
		log(f"Fiscal Year {name}")


def ensure_accounts():
	company = frappe.get_doc("Company", COMPANY)
	abbr = company.abbr

	def child(account_name, parent_name, account_type=None, root_type="Asset"):
		full = f"{account_name} - {abbr}"
		if frappe.db.exists("Account", full):
			return full
		parent = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": parent_name, "is_group": 1}, "name"
		)
		if not parent:
			return None
		acc = frappe.new_doc("Account")
		acc.account_name = account_name
		acc.company = COMPANY
		acc.parent_account = parent
		acc.root_type = root_type
		acc.report_type = "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"
		acc.account_type = account_type
		acc.account_currency = company.default_currency
		acc.insert(ignore_permissions=True)
		log(f"Account {full}")
		return full

	bank = child("HBL Current Account", "Bank Accounts", account_type="Bank")
	payroll_payable = child("Payroll Payable", "Current Liabilities", root_type="Liability")
	freight_income = child("Freight Income", "Direct Income", root_type="Income")
	vehicle_hire = child("Vehicle Hire Charges", "Direct Expenses", root_type="Expense")

	updates = {}
	if bank and not company.default_bank_account:
		updates["default_bank_account"] = bank
	if payroll_payable and not company.default_payroll_payable_account:
		updates["default_payroll_payable_account"] = payroll_payable
	if updates:
		frappe.db.set_value("Company", COMPANY, updates)
	return {
		"bank": bank or company.default_cash_account,
		"cash": company.default_cash_account,
		"freight_income": freight_income or company.default_income_account,
		"vehicle_hire": vehicle_hire or company.default_expense_account,
		"payroll_payable": payroll_payable,
	}


def ensure_holiday_list():
	if frappe.db.exists("Holiday List", HOLIDAY_LIST):
		return HOLIDAY_LIST
	hl = frappe.new_doc("Holiday List")
	hl.holiday_list_name = HOLIDAY_LIST
	hl.from_date = "2026-01-01"
	hl.to_date = "2026-12-31"
	hl.weekly_off = "Sunday"
	hl.insert(ignore_permissions=True)
	hl.get_weekly_off_dates()
	hl.save(ignore_permissions=True)
	frappe.db.set_value("Company", COMPANY, "default_holiday_list", HOLIDAY_LIST)
	log(f"Holiday List {HOLIDAY_LIST}")
	return HOLIDAY_LIST


def ensure_transport_masters():
	"""goods_transport's own seeder — freight items, cargo items, expense types."""
	from goods_transport.setup.install_masters import install_transport_masters

	install_transport_masters()
	log("goods_transport masters (freight items, cargo items, expense types)")


# ---------------------------------------------------------------- master data
def seed_locations():
	for city, state in D.LOCATIONS:
		if frappe.db.exists("Transport Location", city):
			continue
		doc = frappe.new_doc("Transport Location")
		doc.location_name = city
		doc.location_type = "Port" if city in ("Karachi", "Port Qasim") else "Terminal"
		doc.is_active = 1
		if doc.meta.has_field("city"):
			doc.city = city
		if doc.meta.has_field("country"):
			doc.country = "Pakistan"
		doc.insert(ignore_permissions=True)
	log(f"{len(D.LOCATIONS)} transport locations")


def route_name(origin, destination):
	return f"{origin} - {destination}"


def seed_routes():
	for origin, dest, km, hours, toll, fuel in D.ROUTES:
		name = route_name(origin, dest)
		if frappe.db.exists("Transport Route", name):
			continue
		doc = frappe.new_doc("Transport Route")
		doc.route_name = name
		doc.origin = origin
		doc.destination = dest
		doc.distance_km = km
		doc.expected_duration_hours = hours
		doc.estimated_toll = toll
		doc.estimated_fuel_litres = fuel
		doc.is_active = 1
		doc.insert(ignore_permissions=True)
	log(f"{len(D.ROUTES)} routes")


def seed_vehicle_types():
	for name, payload, volume in D.VEHICLE_TYPES:
		if frappe.db.exists("Vehicle Type", name):
			continue
		doc = frappe.new_doc("Vehicle Type")
		doc.vehicle_type_name = name
		doc.default_payload_capacity = payload
		doc.default_volume_capacity = volume
		doc.is_active = 1
		doc.insert(ignore_permissions=True)
	log(f"{len(D.VEHICLE_TYPES)} vehicle types")


def seed_transporters():
	group = "Transporter" if frappe.db.exists("Supplier Group", "Transporter") else "All Supplier Groups"
	for name in D.TRANSPORTERS:
		if frappe.db.exists("Supplier", name):
			continue
		doc = frappe.new_doc("Supplier")
		doc.supplier_name = name
		doc.supplier_group = group
		doc.supplier_type = "Company"
		doc.country = "Pakistan"
		doc.insert(ignore_permissions=True)
	log(f"{len(D.TRANSPORTERS)} transporters (suppliers)")


def seed_customers():
	group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
	territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
	for name, city in D.CUSTOMERS:
		if frappe.db.exists("Customer", name):
			continue
		doc = frappe.new_doc("Customer")
		doc.customer_name = name
		doc.customer_group = group
		doc.territory = territory
		doc.customer_type = "Company"
		doc.insert(ignore_permissions=True)
	log(f"{len(D.CUSTOMERS)} customers")


def seed_vehicles():
	for plate, vtype, ownership, make, model, owner in D.VEHICLES:
		if frappe.db.exists("Vehicle", plate):
			continue
		doc = frappe.new_doc("Vehicle")
		doc.license_plate = plate
		doc.make = make
		doc.model = model
		doc.last_odometer = 100000
		doc.acquisition_date = "2024-03-15"
		doc.fuel_type = "Diesel"
		doc.uom = "Litre" if frappe.db.exists("UOM", "Litre") else frappe.db.get_value("UOM", {}, "name")
		doc.vehicle_value = 18500000 if "Trailer" in vtype else 9500000
		# goods_transport custom fields
		doc.ownership_type = ownership
		doc.vehicle_type = vtype
		doc.current_status = "Available"
		payload = dict((t[0], t[1]) for t in D.VEHICLE_TYPES).get(vtype)
		doc.payload_capacity = payload
		if owner:
			doc.transporter = owner
			doc.vehicle_owner = owner
		doc.insert(ignore_permissions=True)
	log(f"{len(D.VEHICLES)} vehicles ({sum(1 for v in D.VEHICLES if v[2] == 'Company Owned')} owned, "
	    f"{sum(1 for v in D.VEHICLES if v[2] != 'Company Owned')} market/attached)")


def ensure_designation(name):
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
	return name


def ensure_department(name):
	full = f"{name} - {frappe.get_cached_value('Company', COMPANY, 'abbr')}"
	if frappe.db.exists("Department", full):
		return full
	if frappe.db.exists("Department", name):
		return name
	doc = frappe.new_doc("Department")
	doc.department_name = name
	doc.company = COMPANY
	doc.parent_department = "All Departments"
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_drivers_and_employees():
	"""Company drivers get an Employee + salary structure; market drivers do not."""
	designation = ensure_designation("Driver")
	department = ensure_department("Fleet Operations")
	holiday_list = ensure_holiday_list()
	structure = f"Driver Salary Structure - {frappe.get_cached_value('Company', COMPANY, 'abbr')}"

	created = 0
	for idx, (full_name, cell, licence, base, is_company) in enumerate(D.DRIVERS):
		driver_name = frappe.db.get_value("Driver", {"full_name": full_name}, "name")

		employee = None
		if is_company:
			employee = frappe.db.get_value("Employee", {"employee_name": full_name}, "name")
			if not employee:
				emp = frappe.new_doc("Employee")
				emp.first_name = full_name.split()[0]
				emp.last_name = " ".join(full_name.split()[1:]) or "."
				emp.employee_name = full_name
				emp.gender = "Male"
				emp.date_of_birth = f"19{75 + idx}-04-{10 + idx:02d}"
				emp.date_of_joining = "2025-01-15"
				emp.company = COMPANY
				emp.status = "Active"
				emp.designation = designation
				emp.department = department
				emp.holiday_list = holiday_list
				emp.cell_number = cell
				emp.insert(ignore_permissions=True)
				employee = emp.name

			if base and not frappe.db.exists(
				"Salary Structure Assignment", {"employee": employee, "docstatus": 1}
			):
				ssa = frappe.new_doc("Salary Structure Assignment")
				ssa.employee = employee
				ssa.salary_structure = structure
				ssa.from_date = "2026-01-01"
				ssa.company = COMPANY
				ssa.base = base
				ssa.currency = frappe.get_cached_value("Company", COMPANY, "default_currency")
				ssa.insert(ignore_permissions=True)
				ssa.submit()

		if not driver_name:
			doc = frappe.new_doc("Driver")
			doc.full_name = full_name
			doc.status = "Active"
			doc.cell_number = cell
			doc.license_number = licence
			doc.employee = employee
			doc.insert(ignore_permissions=True)
			created += 1
		elif employee and not frappe.db.get_value("Driver", driver_name, "employee"):
			frappe.db.set_value("Driver", driver_name, "employee", employee)

	log(f"{created} drivers ({sum(1 for d in D.DRIVERS if d[4])} on payroll, "
	    f"{sum(1 for d in D.DRIVERS if not d[4])} market drivers without Employee)")


def seed_pay_rules():
	"""A company default plus two more specific rules, to show resolution."""
	abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
	rules = [
		# name, driver, vehicle_type, route, per_trip, per_km, per_ton, commission %, cap
		(f"Default Driver Pay - {abbr}", None, None, None, 2500, 1.5, 0, 0, 25000),
		("Trailer Long Haul Pay", None, "22-Wheeler Trailer", None, 4000, 2.5, 0, 1.0, 30000),
		("Muhammad Aslam - Senior Driver", "Muhammad Aslam", None, None, 5000, 2.75, 0, 1.5, 35000),
	]
	for name, driver_name, vtype, route, per_trip, per_km, per_ton, commission, cap in rules:
		driver = frappe.db.get_value("Driver", {"full_name": driver_name}, "name") if driver_name else None
		if frappe.db.exists("Driver Pay Rule", name):
			doc = frappe.get_doc("Driver Pay Rule", name)
		else:
			doc = frappe.new_doc("Driver Pay Rule")
			doc.rule_name = name
		doc.company = COMPANY
		doc.is_active = 1
		doc.driver = driver
		doc.vehicle_type = vtype
		doc.route = route
		doc.per_trip_amount = per_trip
		doc.trip_component = "Trip Allowance"
		doc.rate_per_km = per_km
		doc.km_component = "Distance Allowance"
		doc.rate_per_ton = per_ton
		doc.tonnage_component = "Tonnage Allowance"
		doc.commission_percent = commission
		doc.commission_component = "Freight Commission"
		doc.recover_advances = 1
		doc.recovery_component = "Driver Advance Recovery"
		doc.max_recovery_per_month = cap
		doc.flags.ignore_permissions = True
		doc.save()
	log(f"{len(rules)} driver pay rules")


def seed_rate_contracts(accounts):
	"""Customer freight rates for the busiest lanes."""
	contracts = [
		("Lucky Cement Ltd", "Karachi - Lahore", "22-Wheeler Trailer", "Per Trip", 285000),
		("Engro Fertilizers Ltd", "Karachi - Multan", "18-Wheeler Trailer", "Per Trip", 210000),
		("Nishat Textile Mills", "Faisalabad - Karachi", "10-Wheeler Truck", "Per Trip", 195000),
		("Pak Steel Traders", "Port Qasim - Lahore", "40ft Flatbed Trailer", "Per Trip", 295000),
	]
	made = 0
	for customer, route, vtype, basis, rate in contracts:
		if frappe.db.exists("Transport Rate Contract", {"customer": customer, "route": route}):
			continue
		doc = frappe.new_doc("Transport Rate Contract")
		doc.customer = customer
		doc.route = route
		if doc.meta.has_field("vehicle_type"):
			doc.vehicle_type = vtype
		doc.rate_basis = basis
		doc.rate = rate
		doc.company = COMPANY
		doc.currency = "PKR"
		doc.valid_from = "2026-01-01"
		doc.valid_to = "2026-12-31"
		if doc.meta.has_field("is_active"):
			doc.is_active = 1
		doc.insert(ignore_permissions=True)
		made += 1
	log(f"{made} rate contracts")


def run():
	print("\n[1/4] Prerequisites and masters")
	ensure_fiscal_years()
	accounts = ensure_accounts()
	ensure_holiday_list()
	ensure_transport_masters()
	seed_locations()
	seed_routes()
	seed_vehicle_types()
	seed_transporters()
	seed_customers()
	seed_vehicles()
	seed_drivers_and_employees()
	seed_pay_rules()
	seed_rate_contracts(accounts)
	frappe.db.commit()
	return accounts
