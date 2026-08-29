import frappe
from frappe import _
from frappe.model.document import Document


class TransportRoute(Document):
	def validate(self):
		if self.origin and self.destination and self.origin == self.destination:
			frappe.throw(_("Origin and Destination must be different."))
