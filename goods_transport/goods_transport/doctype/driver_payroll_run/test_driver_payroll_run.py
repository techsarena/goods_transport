"""Tests for trip earnings, advance recovery, and the payroll run.

Fixtures are created per test class and rolled back by FrappeTestCase, so the
suite is safe to run against a site that already holds real data.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from goods_transport.goods_transport.services import advances as advance_service
from goods_transport.goods_transport.services import earnings as earning_service

COMPANY = None


def _company():
	global COMPANY
	if not COMPANY:
		COMPANY = frappe.db.get_value("Company", {}, "name")
	return COMPANY


def _abbr():
	return frappe.get_cached_value("Company", _company(), "abbr")


def _make_employee(name):
	existing = frappe.db.get_value("Employee", {"employee_name": name}, "name")
	if existing:
		return existing
	emp = frappe.new_doc("Employee")
	emp.first_name = name
	emp.employee_name = name
	emp.gender = "Male"
	emp.date_of_birth = "1985-01-01"
	emp.date_of_joining = "2025-01-01"
	emp.company = _company()
	emp.status = "Active"
	emp.insert(ignore_permissions=True)
	_assign_salary_structure(emp.name)
	return emp.name


def _assign_salary_structure(employee):
	if frappe.db.exists("Salary Structure Assignment", {"employee": employee, "docstatus": 1}):
		return
	ssa = frappe.new_doc("Salary Structure Assignment")
	ssa.employee = employee
	ssa.salary_structure = f"Driver Salary Structure - {_abbr()}"
	ssa.from_date = "2025-12-01"
	ssa.company = _company()
	ssa.base = 50000
	ssa.insert(ignore_permissions=True)
	ssa.submit()


def _make_driver(name, with_employee=True):
	existing = frappe.db.get_value("Driver", {"full_name": name}, "name")
	if existing:
		return existing
	doc = frappe.new_doc("Driver")
	doc.full_name = name
	doc.status = "Active"
	if with_employee:
		doc.employee = _make_employee(name)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_vehicle(plate, vehicle_type=None):
	if frappe.db.exists("Vehicle", plate):
		return plate
	doc = frappe.new_doc("Vehicle")
	doc.license_plate = plate
	doc.make = "Test"
	doc.model = "T1"
	doc.last_odometer = 1000
	doc.fuel_type = "Diesel"
	doc.uom = frappe.db.get_value("UOM", {}, "name")
	if vehicle_type:
		doc.vehicle_type = vehicle_type
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_rule(rule_name, **kwargs):
	if frappe.db.exists("Driver Pay Rule", rule_name):
		frappe.delete_doc("Driver Pay Rule", rule_name, force=True)
	doc = frappe.new_doc("Driver Pay Rule")
	doc.rule_name = rule_name
	doc.company = _company()
	doc.is_active = 1
	doc.trip_component = "Trip Allowance"
	doc.km_component = "Distance Allowance"
	doc.tonnage_component = "Tonnage Allowance"
	doc.commission_component = "Freight Commission"
	doc.recover_advances = 1
	doc.recovery_component = "Driver Advance Recovery"
	doc.update(kwargs)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_trip(driver, vehicle, distance=100, status="Delivered", submit=True,
		trip_date="2026-01-05"):
	trip = frappe.new_doc("Transport Trip")
	trip.company = _company()
	trip.trip_date = trip_date
	trip.vehicle = vehicle
	trip.driver = driver
	trip.actual_distance = distance
	trip.insert(ignore_permissions=True)
	if submit:
		trip.submit()
		trip.db_set("status", status)
	return trip


class TestTripEarning(FrappeTestCase):
	def test_rule_resolution_prefers_the_most_specific_rule(self):
		driver = _make_driver("Test Specific Driver")
		_make_rule("TEST Company Default", per_trip_amount=1000)
		_make_rule("TEST Driver Specific", driver=driver, per_trip_amount=9000)

		self.assertEqual(
			earning_service.resolve_pay_rule(company=_company(), driver=driver, on_date="2026-01-05"),
			"TEST Driver Specific",
		)
		self.assertEqual(
			earning_service.resolve_pay_rule(company=_company(), driver=None, on_date="2026-01-05"),
			"TEST Company Default",
		)

	def test_rule_outside_validity_window_is_ignored(self):
		_make_rule("TEST Expired", per_trip_amount=500, valid_from="2020-01-01",
			valid_upto="2020-12-31")
		resolved = earning_service.resolve_pay_rule(company=_company(), on_date="2026-01-05")
		self.assertNotEqual(resolved, "TEST Expired")

	def test_earning_sums_every_configured_basis(self):
		driver = _make_driver("Test Basis Driver")
		vehicle = _make_vehicle("TEST-0001")
		rule = _make_rule("TEST All Bases", driver=driver, per_trip_amount=2000,
			rate_per_km=3, rate_per_ton=100)
		trip = _make_trip(driver, vehicle, distance=250)
		trip.db_set("loaded_weight", 20000)  # 20 tons
		trip.reload()

		values = earning_service.compute_earning(trip, rule)
		self.assertEqual(flt(values["trip_amount"]), 2000)
		self.assertEqual(flt(values["km_amount"]), 750)       # 250 km x 3
		self.assertEqual(flt(values["tonnage_amount"]), 2000)  # 20 t x 100
		self.assertEqual(flt(values["total_earning"]), 4750)

	def test_driver_without_employee_earns_nothing(self):
		driver = _make_driver("Test Market Driver", with_employee=False)
		vehicle = _make_vehicle("TEST-0002")
		_make_rule("TEST Market Rule", driver=driver, per_trip_amount=3000)
		trip = _make_trip(driver, vehicle)

		self.assertIsNone(earning_service.ensure_trip_earning(trip.name))

	def test_earning_is_not_generated_before_delivery(self):
		driver = _make_driver("Test Intransit Driver")
		vehicle = _make_vehicle("TEST-0003")
		_make_rule("TEST Intransit Rule", driver=driver, per_trip_amount=3000)
		trip = _make_trip(driver, vehicle, status="In Transit")

		self.assertIsNone(earning_service.ensure_trip_earning(trip.name))

	def test_regenerating_updates_in_place(self):
		driver = _make_driver("Test Idempotent Driver")
		vehicle = _make_vehicle("TEST-0004")
		_make_rule("TEST Idempotent Rule", driver=driver, per_trip_amount=1500)
		trip = _make_trip(driver, vehicle)

		first = earning_service.ensure_trip_earning(trip.name)
		second = earning_service.ensure_trip_earning(trip.name)
		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count("Driver Trip Earning", {"trip": trip.name}), 1
		)


class TestAdvanceRecovery(FrappeTestCase):
	def _make_advance(self, trip, driver, amount, advance_date="2026-02-05"):
		abbr = _abbr()
		adv = frappe.new_doc("Trip Advance")
		adv.company = _company()
		adv.advance_date = advance_date
		adv.trip = trip.name
		adv.recipient_type = "Driver"
		adv.driver = driver
		adv.amount = amount
		adv.paying_account = f"Cash - {abbr}"
		adv.advance_account = f"Driver Advances - {abbr}"
		adv.insert(ignore_permissions=True)
		adv.submit()
		return adv

	def test_outstanding_reduces_by_expenses_paid_from_the_advance(self):
		driver = _make_driver("Test Advance Driver")
		vehicle = _make_vehicle("TEST-0005")
		trip = _make_trip(driver, vehicle, status="In Transit", trip_date="2026-02-05")
		adv = self._make_advance(trip, driver, 20000)

		self.assertEqual(advance_service.get_outstanding(adv.name), 20000)

		expense_type = frappe.db.get_value(
			"Trip Expense Type", {"requires_receipt": 0}, "name"
		)
		te = frappe.new_doc("Trip Expense")
		te.company = _company()
		te.expense_date = "2026-02-06"
		te.trip = trip.name
		te.expense_type = expense_type
		te.amount = 5000
		te.expense_account = frappe.db.get_value(
			"Account", {"company": _company(), "root_type": "Expense", "is_group": 0}, "name"
		)
		te.payment_mode = "Trip Advance"
		te.trip_advance = adv.name
		te.insert(ignore_permissions=True)
		te.submit()

		self.assertEqual(advance_service.get_outstanding(adv.name), 15000)
		self.assertEqual(advance_service.get_consumed(adv.name), 5000)

	def test_payroll_run_recovers_the_balance_and_marks_it_processed(self):
		driver = _make_driver("Test Payroll Driver")
		vehicle = _make_vehicle("TEST-0006")
		rule = _make_rule("TEST Payroll Rule", driver=driver, per_trip_amount=8000,
			max_recovery_per_month=0)
		trip = _make_trip(driver, vehicle, distance=100, trip_date="2026-05-05")
		adv = self._make_advance(trip, driver, 12000, advance_date="2026-05-05")
		earning = earning_service.ensure_trip_earning(trip.name)
		self.assertIsNotNone(earning)

		employee = frappe.db.get_value("Driver", driver, "employee")
		if not frappe.db.exists("Salary Structure Assignment", {"employee": employee, "docstatus": 1}):
			ssa = frappe.new_doc("Salary Structure Assignment")
			ssa.employee = employee
			ssa.salary_structure = f"Driver Salary Structure - {_abbr()}"
			ssa.from_date = "2026-01-01"
			ssa.company = _company()
			ssa.base = 50000
			ssa.insert(ignore_permissions=True)
			ssa.submit()

		run = frappe.new_doc("Driver Payroll Run")
		run.company = _company()
		run.from_date = "2026-05-01"
		run.to_date = "2026-05-31"
		run.payroll_date = "2026-05-31"
		run.fetch_earnings()

		row = next(r for r in run.details if r.driver == driver)
		self.assertEqual(flt(row.gross_earning), 8000)
		self.assertEqual(flt(row.outstanding_advance), 12000)
		self.assertEqual(flt(row.advance_recovery), 12000)  # no cap set
		self.assertEqual(flt(row.net_addition), -4000)

		run.insert()
		run.submit()

		self.assertEqual(
			frappe.db.get_value("Driver Trip Earning", earning, "status"), "Processed"
		)
		additional = frappe.get_all(
			"Additional Salary",
			filters={"ref_docname": run.name, "docstatus": 1, "employee": employee},
			fields=["salary_component", "amount", "type"],
		)
		components = {a.salary_component: (flt(a.amount), a.type) for a in additional}
		self.assertEqual(components["Trip Allowance"], (8000, "Earning"))
		self.assertEqual(components["Driver Advance Recovery"], (12000, "Deduction"))
		self.assertEqual(advance_service.get_outstanding(adv.name), 0)

		run.cancel()
		self.assertEqual(
			frappe.db.get_value("Driver Trip Earning", earning, "status"), "Pending"
		)
		self.assertEqual(advance_service.get_outstanding(adv.name), 12000)

	def test_recovery_cannot_exceed_the_outstanding_balance(self):
		driver = _make_driver("Test Overrecovery Driver")
		vehicle = _make_vehicle("TEST-0007")
		_make_rule("TEST Overrecovery Rule", driver=driver, per_trip_amount=5000)
		trip = _make_trip(driver, vehicle, trip_date="2026-04-05")
		self._make_advance(trip, driver, 6000, advance_date="2026-04-05")
		earning_service.ensure_trip_earning(trip.name)

		run = frappe.new_doc("Driver Payroll Run")
		run.company = _company()
		run.from_date = "2026-04-01"
		run.to_date = "2026-04-30"
		run.payroll_date = "2026-04-30"
		run.fetch_earnings()
		for row in run.details:
			if row.driver == driver:
				row.advance_recovery = 999999

		self.assertRaises(frappe.ValidationError, run.insert)

	def test_max_recovery_per_month_caps_the_deduction(self):
		driver = _make_driver("Test Capped Driver")
		vehicle = _make_vehicle("TEST-0008")
		_make_rule("TEST Capped Rule", driver=driver, per_trip_amount=5000,
			max_recovery_per_month=3000)
		trip = _make_trip(driver, vehicle, trip_date="2026-03-05")
		self._make_advance(trip, driver, 20000, advance_date="2026-03-05")
		earning_service.ensure_trip_earning(trip.name)

		run = frappe.new_doc("Driver Payroll Run")
		run.company = _company()
		run.from_date = "2026-03-01"
		run.to_date = "2026-03-31"
		run.payroll_date = "2026-03-31"
		run.fetch_earnings()

		row = next(r for r in run.details if r.driver == driver)
		self.assertEqual(flt(row.outstanding_advance), 20000)
		self.assertEqual(flt(row.advance_recovery), 3000)
