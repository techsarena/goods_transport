"""Trip Expense Types — seeding, receipt policy, prefill safety, and
proof that planned + actual Driver Allowance do not double-count in
Trip Settlement.

Run with:
    bench --site <site> run-tests \\
        --module goods_transport.goods_transport.tests.test_trip_expense_types
"""

import unittest

import frappe
from frappe.utils import today

from goods_transport.setup.install_masters import (
	DEFAULT_TRIP_EXPENSE_TYPES,
	install_transport_masters,
	install_trip_expense_types,
)


EXPECTED_NAMES = [s["name"] for s in DEFAULT_TRIP_EXPENSE_TYPES]

RECEIPT_REQUIRED = {"Fuel", "Tyre Repair", "Vehicle Repair", "Traffic Challan", "Other Trip Expense"}
NON_RECEIPT = {"Driver Food", "Driver Allowance"}


class TestTripExpenseTypesSeeding(unittest.TestCase):
	"""All 7 default types are created with the exact flags the spec requires."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()

	def test_all_seven_types_present(self):
		missing = [name for name in EXPECTED_NAMES if not frappe.db.exists("Trip Expense Type", name)]
		self.assertFalse(missing, f"Missing Trip Expense Types: {missing}")
		self.assertEqual(len(EXPECTED_NAMES), 7)

	def test_flags_match_spec_exactly(self):
		for spec in DEFAULT_TRIP_EXPENSE_TYPES:
			row = frappe.db.get_value(
				"Trip Expense Type",
				spec["name"],
				["is_active", "requires_receipt", "billable_by_default", "default_expense_account", "default_item"],
				as_dict=True,
			)
			self.assertEqual(int(row.is_active or 0), 1, f"{spec['name']} must be active")
			self.assertEqual(
				int(row.requires_receipt or 0),
				spec["requires_receipt"],
				f"{spec['name']}.requires_receipt mismatch",
			)
			self.assertEqual(
				int(row.billable_by_default or 0),
				spec["billable_by_default"],
				f"{spec['name']}.billable_by_default mismatch (all defaults must be 0)",
			)
			self.assertFalse(
				row.default_expense_account,
				f"{spec['name']} must NOT ship with a hard-coded default_expense_account",
			)
			self.assertFalse(
				row.default_item,
				f"{spec['name']} must NOT ship with a hard-coded default_item",
			)

	def test_receipt_partition(self):
		"""Spot-check the exact receipt-required partition from the spec."""
		for name in RECEIPT_REQUIRED:
			self.assertEqual(
				int(frappe.db.get_value("Trip Expense Type", name, "requires_receipt") or 0),
				1,
				f"{name} should require a receipt",
			)
		for name in NON_RECEIPT:
			self.assertEqual(
				int(frappe.db.get_value("Trip Expense Type", name, "requires_receipt") or 0),
				0,
				f"{name} should NOT require a receipt",
			)

	def test_none_billable_by_default(self):
		for name in EXPECTED_NAMES:
			self.assertEqual(
				int(frappe.db.get_value("Trip Expense Type", name, "billable_by_default") or 0),
				0,
				f"{name} must default to non-billable",
			)

	def test_seeder_is_idempotent(self):
		before = frappe.db.count("Trip Expense Type", {"name": ["in", EXPECTED_NAMES]})
		install_trip_expense_types()
		install_trip_expense_types()
		after = frappe.db.count("Trip Expense Type", {"name": ["in", EXPECTED_NAMES]})
		self.assertEqual(before, after, "Re-running the seeder must not create duplicates")

	def test_seeder_preserves_user_modifications(self):
		# User flips a flag on a shipped record; re-installer must not revert.
		frappe.db.set_value("Trip Expense Type", "Fuel", "billable_by_default", 1)
		install_trip_expense_types()
		self.assertEqual(
			int(frappe.db.get_value("Trip Expense Type", "Fuel", "billable_by_default") or 0),
			1,
			"Seeder overwrote a user-modified flag",
		)
		frappe.db.set_value("Trip Expense Type", "Fuel", "billable_by_default", 0)

	def test_user_created_types_are_preserved(self):
		user_type = "Test-User-Custom-Expense-Type"
		if not frappe.db.exists("Trip Expense Type", user_type):
			frappe.get_doc(
				{
					"doctype": "Trip Expense Type",
					"expense_type_name": user_type,
					"is_active": 1,
					"requires_receipt": 0,
					"billable_by_default": 1,
				}
			).insert(ignore_permissions=True)
		install_trip_expense_types()
		self.assertTrue(frappe.db.exists("Trip Expense Type", user_type))
		self.assertEqual(
			int(frappe.db.get_value("Trip Expense Type", user_type, "billable_by_default") or 0),
			1,
		)
		frappe.delete_doc("Trip Expense Type", user_type)


class TestTripExpenseReceiptPolicy(unittest.TestCase):
	"""before_submit blocks submission of a receipt-required type without a receipt.
	Draft save remains allowed."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()
		cls.company = frappe.get_all("Company", pluck="name")[0]
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		abbr = frappe.get_cached_value("Company", cls.company, "abbr")
		cls.cash_account = f"Cash - {abbr}"
		# Reuse the existing test expense account created in earlier smoke runs
		# if present; otherwise fall back to any expense leaf.
		acc = frappe.db.get_value(
			"Account",
			{"company": cls.company, "root_type": "Expense", "is_group": 0},
			"name",
		)
		cls.expense_account = acc
		cls.trip = _ensure_open_test_trip(cls.company, cls.currency)

	def _new_expense(self, expense_type):
		return frappe.get_doc(
			{
				"doctype": "Trip Expense",
				"trip": self.trip,
				"expense_date": today(),
				"expense_type": expense_type,
				"description": f"Test expense {expense_type}",
				"amount": 1000,
				"expense_account": self.expense_account,
				"payment_mode": "Company Cash/Bank",
				"cash_bank_account": self.cash_account,
			}
		)

	def test_receipt_required_type_saves_as_draft_without_receipt(self):
		"""Fuel requires a receipt for submission — draft save must still work."""
		doc = self._new_expense("Fuel")
		doc.insert()  # draft save
		self.assertEqual(doc.docstatus, 0)
		doc.delete()

	def test_receipt_required_type_cannot_submit_without_receipt(self):
		doc = self._new_expense("Fuel")
		doc.insert()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.submit()
		self.assertIn("receipt is required", str(ctx.exception).lower())
		self.assertIn("Fuel", str(ctx.exception))
		doc.delete()

	def test_receipt_required_type_submits_with_receipt(self):
		doc = self._new_expense("Fuel")
		# fake attachment reference — anything truthy satisfies the check
		doc.receipt = "/files/test-receipt.pdf"
		doc.insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		doc.cancel()

	def test_non_receipt_type_submits_without_attachment(self):
		"""Driver Food and Driver Allowance don't require a receipt."""
		doc = self._new_expense("Driver Food")
		doc.insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		doc.cancel()


class TestTripSettlementNoDoubleCount(unittest.TestCase):
	"""Planned driver_allowance on Transport Trip is display-only. Actual
	allowance goes through a Trip Expense with type 'Driver Allowance'.
	total_cost must equal vehicle_hire + trip expenses only — the planned
	amount must NOT be added on top."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()
		cls.company = frappe.get_all("Company", pluck="name")[0]
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		abbr = frappe.get_cached_value("Company", cls.company, "abbr")
		cls.cash_account = f"Cash - {abbr}"
		cls.expense_account = frappe.db.get_value(
			"Account",
			{"company": cls.company, "root_type": "Expense", "is_group": 0},
			"name",
		)

	def test_planned_and_actual_driver_allowance_are_not_double_counted(self):
		# Fresh trip with planned driver_allowance = 3000 and vehicle hire = 50000
		trip = _ensure_open_test_trip(
			self.company,
			self.currency,
			plate="TEST-DBLCNT-01",
			driver_allowance=3000,
			agreed_vehicle_hire=50000,
		)

		# Record an ACTUAL Driver Allowance expense of 3000.
		exp = frappe.get_doc(
			{
				"doctype": "Trip Expense",
				"trip": trip,
				"expense_date": today(),
				"expense_type": "Driver Allowance",
				"description": "Actual allowance paid",
				"amount": 3000,
				"expense_account": self.expense_account,
				"payment_mode": "Company Cash/Bank",
				"cash_bank_account": self.cash_account,
			}
		)
		exp.insert()
		exp.submit()

		try:
			settlement = frappe.get_doc({"doctype": "Trip Settlement", "trip": trip})
			settlement.insert()
			try:
				# Assertion: total_cost = vehicle_hire + total_expenses, and
				# total_expenses is the actual 3000 (planned 3000 must NOT be
				# added again on top).
				self.assertEqual(
					settlement.vehicle_hire,
					50000,
					"vehicle_hire should reflect Trip.agreed_vehicle_hire",
				)
				self.assertEqual(
					settlement.driver_allowance,
					3000,
					"driver_allowance on settlement mirrors planned value from Trip (display only)",
				)
				self.assertEqual(
					settlement.total_expenses,
					3000,
					"total_expenses should be the sum of actual Trip Expenses",
				)
				self.assertEqual(
					settlement.total_cost,
					53000,
					"total_cost must be vehicle_hire + actual expenses only "
					"(planned driver_allowance is NOT added — else double count)",
				)
			finally:
				settlement.delete()
		finally:
			# Cancel just the expense — the trip is left as-is because it now
			# has posted GL Entries via the trip dimension and cancelling a
			# trip that already has GL is intentionally blocked. The test
			# helper creates a fresh submitted trip on every run, so leftover
			# test trips do not affect subsequent runs.
			exp.cancel()


# --- helpers -----------------------------------------------------------------


def _ensure_open_test_trip(
	company,
	currency,
	plate="TEST-TRIP-EXP-TYPES",
	driver_allowance=0,
	agreed_vehicle_hire=0,
):
	# Ensure a vehicle exists for this plate.
	if not frappe.db.exists("Vehicle", plate):
		frappe.get_doc(
			{
				"doctype": "Vehicle",
				"license_plate": plate,
				"make": "Test",
				"model": "T1",
				"last_odometer": 0,
				"acquisition_date": "2024-01-01",
				"fuel_type": "Diesel",
				"uom": "Litre",
				"ownership_type": "Company Owned",
				"payload_capacity": 10000,
			}
		).insert(ignore_permissions=True)

	# Always insert a fresh submitted trip so tests are order-independent.
	trip = frappe.get_doc(
		{
			"doctype": "Transport Trip",
			"company": company,
			"vehicle": plate,
			"trip_date": today(),
			"currency": currency,
			"driver_allowance": driver_allowance,
			"agreed_vehicle_hire": agreed_vehicle_hire,
		}
	)
	trip.insert()
	trip.submit()
	return trip.name
