import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TripAdvance(Document):
	def validate(self):
		self._snapshot_receiver_name()
		self._validate_trip_open()

	def on_submit(self):
		self.journal_entry = self._create_journal_entry()
		self.db_set("journal_entry", self.journal_entry, update_modified=False)
		self.db_set("status", "Paid", update_modified=False)

	def on_cancel(self):
		if self.journal_entry:
			doc = frappe.get_doc("Journal Entry", self.journal_entry)
			if doc.docstatus == 1:
				doc.cancel()
		self.db_set("status", "Cancelled", update_modified=False)

	# --- helpers ---------------------------------------------------------

	def _validate_trip_open(self):
		trip_status = frappe.db.get_value("Transport Trip", self.trip, "status")
		if trip_status in ("Settled", "Closed", "Cancelled"):
			frappe.throw(_("Cannot pay advance on Trip {0}: it is {1}.").format(self.trip, trip_status))

	def _snapshot_receiver_name(self):
		if self.receiver_name:
			return
		if self.recipient_type == "Driver" and self.driver:
			self.receiver_name = frappe.db.get_value("Driver", self.driver, "full_name")
		elif self.recipient_type == "Employee" and self.employee:
			self.receiver_name = frappe.db.get_value("Employee", self.employee, "employee_name")
		elif self.recipient_type == "Supplier" and self.supplier:
			self.receiver_name = frappe.db.get_value("Supplier", self.supplier, "supplier_name")

	def _create_journal_entry(self) -> str:
		cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = self.advance_date
		je.voucher_type = "Cash Entry"
		je.user_remark = _("Trip Advance {0} on Trip {1} to {2}").format(
			self.name, self.trip, self.receiver_name or ""
		)
		if je.meta.has_field("transport_trip"):
			je.transport_trip = self.trip

		# Debit: Advance Account (with party info if we can resolve one)
		dr_row = {
			"account": self.advance_account,
			"debit_in_account_currency": flt(self.amount),
			"cost_center": cost_center,
		}
		party_type = self.party_type_for_je()
		party = self.party_for_je()
		if party_type and party:
			dr_row["party_type"] = party_type
			dr_row["party"] = party
		acc = je.append("accounts", dr_row)
		if acc.meta.has_field("transport_trip"):
			acc.transport_trip = self.trip

		# Credit: Paying (cash/bank)
		cr_row = {
			"account": self.paying_account,
			"credit_in_account_currency": flt(self.amount),
			"cost_center": cost_center,
		}
		acc = je.append("accounts", cr_row)
		if acc.meta.has_field("transport_trip"):
			acc.transport_trip = self.trip

		je.insert()
		je.submit()
		return je.name

	# --- called by Trip Expense controller when settling against an advance
	def party_type_for_je(self) -> str | None:
		if self.recipient_type == "Employee":
			return "Employee"
		if self.recipient_type == "Supplier":
			return "Supplier"
		if self.recipient_type == "Driver" and self.driver:
			emp = frappe.db.get_value("Driver", self.driver, "employee")
			return "Employee" if emp else None
		return None

	def party_for_je(self) -> str | None:
		if self.recipient_type == "Employee":
			return self.employee
		if self.recipient_type == "Supplier":
			return self.supplier
		if self.recipient_type == "Driver" and self.driver:
			return frappe.db.get_value("Driver", self.driver, "employee")
		return None


@frappe.whitelist()
def get_advance_balance(trip_advance: str) -> dict:
	"""Return {paid, consumed, balance} for a Trip Advance.

	`consumed` = sum of submitted Trip Expense.amount where trip_advance == this."""
	adv = frappe.db.get_value("Trip Advance", trip_advance, ["amount", "docstatus"], as_dict=True)
	if not adv or adv.docstatus != 1:
		return {"paid": 0, "consumed": 0, "balance": 0}
	consumed = (
		frappe.db.sql(
			"SELECT COALESCE(SUM(amount), 0) FROM `tabTrip Expense` WHERE trip_advance=%s AND docstatus=1",
			(trip_advance,),
		)[0][0]
		or 0
	)
	return {"paid": flt(adv.amount), "consumed": flt(consumed), "balance": flt(adv.amount) - flt(consumed)}
