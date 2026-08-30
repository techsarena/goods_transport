"""Stage 3 — run driver payroll for the completed months.

June and July are processed end to end (Driver Payroll Run → Payroll Entry →
Salary Slips). August is deliberately left untouched: its trip earnings sit
Pending so a live demo can fetch and pay them on screen.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, get_last_day, getdate

from goods_transport.demo.seed_masters import COMPANY, log

MONTHS = [("2026-06-01", "2026-06-30"), ("2026-07-01", "2026-07-31")]


def create_driver_payroll_run(from_date, to_date):
	existing = frappe.db.get_value(
		"Driver Payroll Run",
		{"company": COMPANY, "from_date": from_date, "to_date": to_date, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing

	run = frappe.new_doc("Driver Payroll Run")
	run.company = COMPANY
	run.from_date = from_date
	run.to_date = to_date
	run.payroll_date = to_date
	run.remarks = "Monthly trip earnings and advance recovery."
	run.fetch_earnings()
	if not run.details:
		return None
	run.flags.ignore_permissions = True
	run.insert()
	run.submit()
	log(
		f"Driver Payroll Run {run.name}: {run.total_drivers} drivers, {run.total_trips} trips, "
		f"earnings {flt(run.total_earnings):,.0f}, recovery {flt(run.total_recovery):,.0f}"
	)
	return run.name


def run_payroll_entry(from_date, to_date):
	existing = frappe.db.get_value(
		"Payroll Entry",
		{"company": COMPANY, "start_date": from_date, "end_date": to_date, "docstatus": ["<", 2]},
		"name",
	)
	if existing:
		return existing

	company = frappe.get_doc("Company", COMPANY)
	pe = frappe.new_doc("Payroll Entry")
	pe.company = COMPANY
	pe.posting_date = to_date
	pe.payroll_frequency = "Monthly"
	pe.start_date = from_date
	pe.end_date = to_date
	pe.currency = company.default_currency
	pe.exchange_rate = 1
	pe.payroll_payable_account = company.default_payroll_payable_account
	pe.payment_account = company.default_bank_account or company.default_cash_account
	pe.fill_employee_details()
	if not pe.employees:
		log(f"no employees with salary structures for {from_date} — skipped")
		return None
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()

	# HRMS's own submitter also posts the accrual Journal Entry (Dr each salary
	# component's account / Cr Payroll Payable), which is what puts driver pay in
	# the P&L and credits the advance recovery back to Driver Advances.
	pe.reload()
	pe.submit_salary_slips()

	total = frappe.db.sql(
		"""SELECT COALESCE(SUM(net_pay), 0) FROM `tabSalary Slip`
		WHERE payroll_entry = %s AND docstatus = 1""",
		(pe.name,),
	)[0][0]
	log(f"Payroll Entry {pe.name}: {len(pe.employees)} employees, net pay {flt(total):,.0f}")
	return pe.name


def run():
	print("\n[3/4] Payroll — June and July processed, August left for the live demo")
	for from_date, to_date in MONTHS:
		create_driver_payroll_run(from_date, to_date)
		run_payroll_entry(from_date, to_date)
		frappe.db.commit()

	pending = frappe.db.sql(
		"""SELECT COUNT(*), COALESCE(SUM(total_earning), 0)
		FROM `tabDriver Trip Earning` WHERE status = 'Pending'"""
	)[0]
	log(f"{pending[0]} trip earnings still Pending (PKR {flt(pending[1]):,.0f}) — August, ready to demo")
