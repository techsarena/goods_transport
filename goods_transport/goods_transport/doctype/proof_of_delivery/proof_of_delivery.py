import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ProofofDelivery(Document):
	def validate(self):
		self._validate_bilty_submitted()
		self._compute_short_quantity()

	def on_submit(self):
		# Advance Bilty state.
		bilty = frappe.get_doc("Bilty", self.bilty)
		updates = {"pod_status": "Received"}
		# Preserve Billed / Closed if already reached.
		if bilty.status not in ("Billed", "Closed", "Cancelled"):
			updates["status"] = "POD Received"
		frappe.db.set_value("Bilty", self.bilty, updates, update_modified=False)

		# Nudge the parent Order to recompute delivered qty.
		order = frappe.db.get_value("Bilty", self.bilty, "transport_order")
		if order:
			frappe.get_doc("Transport Order", order).refresh_progress()

	def on_cancel(self):
		bilty = frappe.get_doc("Bilty", self.bilty)
		new_pod_status = "Pending" if bilty.pod_required else "Not Required"
		# Reset Bilty status if it was moved to POD Received solely by this doc.
		updates = {"pod_status": new_pod_status}
		if bilty.status == "POD Received":
			updates["status"] = "Delivered" if bilty.status == "POD Received" else bilty.status
		frappe.db.set_value("Bilty", self.bilty, updates, update_modified=False)

		order = bilty.transport_order
		if order:
			frappe.get_doc("Transport Order", order).refresh_progress()

	# --- helpers ---------------------------------------------------------

	def _validate_bilty_submitted(self):
		docstatus = frappe.db.get_value("Bilty", self.bilty, "docstatus")
		if docstatus is None:
			frappe.throw(_("Bilty {0} does not exist.").format(self.bilty))
		if docstatus != 1:
			frappe.throw(_("Bilty {0} is not submitted.").format(self.bilty))

	def _compute_short_quantity(self):
		shipped = flt(self.shipped_quantity)
		delivered = flt(self.delivered_quantity)
		self.short_quantity = max(shipped - delivered, 0)
