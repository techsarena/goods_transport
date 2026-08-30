import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class TripExpense(Document):
	def validate(self):
		self._validate_trip_open()
		self._validate_recoverable()

	def before_submit(self):
		# Draft can be saved without a receipt; the requirement only bites at
		# submission so the ops team can capture the entry immediately in the
		# field and attach the receipt later.
		self._validate_receipt_before_submit()

	def _validate_receipt_before_submit(self):
		if not self.expense_type:
			return
		if self.receipt:
			return
		requires_receipt = frappe.db.get_value(
			"Trip Expense Type", self.expense_type, "requires_receipt"
		)
		if requires_receipt:
			frappe.throw(
				_("A receipt is required before submitting a Trip Expense of type {0}.").format(
					frappe.bold(self.expense_type)
				)
			)

	def on_submit(self):
		if self.payment_mode == "Company Cash/Bank":
			self.journal_entry = self._create_cash_journal_entry()
		elif self.payment_mode == "Trip Advance":
			self.journal_entry = self._create_advance_journal_entry()
		elif self.payment_mode == "Third-Party Bill":
			self.purchase_invoice = self._create_purchase_invoice()
		self.db_set("journal_entry", self.journal_entry, update_modified=False)
		self.db_set("purchase_invoice", self.purchase_invoice, update_modified=False)

	def on_cancel(self):
		if self.journal_entry:
			doc = frappe.get_doc("Journal Entry", self.journal_entry)
			if doc.docstatus == 1:
				doc.cancel()
		if self.purchase_invoice:
			doc = frappe.get_doc("Purchase Invoice", self.purchase_invoice)
			if doc.docstatus == 1:
				doc.cancel()

	# --- validations -----------------------------------------------------

	def _validate_trip_open(self):
		trip_status = frappe.db.get_value("Transport Trip", self.trip, "status")
		if trip_status in ("Settled", "Closed", "Cancelled"):
			frappe.throw(
				_("Cannot book expense against Trip {0}: it is {1}.").format(self.trip, trip_status)
			)

	def _validate_recoverable(self):
		if self.billable_to_customer and self.recoverable_amount and flt(self.recoverable_amount) > flt(self.amount):
			frappe.throw(_("Recoverable amount cannot exceed the expense amount."))

	# --- accounting document builders ------------------------------------

	def _cost_center(self):
		return frappe.get_cached_value("Company", self.company, "cost_center")

	def _create_cash_journal_entry(self) -> str:
		cost_center = self._cost_center()
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = self.expense_date
		je.voucher_type = "Cash Entry"
		je.user_remark = _("Trip Expense {0} on Trip {1}: {2}").format(
			self.name, self.trip, self.description or self.expense_type or ""
		)
		if je.meta.has_field("transport_trip"):
			je.transport_trip = self.trip
		self._append_je_account(je, self.expense_account, dr=self.amount, cost_center=cost_center)
		self._append_je_account(je, self.cash_bank_account, cr=self.amount, cost_center=cost_center)
		je.insert()
		je.submit()
		return je.name

	def _create_advance_journal_entry(self) -> str:
		advance = frappe.get_doc("Trip Advance", self.trip_advance)
		if advance.docstatus != 1:
			frappe.throw(_("Trip Advance {0} must be submitted first.").format(advance.name))
		if advance.trip != self.trip:
			frappe.throw(
				_("Trip Advance {0} belongs to a different Trip ({1}).").format(advance.name, advance.trip)
			)
		cost_center = self._cost_center()
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = self.expense_date
		je.voucher_type = "Journal Entry"
		je.user_remark = _("Trip Expense {0} settled against Advance {1}").format(self.name, advance.name)
		if je.meta.has_field("transport_trip"):
			je.transport_trip = self.trip
		self._append_je_account(je, self.expense_account, dr=self.amount, cost_center=cost_center)
		self._append_je_account(
			je,
			advance.advance_account,
			cr=self.amount,
			cost_center=cost_center,
			party_type=advance.party_type_for_je(),
			party=advance.party_for_je(),
		)
		je.insert()
		je.submit()
		return je.name

	def _create_purchase_invoice(self) -> str:
		cost_center = self._cost_center()
		item_code = None
		if self.expense_type:
			item_code = frappe.db.get_value("Trip Expense Type", self.expense_type, "default_item")
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = self.supplier
		pi.company = self.company
		pi.posting_date = getdate(self.expense_date)
		pi.set_posting_time = 1
		if pi.meta.has_field("transport_trip"):
			pi.transport_trip = self.trip
		item_row = {
			"description": self.description or self.expense_type or "Trip Expense",
			"qty": 1,
			"rate": flt(self.amount),
			"expense_account": self.expense_account,
			"cost_center": cost_center,
		}
		if item_code:
			item_row["item_code"] = item_code
		row = pi.append("items", item_row)
		if row.meta.has_field("transport_trip"):
			row.transport_trip = self.trip
		pi.insert()
		# Leave as draft — user reviews & submits.
		return pi.name

	def _append_je_account(self, je, account, dr=0, cr=0, cost_center=None, party_type=None, party=None):
		row = {
			"account": account,
			"debit_in_account_currency": flt(dr),
			"credit_in_account_currency": flt(cr),
		}
		if cost_center:
			row["cost_center"] = cost_center
		if party_type and party:
			row["party_type"] = party_type
			row["party"] = party
		acc_row = je.append("accounts", row)
		if acc_row.meta.has_field("transport_trip"):
			acc_row.transport_trip = self.trip
