"""Stage 2 — three months of transport operations.

Builds the full lifecycle for each trip:

	Transport Order -> Transport Trip -> Bilty -> Trip Advance / Trip Expense
	-> Proof of Delivery -> Sales Invoice -> (market vehicle: Purchase Invoice)
	-> Trip Settlement -> Driver Trip Earning

The last few trips are deliberately left mid-pipeline so a live demo has
in-transit, delivered-unbilled and unsettled work to show.
"""

from __future__ import annotations

import random

import frappe
from frappe.utils import add_days, date_diff, flt, getdate

from goods_transport.demo import data as D
from goods_transport.demo.seed_masters import COMPANY, log

SEED = 20260830
START_DATE = "2026-06-01"
DEMO_TODAY = "2026-08-30"
TRIP_COUNT = 95  # the Aug-27 cut-off, not this number, ends the run

#: PKR of diesel per km, by vehicle class (HSD ~PKR 280/litre in 2026).
FUEL_RATE_PER_KM = {
	"22-Wheeler Trailer": 95,
	"18-Wheeler Trailer": 88,
	"40ft Flatbed Trailer": 84,
	"10-Wheeler Truck": 66,
	"6-Wheeler Truck": 48,
	"Mazda Truck": 34,
}

EXPENSE_ACCOUNTS = {
	"Fuel": ("Fuel & Lubricants", "Direct Expenses"),
	"Driver Food": ("Driver Allowances", "Direct Expenses"),
	"Tyre Repair": ("Vehicle Repair & Maintenance", "Direct Expenses"),
	"Vehicle Repair": ("Vehicle Repair & Maintenance", "Direct Expenses"),
	"Traffic Challan": ("Other Trip Expenses", "Indirect Expenses"),
	"Driver Allowance": ("Driver Allowances", "Direct Expenses"),
	"Other Trip Expense": ("Other Trip Expenses", "Indirect Expenses"),
}


_RECEIPT_CACHE = {}


def demo_receipt_url() -> str:
	"""A placeholder receipt so Trip Expense Types that require one can submit.

	Trip Expense refuses to submit Fuel / Repair / Challan without an
	attachment — a real feature, so the demo satisfies it rather than
	switching it off.
	"""
	if _RECEIPT_CACHE.get("url"):
		return _RECEIPT_CACHE["url"]

	file_name = "demo-trip-expense-receipt.txt"
	existing = frappe.db.get_value("File", {"file_name": file_name}, "file_url")
	if existing:
		_RECEIPT_CACHE["url"] = existing
		return existing

	doc = frappe.get_doc({
		"doctype": "File",
		"file_name": file_name,
		"is_private": 0,
		"content": (
			"DEMO RECEIPT\n"
			"Techs Arena Goods Transport\n"
			"Placeholder scan for demo trip expenses.\n"
		),
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	_RECEIPT_CACHE["url"] = doc.file_url
	return doc.file_url


def _abbr():
	return frappe.get_cached_value("Company", COMPANY, "abbr")


def ensure_expense_accounts():
	"""Give each Trip Expense Type a real P&L account to post against."""
	abbr = _abbr()
	for expense_type, (account_name, parent_name) in EXPENSE_ACCOUNTS.items():
		full = f"{account_name} - {abbr}"
		if not frappe.db.exists("Account", full):
			parent = frappe.db.get_value(
				"Account", {"company": COMPANY, "account_name": parent_name, "is_group": 1}, "name"
			)
			if not parent:
				continue
			acc = frappe.new_doc("Account")
			acc.account_name = account_name
			acc.company = COMPANY
			acc.parent_account = parent
			acc.root_type = "Expense"
			acc.report_type = "Profit and Loss"
			acc.insert(ignore_permissions=True)
		if frappe.db.exists("Trip Expense Type", expense_type):
			frappe.db.set_value("Trip Expense Type", expense_type, "default_expense_account", full)
	log("trip expense accounts wired to expense types")


def ensure_item_defaults():
	"""Freight items post to Freight Income; Vehicle Hire to its own expense."""
	abbr = _abbr()
	income = f"Freight Income - {abbr}"
	hire_expense = f"Vehicle Hire Charges - {abbr}"
	cost_center = frappe.get_cached_value("Company", COMPANY, "cost_center")

	for item in frappe.get_all("Item", filters={"item_group": "Freight Items"}, pluck="name"):
		doc = frappe.get_doc("Item", item)
		expense = hire_expense if item == "Vehicle Hire" else None
		row = None
		for d in doc.item_defaults:
			if d.company == COMPANY:
				row = d
				break
		if not row:
			row = doc.append("item_defaults", {"company": COMPANY})
		row.income_account = income if frappe.db.exists("Account", income) else None
		row.selling_cost_center = cost_center
		row.buying_cost_center = cost_center
		if expense and frappe.db.exists("Account", expense):
			row.expense_account = expense
		doc.flags.ignore_permissions = True
		doc.save()
	log("freight item defaults set")


# ---------------------------------------------------------------- generation
def _pick_cargo(customer):
	for code, cust, desc in D.CARGO_MIX:
		if cust == customer:
			return code, desc
	return "CARGO-GENERAL", "General cargo"


def _vehicles():
	rows = []
	for plate, vtype, ownership, _make, _model, owner in D.VEHICLES:
		rows.append({"plate": plate, "type": vtype, "ownership": ownership, "owner": owner})
	return rows


def _drivers():
	company_drivers, market_drivers = [], []
	for full_name, _cell, _lic, _base, is_company in D.DRIVERS:
		name = frappe.db.get_value("Driver", {"full_name": full_name}, "name")
		(company_drivers if is_company else market_drivers).append(name)
	return company_drivers, market_drivers


def _route_rate(customer, route_name, vtype, km):
	"""Contract rate when one matches, else a per-km market rate."""
	rate = frappe.db.get_value(
		"Transport Rate Contract",
		{"customer": customer, "route": route_name, "is_active": 1},
		"rate",
	)
	if rate:
		return flt(rate)
	base = {"22-Wheeler Trailer": 235, "18-Wheeler Trailer": 205, "40ft Flatbed Trailer": 220,
		"10-Wheeler Truck": 175, "6-Wheeler Truck": 140, "Mazda Truck": 95}.get(vtype, 160)
	return round(km * base / 1000.0) * 1000


def build_trips():
	rng = random.Random(SEED)
	vehicles = _vehicles()
	company_drivers, market_drivers = _drivers()
	customers = [c[0] for c in D.CUSTOMERS]
	routes = frappe.get_all(
		"Transport Route",
		fields=["name", "origin", "destination", "distance_km", "estimated_toll"],
	)
	capacity = dict((t[0], t[1]) for t in D.VEHICLE_TYPES)

	created = {"orders": 0, "trips": 0, "bilties": 0, "pods": 0, "advances": 0,
		"expenses": 0, "invoices": 0, "purchase_invoices": 0, "settlements": 0}

	date = getdate(START_DATE)
	for i in range(TRIP_COUNT):
		date = add_days(date, rng.choice([0, 1, 1, 2]))
		if getdate(date) > getdate(DEMO_TODAY):
			break

		vehicle = vehicles[i % len(vehicles)]
		route = rng.choice(routes)
		customer = customers[i % len(customers)]
		is_market = vehicle["ownership"] != "Company Owned"
		driver = rng.choice(market_drivers) if is_market else company_drivers[i % len(company_drivers)]

		cap = capacity.get(vehicle["type"], 20000)
		weight = int(cap * rng.uniform(0.78, 0.97))
		freight = _route_rate(customer, route.name, vehicle["type"], route.distance_km)
		cargo_item, cargo_desc = _pick_cargo(customer)

		# How far a trip has progressed depends on how recent it is, so the
		# demo always opens with live work in every stage of the pipeline.
		age = date_diff(DEMO_TODAY, date)
		if age <= 2:
			stage = "in_transit"
		elif age <= 4:
			stage = "delivered"      # POD taken, not yet invoiced
		elif age <= 7:
			stage = "invoiced"       # invoiced, not settled
		else:
			stage = "settled"

		_build_one(
			created=created, rng=rng, date=date, customer=customer, route=route,
			vehicle=vehicle, driver=driver, weight=weight, freight=freight,
			cargo_item=cargo_item, cargo_desc=cargo_desc, is_market=is_market,
			stage=stage,
		)
		if i % 10 == 0:
			frappe.db.commit()

	frappe.db.commit()
	return created


def _build_one(*, created, rng, date, customer, route, vehicle, driver, weight, freight,
		cargo_item, cargo_desc, is_market, stage):
	abbr = _abbr()
	currency = "PKR"
	quantity = round(weight / 1000.0, 2)

	# --- Transport Order ---------------------------------------------------
	order = frappe.new_doc("Transport Order")
	order.company = COMPANY
	order.booking_date = date
	order.customer = customer
	order.origin = route.origin
	order.destination = route.destination
	order.expected_loading_date = date
	order.expected_delivery_date = add_days(date, 3)
	order.commodity = cargo_item
	order.description = cargo_desc
	order.quantity = quantity
	order.uom = "Kg" if frappe.db.exists("UOM", "Kg") else None
	order.weight = weight
	order.rate_basis = "Per Trip"
	order.rate = freight
	order.currency = currency
	order.pod_required = 1
	order.insert(ignore_permissions=True)
	order.submit()
	created["orders"] += 1

	# --- Transport Trip ----------------------------------------------------
	trip = frappe.new_doc("Transport Trip")
	trip.company = COMPANY
	trip.trip_date = date
	trip.vehicle = vehicle["plate"]
	trip.driver = driver
	trip.route = route.name
	trip.origin = route.origin
	trip.destination = route.destination
	trip.planned_distance = route.distance_km
	trip.actual_distance = route.distance_km + rng.randint(-15, 40)
	trip.currency = currency
	trip.freight_item = "Freight"
	trip.reporting_time = f"{date} 07:30:00"
	trip.loading_time = f"{date} 10:00:00"
	trip.departure_time = f"{date} 14:00:00"
	if is_market:
		# Market vehicle: we hire it and keep the margin.
		trip.transporter = vehicle["owner"]
		trip.vehicle_owner = vehicle["owner"]
		trip.agreed_vehicle_hire = round(freight * rng.uniform(0.72, 0.82) / 1000) * 1000
	else:
		trip.driver_allowance = rng.choice([3000, 4000, 5000])
	trip.insert(ignore_permissions=True)
	trip.submit()
	created["trips"] += 1

	# --- Bilty -------------------------------------------------------------
	bilty = frappe.new_doc("Bilty")
	bilty.company = COMPANY
	bilty.bilty_date = date
	bilty.customer = customer
	bilty.transport_order = order.name
	bilty.transport_trip = trip.name
	bilty.origin = route.origin
	bilty.destination = route.destination
	bilty.vehicle = vehicle["plate"]
	bilty.driver = driver
	bilty.transporter = trip.transporter
	bilty.currency = currency
	bilty.consignor = customer
	bilty.consignee = f"{customer} — {route.destination} depot"
	bilty.customer_challan_number = f"CH-{rng.randint(10000, 99999)}"
	bilty.freight_item = "Freight"
	bilty.rate_basis = "Per Trip"
	bilty.rate = freight
	bilty.freight_quantity = 1
	bilty.pod_required = 1
	bilty.append("items", {
		"item": cargo_item,
		"description": cargo_desc,
		"quantity": quantity,
		"uom": "Kg" if frappe.db.exists("UOM", "Kg") else None,
		"packages": rng.randint(80, 600),
		"gross_weight": weight,
		"net_weight": weight - rng.randint(50, 400),
	})
	if rng.random() < 0.45:
		bilty.append("charges", {
			"item": "Loading", "description": "Loading labour at origin",
			"quantity": 1, "rate": rng.choice([6000, 8000, 10000]),
			"billable_to_customer": 1,
		})
	if rng.random() < 0.3:
		bilty.append("charges", {
			"item": "Detention", "description": "Detention at unloading point",
			"quantity": 1, "rate": rng.choice([5000, 7500, 12000]),
			"billable_to_customer": 1,
		})
	bilty.insert(ignore_permissions=True)
	bilty.submit()
	created["bilties"] += 1

	from goods_transport.goods_transport.doctype.transport_trip.transport_trip import advance_status

	advance_status(trip.name, "Loaded")
	advance_status(trip.name, "In Transit")

	# --- Trip Advance + Trip Expenses --------------------------------------
	advance_name = None
	if not is_market and rng.random() < 0.85:
		adv = frappe.new_doc("Trip Advance")
		adv.company = COMPANY
		adv.advance_date = date
		adv.trip = trip.name
		adv.currency = currency
		adv.recipient_type = "Driver"
		adv.driver = driver
		adv.amount = rng.choice([15000, 18000, 20000, 25000])
		adv.paying_account = f"Cash - {abbr}"
		adv.advance_account = f"Driver Advances - {abbr}"
		adv.remarks = "Road expenses advance"
		adv.insert(ignore_permissions=True)
		adv.submit()
		advance_name = adv.name
		created["advances"] += 1

	if stage == "in_transit":
		return

	# Expenses actually incurred on the road.
	#
	# Own fleet: we carry fuel, tolls, food, repairs — the real running cost.
	# Market vehicle: the agreed hire covers the owner's running cost, so only
	# our own incidentals land on the trip. That contrast is the point of the
	# own-fleet vs market-vehicle model.
	expense_plan = []
	if is_market:
		if rng.random() < 0.35:
			expense_plan.append(("Other Trip Expense", rng.choice([4000, 6000, 9000]), "company"))
	else:
		fuel_rate = FUEL_RATE_PER_KM.get(vehicle["type"], 60)
		expense_plan.append((
			"Fuel", round(route.distance_km * fuel_rate * rng.uniform(0.95, 1.08) / 500) * 500,
			"company",
		))
		expense_plan.append(("Other Trip Expense", flt(route.estimated_toll), "advance"))
		if rng.random() < 0.75:
			expense_plan.append(("Driver Food", rng.choice([1500, 2000, 2500, 3000]), "advance"))
		if rng.random() < 0.6:
			expense_plan.append(("Driver Allowance", flt(trip.driver_allowance), "advance"))
		if rng.random() < 0.22:
			expense_plan.append(("Tyre Repair", rng.choice([4000, 6500, 9000, 14000]), "company"))
		if rng.random() < 0.12:
			expense_plan.append(("Vehicle Repair", rng.choice([12000, 18000, 26000]), "company"))
		if rng.random() < 0.13:
			expense_plan.append(("Traffic Challan", rng.choice([2000, 3000, 5000]), "advance"))

	for expense_type, amount, funding in expense_plan:
		if not amount:
			continue
		account = frappe.db.get_value("Trip Expense Type", expense_type, "default_expense_account")
		te = frappe.new_doc("Trip Expense")
		te.company = COMPANY
		te.expense_date = add_days(date, 1)
		te.trip = trip.name
		te.currency = currency
		te.expense_type = expense_type
		te.description = (
			f"Toll and motorway charges — {route.origin} to {route.destination}"
			if expense_type == "Other Trip Expense" and funding == "advance"
			else f"{expense_type} — {route.origin} to {route.destination}"
		)
		te.amount = amount
		te.expense_account = account
		if advance_name and funding == "advance":
			te.payment_mode = "Trip Advance"
			te.trip_advance = advance_name
		else:
			te.payment_mode = "Company Cash/Bank"
			te.cash_bank_account = f"Cash - {abbr}"
		te.party_type = "Driver"
		te.driver = driver
		if frappe.db.get_value("Trip Expense Type", expense_type, "requires_receipt"):
			te.receipt = demo_receipt_url()
		te.insert(ignore_permissions=True)
		te.submit()
		created["expenses"] += 1

	# --- Delivery ----------------------------------------------------------
	delivery_date = add_days(date, 2 if route.distance_km < 600 else 3)
	advance_status(trip.name, "Arrived")
	advance_status(trip.name, "Unloading")

	pod = frappe.new_doc("Proof of Delivery")
	pod.bilty = bilty.name
	pod.delivery_date = delivery_date
	pod.delivery_time = "11:20:00"
	pod.delivered_quantity = quantity
	pod.receiver_name = f"{route.destination} Store Incharge"
	pod.receiver_contact = f"03{rng.randint(10, 49)}-{rng.randint(1000000, 9999999)}"
	pod.insert(ignore_permissions=True)
	pod.submit()
	created["pods"] += 1

	advance_status(trip.name, "Delivered")

	if stage == "delivered":
		return

	# --- Customer invoice ---------------------------------------------------
	from goods_transport.goods_transport.services.billing import create_sales_invoice_from_bilties

	si_name = create_sales_invoice_from_bilties([bilty.name])
	si = frappe.get_doc("Sales Invoice", si_name)
	si.set_posting_time = 1
	si.posting_date = delivery_date
	si.due_date = add_days(delivery_date, 30)
	si.save(ignore_permissions=True)
	si.submit()
	created["invoices"] += 1

	# --- Market vehicle hire bill ------------------------------------------
	if is_market:
		from goods_transport.goods_transport.services.operations import (
			create_transporter_purchase_invoice,
		)

		pi_name = create_transporter_purchase_invoice(
			transport_trip=trip.name,
			hire_item="Vehicle Hire",
			expense_account=f"Vehicle Hire Charges - {abbr}",
		)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		pi.set_posting_time = 1
		pi.posting_date = delivery_date
		pi.bill_no = f"BL-{rng.randint(1000, 9999)}"
		pi.bill_date = delivery_date
		pi.save(ignore_permissions=True)
		pi.submit()
		created["purchase_invoices"] += 1

	if stage == "invoiced":
		return

	# --- Settlement ---------------------------------------------------------
	from goods_transport.goods_transport.doctype.trip_settlement.trip_settlement import (
		create_settlement_for_trip,
	)

	ts_name = create_settlement_for_trip(trip.name)
	ts = frappe.get_doc("Trip Settlement", ts_name)
	ts.settlement_date = add_days(delivery_date, 1)
	if flt(ts.advance_balance) > 0 and rng.random() < 0.75:
		# The driver hands most of the unspent balance back in cash at
		# settlement; whatever is left is recovered from the next salary by
		# the Driver Payroll Run.
		ts.cash_returned = round(flt(ts.advance_balance) * rng.uniform(0.55, 0.9) / 500) * 500
	ts.save(ignore_permissions=True)
	ts.submit()
	created["settlements"] += 1


def run():
	print("\n[2/4] Operations — orders, trips, bilties, PODs, invoices, settlements")
	ensure_expense_accounts()
	ensure_item_defaults()
	created = build_trips()
	for key, value in created.items():
		log(f"{value} {key}")
	return created
