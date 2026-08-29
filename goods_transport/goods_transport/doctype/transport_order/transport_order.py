import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TransportOrder(Document):
	def validate(self):
		self._default_currency()
		self._compute_estimated_totals()
		self._set_status_draft_time()

	def on_submit(self):
		if not self.status or self.status == "Draft":
			self.db_set("status", "Confirmed")

	def on_cancel(self):
		bilty_count = frappe.db.count("Bilty", {"transport_order": self.name, "docstatus": ["!=", 2]})
		if bilty_count:
			frappe.throw(
				_("Cannot cancel Transport Order {0}: {1} active Bilty record(s) reference it. Cancel them first.").format(
					self.name, bilty_count
				)
			)
		self.db_set("status", "Cancelled")

	# --- helpers ---------------------------------------------------------

	def _default_currency(self):
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def _compute_estimated_totals(self):
		self.estimated_freight = flt(self.rate) * flt(self.quantity)
		self.grand_total = flt(self.estimated_freight) + flt(self.additional_charges)

	def _set_status_draft_time(self):
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"

	# --- called by Bilty controller and POD controller -------------------

	def refresh_progress(self):
		"""Recompute dispatched/delivered/remaining/billed from linked Bilties."""
		rows = frappe.db.sql(
			"""
			SELECT b.name, b.docstatus, b.total_quantity, b.grand_total, b.pod_status,
			       b.sales_invoice, b.status
			FROM `tabBilty` b
			WHERE b.transport_order = %s
			""",
			(self.name,),
			as_dict=1,
		)
		dispatched = sum(flt(r.total_quantity) for r in rows if r.docstatus == 1)
		delivered = sum(
			flt(r.total_quantity)
			for r in rows
			if r.docstatus == 1 and (r.pod_status == "Received" or r.status in ("Delivered", "POD Received", "Billed", "Closed"))
		)
		billed = sum(flt(r.grand_total) for r in rows if r.docstatus == 1 and r.sales_invoice)
		remaining = max(flt(self.quantity) - dispatched, 0)

		new_status = self.status
		if self.docstatus == 1:
			if dispatched <= 0:
				new_status = "Confirmed"
			elif dispatched < flt(self.quantity):
				new_status = "Partially Dispatched"
			elif delivered >= flt(self.quantity) - 1e-9:
				new_status = "Delivered"
			else:
				new_status = "Fully Dispatched"

		frappe.db.set_value(
			"Transport Order",
			self.name,
			{
				"dispatched_quantity": dispatched,
				"delivered_quantity": delivered,
				"remaining_quantity": remaining,
				"billed_amount": billed,
				"status": new_status,
			},
			update_modified=False,
		)
