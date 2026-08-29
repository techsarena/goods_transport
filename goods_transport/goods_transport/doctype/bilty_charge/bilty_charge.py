from frappe.model.document import Document


class BiltyCharge(Document):
	def compute_amount(self):
		self.amount = (self.quantity or 0) * (self.rate or 0)
