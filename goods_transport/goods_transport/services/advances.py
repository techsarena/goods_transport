"""Trip Advance outstanding-balance arithmetic.

A Trip Advance is cash issued to a driver. It is settled in three ways:

1. **Consumed** — a submitted Trip Expense with payment_mode='Trip Advance'
   pointing at the advance records how the driver actually spent it.
2. **Returned in cash** — Trip Settlement.cash_returned for the advance's Trip.
3. **Recovered from salary** — a submitted Driver Payroll Run allocates a
   recovery against the advance (this app).

outstanding = amount - consumed - cash_returned_allocated - recovered

Cash returned is recorded per Trip, not per advance, so it is allocated across
that Trip's advances oldest-first — the same order recovery uses.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


def get_consumed(trip_advance: str) -> float:
	"""Sum of submitted Trip Expenses paid out of this advance."""
	return flt(
		frappe.db.sql(
			"""SELECT COALESCE(SUM(amount), 0) FROM `tabTrip Expense`
			WHERE trip_advance = %s AND docstatus = 1""",
			(trip_advance,),
		)[0][0]
	)


def get_recovered(trip_advance: str, exclude_run: str | None = None) -> float:
	"""Sum already recovered from salary through submitted Driver Payroll Runs."""
	conditions = ["r.trip_advance = %(adv)s", "run.docstatus = 1"]
	values = {"adv": trip_advance}
	if exclude_run:
		conditions.append("r.parent != %(exclude)s")
		values["exclude"] = exclude_run
	return flt(
		frappe.db.sql(
			f"""SELECT COALESCE(SUM(r.recovery_amount), 0)
			FROM `tabDriver Advance Recovery` r
			INNER JOIN `tabDriver Payroll Run` run ON run.name = r.parent
			WHERE {" AND ".join(conditions)}""",
			values,
		)[0][0]
	)


def _cash_returned_for_trip(trip: str) -> float:
	return flt(
		frappe.db.get_value(
			"Trip Settlement", {"trip": trip, "docstatus": 1}, "cash_returned"
		)
	)


def get_trip_advances(trip: str) -> list[dict]:
	"""Submitted advances on a Trip, oldest first."""
	return frappe.get_all(
		"Trip Advance",
		filters={"trip": trip, "docstatus": 1},
		fields=["name", "advance_date", "amount", "driver", "employee", "recipient_type",
			"company", "currency", "advance_account"],
		order_by="advance_date asc, creation asc",
	)


def get_outstanding(trip_advance: str, exclude_run: str | None = None) -> float:
	"""Outstanding balance on a single Trip Advance."""
	adv = frappe.db.get_value(
		"Trip Advance", trip_advance, ["amount", "trip", "docstatus"], as_dict=True
	)
	if not adv or adv.docstatus != 1:
		return 0.0

	consumed = get_consumed(trip_advance)
	recovered = get_recovered(trip_advance, exclude_run=exclude_run)

	# Allocate the Trip's cash_returned across its advances oldest-first.
	returned_pool = _cash_returned_for_trip(adv.trip)
	allocated_return = 0.0
	if returned_pool:
		for row in get_trip_advances(adv.trip):
			if returned_pool <= 0:
				break
			room = flt(row.amount) - get_consumed(row.name)
			take = min(room, returned_pool)
			if row.name == trip_advance:
				allocated_return = max(take, 0)
				break
			returned_pool -= max(take, 0)

	return max(flt(adv.amount) - consumed - recovered - allocated_return, 0.0)


def get_driver_outstanding_advances(
	driver: str, company: str, upto_date: str | None = None, exclude_run: str | None = None
) -> list[dict]:
	"""Every open advance for a driver, oldest first, with its outstanding balance.

	Covers advances booked against the Driver directly and advances booked to
	the Employee linked to that Driver.
	"""
	employee = frappe.db.get_value("Driver", driver, "employee")
	filters = ["ta.docstatus = 1", "ta.company = %(company)s"]
	values = {"company": company, "driver": driver, "employee": employee}
	party = ["ta.driver = %(driver)s"]
	if employee:
		party.append("(ta.recipient_type = 'Employee' AND ta.employee = %(employee)s)")
	filters.append("(" + " OR ".join(party) + ")")
	if upto_date:
		filters.append("ta.advance_date <= %(upto)s")
		values["upto"] = upto_date

	rows = frappe.db.sql(
		f"""SELECT ta.name, ta.trip, ta.advance_date, ta.amount, ta.currency
		FROM `tabTrip Advance` ta
		WHERE {" AND ".join(filters)}
		ORDER BY ta.advance_date ASC, ta.creation ASC""",
		values,
		as_dict=True,
	)
	out = []
	for r in rows:
		bal = get_outstanding(r.name, exclude_run=exclude_run)
		if bal > 0.005:
			r["outstanding"] = bal
			r["settled"] = flt(r.amount) - bal
			out.append(r)
	return out


@frappe.whitelist()
def get_driver_advance_summary(driver: str, company: str) -> dict:
	"""UI helper: total outstanding advance for a driver."""
	rows = get_driver_outstanding_advances(driver, company)
	return {
		"count": len(rows),
		"outstanding": sum(flt(r["outstanding"]) for r in rows),
		"advances": rows,
	}
