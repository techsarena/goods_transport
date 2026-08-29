import frappe
from frappe import _
from frappe.model.document import Document


class TransportLocation(Document):
	def validate(self):
		self._validate_geo()

	def _validate_geo(self):
		if self.latitude is not None and (self.latitude < -90 or self.latitude > 90):
			frappe.throw(_("Latitude must be between -90 and 90."))
		if self.longitude is not None and (self.longitude < -180 or self.longitude > 180):
			frappe.throw(_("Longitude must be between -180 and 180."))
