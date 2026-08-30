"""Stage 3b — customer collections, so receivables and ageing look real.

Invoices older than the credit window are mostly paid; recent ones are left
open. Payments land in the bank account, giving the demo a believable cash
position and an Accounts Receivable ageing with something in every bucket.
"""

from __future__ import annotations

import random

import frappe
from frappe.utils import add_days, flt, getdate

from goods_transport.demo.seed_masters import COMPANY, log

DEMO_TODAY = "2026-08-30"
SEED = 90210


def run():
	print("\n[3b/4] Customer collections")
	rng = random.Random(SEED)
	company = frappe.get_doc("Company", COMPANY)
	bank = company.default_bank_account or company.default_cash_account

	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "posting_date", "customer", "grand_total", "outstanding_amount"],
		order_by="posting_date",
	)

	paid = partial = 0
	for inv in invoices:
		age = (getdate(DEMO_TODAY) - getdate(inv.posting_date)).days
		roll = rng.random()
		if age > 45:
			share = 1.0 if roll < 0.9 else 0.5
		elif age > 25:
			share = 1.0 if roll < 0.6 else (0.5 if roll < 0.8 else 0)
		elif age > 12:
			share = 1.0 if roll < 0.25 else 0
		else:
			share = 0
		if not share:
			continue

		amount = round(flt(inv.outstanding_amount) * share / 100) * 100
		if amount <= 0:
			continue

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.company = COMPANY
		pe.posting_date = add_days(inv.posting_date, rng.randint(10, min(max(age, 11), 55)))
		pe.mode_of_payment = "Bank Draft" if frappe.db.exists("Mode of Payment", "Bank Draft") else None
		pe.party_type = "Customer"
		pe.party = inv.customer
		pe.paid_from = company.default_receivable_account
		pe.paid_to = bank
		pe.paid_amount = amount
		pe.received_amount = amount
		pe.reference_no = f"CHQ-{rng.randint(100000, 999999)}"
		pe.reference_date = pe.posting_date
		pe.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": inv.name,
			"total_amount": inv.grand_total,
			"outstanding_amount": inv.outstanding_amount,
			"allocated_amount": amount,
		})
		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
		if share == 1.0:
			paid += 1
		else:
			partial += 1

	frappe.db.commit()
	total_out = frappe.db.sql(
		"SELECT COALESCE(SUM(outstanding_amount), 0) FROM `tabSales Invoice` WHERE docstatus = 1"
	)[0][0]
	log(f"{paid} invoices settled in full, {partial} part-paid; receivable now {flt(total_out):,.0f}")
