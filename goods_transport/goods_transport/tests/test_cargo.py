"""Cargo Items separation — seeded items, filters, validation.

Run with:
    bench --site <site> run-tests --module goods_transport.goods_transport.tests.test_cargo
"""

import unittest

import frappe

from goods_transport.goods_transport.services.cargo import (
	CARGO_ROOT_ITEM_GROUP,
	get_cargo_item_groups,
	is_cargo_item,
)
from goods_transport.setup.install_masters import (
	CARGO_ITEMS,
	install_cargo_item_group_and_items,
	install_transport_masters,
)


CARGO_SAMPLE = "CARGO-STEEL-COIL"
CARGO_ALT = "CARGO-CONTAINER"
FREIGHT_ITEM = "Freight"
LOADING_ITEM = "Loading"


class TestCargoSetup(unittest.TestCase):
	"""Idempotent seeding and correctness of seeded records."""

	@classmethod
	def setUpClass(cls):
		# Ensure freight-side + cargo-side masters exist. install is idempotent.
		install_transport_masters()

	def test_cargo_item_group_exists(self):
		self.assertTrue(frappe.db.exists("Item Group", CARGO_ROOT_ITEM_GROUP))
		self.assertEqual(
			frappe.db.get_value("Item Group", CARGO_ROOT_ITEM_GROUP, "is_group"),
			1,
		)

	def test_all_seeded_cargo_items_present(self):
		missing = [s["code"] for s in CARGO_ITEMS if not frappe.db.exists("Item", s["code"])]
		self.assertFalse(missing, f"Missing cargo items: {missing}")

	def test_cargo_items_are_non_transactional(self):
		for spec in CARGO_ITEMS:
			d = frappe.db.get_value(
				"Item",
				spec["code"],
				["item_group", "is_stock_item", "is_sales_item", "is_purchase_item", "stock_uom", "disabled"],
				as_dict=True,
			)
			self.assertEqual(d.item_group, CARGO_ROOT_ITEM_GROUP, spec["code"])
			self.assertEqual(int(d.is_stock_item or 0), 0, f"{spec['code']} should be non-stock")
			self.assertEqual(int(d.is_sales_item or 0), 0, f"{spec['code']} should be non-sales")
			self.assertEqual(int(d.is_purchase_item or 0), 0, f"{spec['code']} should be non-purchase")
			self.assertEqual(int(d.disabled or 0), 0, f"{spec['code']} should not be disabled")
			self.assertEqual(d.stock_uom, spec["uom"], f"{spec['code']} UOM mismatch")

	def test_seeder_is_idempotent(self):
		before = frappe.db.count("Item", {"item_group": CARGO_ROOT_ITEM_GROUP})
		install_cargo_item_group_and_items()
		install_cargo_item_group_and_items()
		after = frappe.db.count("Item", {"item_group": CARGO_ROOT_ITEM_GROUP})
		self.assertEqual(before, after, "Re-running the seeder must not create duplicates")

	def test_seeder_preserves_user_modifications(self):
		# User renames the shipped item — installer must not overwrite it.
		frappe.db.set_value("Item", CARGO_SAMPLE, "item_name", "Custom Steel Coil Name")
		install_cargo_item_group_and_items()
		self.assertEqual(
			frappe.db.get_value("Item", CARGO_SAMPLE, "item_name"),
			"Custom Steel Coil Name",
		)
		# Restore for other tests.
		frappe.db.set_value("Item", CARGO_SAMPLE, "item_name", "Steel Coil")


class TestCargoClassification(unittest.TestCase):
	"""is_cargo_item / get_cargo_item_groups semantics."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()

	def test_cargo_item_group_lookup_includes_root(self):
		groups = get_cargo_item_groups()
		self.assertIn(CARGO_ROOT_ITEM_GROUP, groups)

	def test_seeded_cargo_item_classifies_as_cargo(self):
		self.assertTrue(is_cargo_item(CARGO_SAMPLE))
		self.assertTrue(is_cargo_item(CARGO_ALT))

	def test_freight_service_item_is_not_cargo(self):
		self.assertFalse(is_cargo_item(FREIGHT_ITEM))
		self.assertFalse(is_cargo_item(LOADING_ITEM))

	def test_unknown_item_is_not_cargo(self):
		self.assertFalse(is_cargo_item("__does-not-exist__"))
		self.assertFalse(is_cargo_item(None))

	def test_descendant_group_items_are_cargo(self):
		"""If a user adds a subgroup under Cargo Items and drops an Item in it,
		that Item still counts as cargo."""
		subgroup = "Cargo Items :: Test Perishable"
		if not frappe.db.exists("Item Group", subgroup):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": subgroup,
					"parent_item_group": CARGO_ROOT_ITEM_GROUP,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		# get_descendants relies on the nested set; rebuild if stale.
		frappe.db.commit()
		item_code = "CARGO-TEST-FISH"
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": "Test Fish",
					"item_group": subgroup,
					"stock_uom": "Kg",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
		self.assertTrue(is_cargo_item(item_code), "Item in descendant group must classify as cargo")


class TestTransportOrderCargoValidation(unittest.TestCase):
	"""Transport Order.commodity must be a Cargo Item."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()
		cls.company = frappe.get_all("Company", pluck="name")[0]
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		cls.customer = _ensure_test_customer()
		cls.origin = _ensure_test_location("Test Origin A")
		cls.destination = _ensure_test_location("Test Destination B")

	def _new_order(self, commodity):
		return frappe.get_doc(
			{
				"doctype": "Transport Order",
				"company": self.company,
				"customer": self.customer,
				"origin": self.origin,
				"destination": self.destination,
				"currency": self.currency,
				"commodity": commodity,
				"quantity": 10,
				"uom": "Kg",
				"rate_basis": "Per Ton",
				"rate": 5000,
			}
		)

	def test_accepts_cargo_item(self):
		doc = self._new_order(CARGO_SAMPLE)
		doc.insert()
		self.assertEqual(doc.commodity, CARGO_SAMPLE)
		doc.delete()

	def test_rejects_freight_item(self):
		doc = self._new_order(FREIGHT_ITEM)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert()
		self.assertIn("not a Cargo Item", str(ctx.exception))

	def test_accepts_empty_commodity(self):
		"""commodity is optional — an unset field must not trip the validator."""
		doc = self._new_order(None)
		doc.insert()
		doc.delete()


class TestBiltyCargoValidation(unittest.TestCase):
	"""Bilty items[*].item must be a Cargo Item."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()
		cls.company = frappe.get_all("Company", pluck="name")[0]
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		cls.customer = _ensure_test_customer()
		cls.origin = _ensure_test_location("Test Origin A")
		cls.destination = _ensure_test_location("Test Destination B")

	def _new_bilty(self, item_code):
		bilty = frappe.get_doc(
			{
				"doctype": "Bilty",
				"company": self.company,
				"customer": self.customer,
				"origin": self.origin,
				"destination": self.destination,
				"currency": self.currency,
				"freight_item": FREIGHT_ITEM,
				"rate_basis": "Per Ton",
				"rate": 5000,
				"freight_quantity": 1,
			}
		)
		bilty.append("items", {"item": item_code, "quantity": 1, "uom": "Kg", "gross_weight": 1000})
		return bilty

	def test_accepts_cargo_item_row(self):
		bilty = self._new_bilty(CARGO_SAMPLE)
		bilty.insert()
		self.assertEqual(bilty.items[0].item, CARGO_SAMPLE)
		bilty.delete()

	def test_rejects_freight_item_in_cargo_row(self):
		bilty = self._new_bilty(FREIGHT_ITEM)
		with self.assertRaises(frappe.ValidationError) as ctx:
			bilty.insert()
		self.assertIn("not a Cargo Item", str(ctx.exception))

	def test_rejects_loading_item_in_cargo_row(self):
		bilty = self._new_bilty(LOADING_ITEM)
		with self.assertRaises(frappe.ValidationError) as ctx:
			bilty.insert()
		self.assertIn("not a Cargo Item", str(ctx.exception))

	def test_error_message_identifies_row(self):
		bilty = self._new_bilty(CARGO_SAMPLE)
		bilty.append("items", {"item": FREIGHT_ITEM, "quantity": 1, "uom": "Kg", "gross_weight": 500})
		with self.assertRaises(frappe.ValidationError) as ctx:
			bilty.insert()
		msg = str(ctx.exception)
		# Row 2 is the bad one — the message must name it and the bad item.
		self.assertIn("Row 2", msg)
		self.assertIn(FREIGHT_ITEM, msg)


class TestBillingStillWorks(unittest.TestCase):
	"""End-to-end: Bilty → Sales Invoice consolidation still functions,
	and the SI is built from FREIGHT items — never from Cargo Items."""

	@classmethod
	def setUpClass(cls):
		install_transport_masters()
		cls.company = frappe.get_all("Company", pluck="name")[0]
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		cls.customer = _ensure_test_customer()
		cls.origin = _ensure_test_location("Test Origin A")
		cls.destination = _ensure_test_location("Test Destination B")

	def test_bilty_to_sales_invoice_uses_freight_item_not_cargo(self):
		from goods_transport.goods_transport.services.billing import (
			create_sales_invoice_from_bilties,
		)

		bilty = frappe.get_doc(
			{
				"doctype": "Bilty",
				"company": self.company,
				"customer": self.customer,
				"origin": self.origin,
				"destination": self.destination,
				"currency": self.currency,
				"freight_item": FREIGHT_ITEM,
				"rate_basis": "Per Ton",
				"rate": 7000,
				"freight_quantity": 3,
			}
		)
		bilty.append(
			"items",
			{"item": CARGO_SAMPLE, "quantity": 3, "uom": "Kg", "gross_weight": 3000},
		)
		bilty.append(
			"charges",
			{"item": LOADING_ITEM, "quantity": 1, "rate": 1000, "billable_to_customer": 1},
		)
		bilty.insert()
		bilty.submit()
		try:
			si_name = create_sales_invoice_from_bilties([bilty.name])
			si = frappe.get_doc("Sales Invoice", si_name)
			item_codes = [row.item_code for row in si.items]
			self.assertIn(FREIGHT_ITEM, item_codes)
			self.assertIn(LOADING_ITEM, item_codes)
			# Cargo Item must never appear as an invoice line.
			self.assertNotIn(CARGO_SAMPLE, item_codes)
		finally:
			# Clean up: cancel the SI (if inserted), then unlink and cancel the bilty.
			if frappe.db.exists("Sales Invoice", si_name):
				try:
					si.cancel()
				except Exception:
					pass
			frappe.db.set_value("Bilty", bilty.name, "sales_invoice", None)
			bilty.reload()
			try:
				bilty.cancel()
			except Exception:
				pass


# --- helpers ---------------------------------------------------------------


def _ensure_test_customer():
	name = "Test Cargo Customer"
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Company",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
				or "All Customer Groups",
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")
				or "All Territories",
			}
		).insert(ignore_permissions=True)
	return name


def _ensure_test_location(name):
	if not frappe.db.exists("Transport Location", name):
		frappe.get_doc(
			{
				"doctype": "Transport Location",
				"location_name": name,
				"location_type": "Warehouse",
			}
		).insert(ignore_permissions=True)
	return name
