"""Driver Payroll Run — turns completed Trips into HRMS payroll input.

The run is deliberately *not* a parallel payroll engine. It aggregates
Driver Trip Earnings for a period and pushes them into standard HRMS
`Additional Salary` records, so the regular Payroll Entry → Salary Slip →
Journal Entry path does the actual payroll, tax and accounting work.

	Driver Trip Earning (per trip)
	        |  aggregate by employee + salary component
	        v
	Additional Salary (Earning)      -> picked up by the month's Salary Slip
	Additional Salary (Deduction)    -> advance recovered from the same slip
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from goods_transport.goods_transport.services import advances as advance_service
from goods_transport.goods_transport.services import earnings as earning_service

EARNING_COMPONENT_FIELDS = (
	# (earning amount field, pay-rule component field, detail total field)
	("trip_amount", "trip_component", "trip_amount"),
	("km_amount", "km_component", "km_amount"),
	("tonnage_amount", "tonnage_component", "tonnage_amount"),
	("commission_amount", "commission_component", "commission_amount"),
)


class DriverPayrollRun(Document):
	# ------------------------------------------------------------ lifecycle
	def validate(self):
		self._validate_period()
		self._validate_rows()
		self._compute_totals()

	def before_submit(self):
		if not self.details:
			frappe.throw(_("Nothing to submit — fetch trip earnings first."))
		self._validate_payroll_prerequisites()
		# Built here, not in on_submit, so the allocation is written by the same
		# save that submits the document.
		self._build_recovery_allocation()

	def on_submit(self):
		created = self._create_additional_salaries()
		self.db_set("status", "Submitted")
		frappe.msgprint(
			_("Created {0} Additional Salary record(s). They will be picked up by the "
			  "Salary Slips covering {1}.").format(created, frappe.format(self.payroll_date, "Date")),
			indicator="green",
			alert=True,
		)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry",)
		self._cancel_additional_salaries()
		self._release_earnings()
		self.db_set("status", "Cancelled")

	# ----------------------------------------------------------- validation
	def _validate_period(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date must be on or before To Date."))
		if not self.payroll_date:
			self.payroll_date = self.to_date
		if getdate(self.payroll_date) < getdate(self.from_date):
			frappe.throw(_("Payroll Date cannot be before the period's From Date."))
		if not self.currency:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def _validate_rows(self):
		seen = set()
		for row in self.details:
			if row.driver in seen:
				frappe.throw(_("Driver {0} appears more than once.").format(row.driver))
			seen.add(row.driver)

			if not row.employee:
				row.employee = frappe.db.get_value("Driver", row.driver, "employee")
			if not row.employee:
				frappe.throw(
					_("Driver {0} is not linked to an Employee. Set the Employee field on the "
					  "Driver record — payroll cannot run without it.").format(row.driver)
				)

			row.gross_earning = (
				flt(row.trip_amount) + flt(row.km_amount)
				+ flt(row.tonnage_amount) + flt(row.commission_amount)
			)
			if flt(row.advance_recovery) < 0:
				frappe.throw(_("Advance recovery cannot be negative for {0}.").format(row.driver))
			outstanding = flt(row.outstanding_advance)
			if flt(row.advance_recovery) > outstanding + 0.005:
				frappe.throw(
					_("Recovery {0} for {1} exceeds the outstanding advance {2}.").format(
						frappe.format(row.advance_recovery, {"fieldtype": "Currency"}),
						row.driver,
						frappe.format(outstanding, {"fieldtype": "Currency"}),
					)
				)
			row.net_addition = flt(row.gross_earning) - flt(row.advance_recovery)
			row.currency = self.currency

	def _compute_totals(self):
		self.total_drivers = len(self.details)
		self.total_trips = sum(int(r.trips or 0) for r in self.details)
		self.total_earnings = sum(flt(r.gross_earning) for r in self.details)
		self.total_recovery = sum(flt(r.advance_recovery) for r in self.details)
		self.net_payable = flt(self.total_earnings) - flt(self.total_recovery)

	def _validate_payroll_prerequisites(self):
		"""Fail early and clearly instead of deep inside Additional Salary."""
		for row in self.details:
			emp = frappe.db.get_value(
				"Employee", row.employee, ["status", "date_of_joining", "employee_name"], as_dict=True
			)
			if not emp:
				frappe.throw(_("Employee {0} not found.").format(row.employee))
			if emp.status != "Active":
				frappe.throw(
					_("Employee {0} ({1}) is {2}. Only Active employees can be paid.").format(
						row.employee, emp.employee_name, emp.status
					)
				)
			if emp.date_of_joining and getdate(self.payroll_date) < getdate(emp.date_of_joining):
				frappe.throw(
					_("Payroll Date {0} is before {1}'s joining date {2}.").format(
						frappe.format(self.payroll_date, "Date"), emp.employee_name,
						frappe.format(emp.date_of_joining, "Date"),
					)
				)
			if not frappe.db.exists("Salary Structure Assignment", {"employee": row.employee}):
				frappe.throw(
					_("{0} has no Salary Structure Assignment. Assign a salary structure "
					  "before running driver payroll.").format(emp.employee_name)
				)
			if flt(row.advance_recovery) and not self._recovery_component(row):
				frappe.throw(
					_("Pay Rule for {0} does not define a Recovery Component, so the advance "
					  "cannot be deducted.").format(row.driver)
				)

	# -------------------------------------------------------------- fetching
	@frappe.whitelist()
	def fetch_earnings(self):
		"""Pull every unpaid Driver Trip Earning in the period into the table."""
		self._validate_period()
		earning_service.generate_earnings_for_period(self.company, self.from_date, self.to_date)

		rows = frappe.get_all(
			"Driver Trip Earning",
			filters={
				"company": self.company,
				"status": "Pending",
				"employee": ["is", "set"],
				"trip_date": ["between", [self.from_date, self.to_date]],
			},
			fields=["name", "driver", "employee", "pay_rule", "trip_amount", "km_amount",
				"tonnage_amount", "commission_amount", "total_earning"],
			order_by="trip_date asc",
		)

		by_driver: dict[str, dict] = {}
		for r in rows:
			d = by_driver.setdefault(r.driver, {
				"driver": r.driver, "employee": r.employee, "pay_rule": r.pay_rule,
				"trips": 0, "trip_amount": 0.0, "km_amount": 0.0,
				"tonnage_amount": 0.0, "commission_amount": 0.0,
			})
			d["trips"] += 1
			d["pay_rule"] = d["pay_rule"] or r.pay_rule
			for field in ("trip_amount", "km_amount", "tonnage_amount", "commission_amount"):
				d[field] += flt(r.get(field))

		self.set("details", [])
		for driver, data in sorted(by_driver.items()):
			row = self.append("details", data)
			row.employee = row.employee or frappe.db.get_value("Driver", driver, "employee")
			row.gross_earning = (
				flt(row.trip_amount) + flt(row.km_amount)
				+ flt(row.tonnage_amount) + flt(row.commission_amount)
			)
			outstanding, recovery = self._advance_figures(driver, row.pay_rule)
			row.outstanding_advance = outstanding
			row.advance_recovery = recovery
			row.net_addition = flt(row.gross_earning) - flt(recovery)
			row.currency = self.currency

		self._compute_totals()
		return {"drivers": len(self.details), "trips": self.total_trips}

	def _advance_figures(self, driver: str, pay_rule: str | None) -> tuple[float, float]:
		open_rows = advance_service.get_driver_outstanding_advances(
			driver, self.company, upto_date=self.to_date, exclude_run=self.name
		)
		outstanding = sum(flt(r["outstanding"]) for r in open_rows)
		if not outstanding:
			return 0.0, 0.0

		rule = frappe.get_cached_doc("Driver Pay Rule", pay_rule) if pay_rule else None
		if not rule or not rule.recover_advances:
			return outstanding, 0.0

		cap = flt(rule.max_recovery_per_month)
		recovery = min(outstanding, cap) if cap else outstanding
		return outstanding, recovery

	def _recovery_component(self, row) -> str | None:
		if not row.pay_rule:
			return None
		rule = frappe.get_cached_doc("Driver Pay Rule", row.pay_rule)
		return rule.recovery_component if rule.recover_advances else None

	# --------------------------------------------------------- posting logic
	def _period_earnings(self, driver: str) -> list[dict]:
		return frappe.get_all(
			"Driver Trip Earning",
			filters={
				"company": self.company,
				"driver": driver,
				"status": "Pending",
				"trip_date": ["between", [self.from_date, self.to_date]],
			},
			fields=["name", "pay_rule", "trip_amount", "km_amount", "tonnage_amount",
				"commission_amount"],
		)

	def _create_additional_salaries(self) -> int:
		created = 0
		self.set("recoveries", [])

		for row in self.details:
			earnings = self._period_earnings(row.driver)

			# Aggregate per Salary Component — a driver's trips in one month may
			# fall under different pay rules pointing at different components.
			by_component: dict[str, float] = {}
			for earning in earnings:
				rule = frappe.get_cached_doc("Driver Pay Rule", earning.pay_rule)
				for amount_field, component_field, _detail in EARNING_COMPONENT_FIELDS:
					amount = flt(earning.get(amount_field))
					component = rule.get(component_field)
					if amount and component:
						by_component[component] = by_component.get(component, 0.0) + amount

			for component, amount in by_component.items():
				self._make_additional_salary(row, component, amount, "Earning")
				created += 1

			# Mark the earnings paid.
			for earning in earnings:
				frappe.db.set_value(
					"Driver Trip Earning", earning.name,
					{"status": "Processed", "payroll_run": self.name},
					update_modified=False,
				)

			# Advance recovery — the FIFO allocation was built in before_submit.
			recovery = flt(row.advance_recovery)
			if recovery:
				self._make_additional_salary(
					row, self._recovery_component(row), recovery, "Deduction"
				)
				created += 1

		self._close_recovered_advances()
		return created

	def _build_recovery_allocation(self):
		"""Spread each driver's recovery across their open advances, oldest first."""
		self.set("recoveries", [])
		for row in self.details:
			remaining = flt(row.advance_recovery)
			if not remaining:
				continue
			open_rows = advance_service.get_driver_outstanding_advances(
				row.driver, self.company, upto_date=self.to_date, exclude_run=self.name
			)
			for adv in open_rows:
				if remaining <= 0.005:
					break
				take = min(flt(adv["outstanding"]), remaining)
				self.append("recoveries", {
					"driver": row.driver,
					"employee": row.employee,
					"trip_advance": adv["name"],
					"trip": adv["trip"],
					"advance_amount": adv["amount"],
					"previously_settled": adv["settled"],
					"recovery_amount": take,
					"currency": self.currency,
				})
				remaining -= take

			if remaining > 0.005:
				frappe.throw(
					_("Could not allocate {0} of advance recovery for {1} — the outstanding "
					  "advances have changed. Re-fetch the run and try again.").format(
						frappe.format(remaining, {"fieldtype": "Currency"}), row.driver)
				)

	def _close_recovered_advances(self):
		"""Mark advances fully settled by this run as Cleared."""
		for adv in {r.trip_advance for r in self.recoveries}:
			if advance_service.get_outstanding(adv) <= 0.005:
				frappe.db.set_value("Trip Advance", adv, "status", "Cleared",
					update_modified=False)

	def _make_additional_salary(self, row, component: str, amount: float, ctype: str):
		doc = frappe.new_doc("Additional Salary")
		doc.employee = row.employee
		doc.company = self.company
		doc.salary_component = component
		doc.amount = flt(amount)
		doc.payroll_date = self.payroll_date
		doc.currency = self.currency
		doc.overwrite_salary_structure_amount = 0
		doc.type = ctype
		doc.ref_doctype = self.doctype
		doc.ref_docname = self.name
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		return doc.name

	def _cancel_additional_salaries(self):
		names = frappe.get_all(
			"Additional Salary",
			filters={"ref_doctype": self.doctype, "ref_docname": self.name, "docstatus": 1},
			pluck="name",
		)
		for name in names:
			doc = frappe.get_doc("Additional Salary", name)
			slip = frappe.db.sql(
				"""SELECT sd.parent FROM `tabSalary Detail` sd
				INNER JOIN `tabSalary Slip` ss ON ss.name = sd.parent
				WHERE sd.additional_salary = %s AND ss.docstatus = 1 LIMIT 1""",
				(name,),
			)
			if slip:
				frappe.throw(
					_("Additional Salary {0} is already paid through Salary Slip {1}. "
					  "Cancel the Salary Slip before cancelling this run.").format(name, slip[0][0])
				)
			doc.flags.ignore_permissions = True
			doc.cancel()

	def _release_earnings(self):
		for name in frappe.get_all(
			"Driver Trip Earning", filters={"payroll_run": self.name}, pluck="name"
		):
			frappe.db.set_value(
				"Driver Trip Earning", name,
				{"status": "Pending", "payroll_run": None},
				update_modified=False,
			)
		for row in self.recoveries:
			if frappe.db.get_value("Trip Advance", row.trip_advance, "status") == "Cleared":
				frappe.db.set_value("Trip Advance", row.trip_advance, "status", "Paid",
					update_modified=False)


@frappe.whitelist()
def create_run_for_month(company: str, from_date: str, to_date: str, payroll_date: str | None = None) -> str:
	"""Scripted entry point: build a draft run for a period and fill it."""
	run = frappe.new_doc("Driver Payroll Run")
	run.company = company
	run.from_date = from_date
	run.to_date = to_date
	run.payroll_date = payroll_date or to_date
	run.fetch_earnings()
	run.insert()
	return run.name
