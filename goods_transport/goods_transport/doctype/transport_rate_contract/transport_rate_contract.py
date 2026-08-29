import frappe
from frappe import _
from frappe.model.document import Document


class TransportRateContract(Document):
	def validate(self):
		self._validate_validity()
		self._set_currency_default()

	def _validate_validity(self):
		if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
			frappe.throw(_("Valid To cannot be earlier than Valid From."))

	def _set_currency_default(self):
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
