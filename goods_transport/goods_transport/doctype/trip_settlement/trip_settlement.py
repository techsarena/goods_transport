import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TripSettlement(Document):
	def validate(self):
		self._validate_unique_open_settlement()
		self.refresh_from_source()
		self._compute_final()

	def on_submit(self):
		trip = frappe.get_doc("Transport Trip", self.trip)
		if trip.status in ("Cancelled",):
			frappe.throw(_("Cannot settle cancelled Trip {0}.").format(self.trip))
		frappe.db.set_value(
			"Transport Trip",
			self.trip,
			{"status": "Settled", "trip_settlement": self.name},
			update_modified=False,
		)

	def on_cancel(self):
		frappe.db.set_value(
			"Transport Trip",
			self.trip,
			{"status": "Delivered", "trip_settlement": None},
			update_modified=False,
		)

	# --- computation -----------------------------------------------------

	def _validate_unique_open_settlement(self):
		other = frappe.db.get_value(
			"Trip Settlement",
			{"trip": self.trip, "docstatus": ["!=", 2], "name": ["!=", self.name or "__new__"]},
			"name",
		)
		if other:
			frappe.throw(_("Trip Settlement {0} already exists for Trip {1}.").format(other, self.trip))

	def refresh_from_source(self):
		"""Recompute all figures from the underlying Bilty / Sales Invoice /
		Trip Expense / Trip Advance records. Called from validate() and via
		the client-side Refresh button."""
		trip = frappe.get_doc("Transport Trip", self.trip)

		# Revenue
		invoices = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "transport_trip": self.trip},
			fields=["name", "grand_total"],
		)
		self.total_revenue = sum(flt(r.grand_total) for r in invoices)
		self.invoice_count = len(invoices)

		bilties = frappe.get_all(
			"Bilty",
			filters={"transport_trip": self.trip, "docstatus": 1},
			fields=["name", "grand_total", "sales_invoice"],
		)
		self.bilty_count = len(bilties)
		self.pending_revenue = sum(flt(b.grand_total) for b in bilties if not b.sales_invoice)

		# Cost — planned from Trip + actuals from Trip Expense
		self.vehicle_hire = flt(trip.agreed_vehicle_hire)
		self.driver_allowance = flt(trip.driver_allowance)
		expense_total = (
			frappe.db.sql(
				"SELECT COALESCE(SUM(amount), 0) FROM `tabTrip Expense` WHERE trip=%s AND docstatus=1",
				(self.trip,),
			)[0][0]
			or 0
		)
		self.total_expenses = flt(expense_total)

		# Advances
		self.total_advances = (
			frappe.db.sql(
				"SELECT COALESCE(SUM(amount), 0) FROM `tabTrip Advance` WHERE trip=%s AND docstatus=1",
				(self.trip,),
			)[0][0]
			or 0
		)
		self.consumed_from_advance = (
			frappe.db.sql(
				"""SELECT COALESCE(SUM(te.amount), 0)
				FROM `tabTrip Expense` te
				WHERE te.trip=%s AND te.docstatus=1 AND te.payment_mode='Trip Advance'""",
				(self.trip,),
			)[0][0]
			or 0
		)

	def _compute_final(self):
		# Cost model — planned Driver Allowance is intentionally NOT part of
		# total_cost. Actual driver allowance is recorded as a submitted Trip
		# Expense with expense_type='Driver Allowance' and rolls up through
		# `total_expenses`. driver_allowance on the header is a planning /
		# budgeting reference and is shown separately in the settlement print
		# for comparison; it must not be added here or the actual + planned
		# allowance would be double-counted.
		self.total_cost = flt(self.vehicle_hire) + flt(self.total_expenses)
		self.gross_profit = flt(self.total_revenue) - flt(self.total_cost)
		self.margin_percent = (self.gross_profit / self.total_revenue * 100) if self.total_revenue else 0
		self.advance_balance = flt(self.total_advances) - flt(self.consumed_from_advance)
		self.outstanding_from_driver = max(flt(self.advance_balance) - flt(self.cash_returned), 0)


@frappe.whitelist()
def create_settlement_for_trip(trip: str) -> str:
	"""Create a draft Trip Settlement prefilled from the given Trip."""
	if frappe.db.exists("Trip Settlement", {"trip": trip, "docstatus": ["!=", 2]}):
		frappe.throw(_("An open Trip Settlement already exists for Trip {0}.").format(trip))
	ts = frappe.new_doc("Trip Settlement")
	ts.trip = trip
	ts.insert()
	return ts.name
