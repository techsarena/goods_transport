import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DriverTripEarning(Document):
	def validate(self):
		self.total_earning = (
			flt(self.trip_amount)
			+ flt(self.km_amount)
			+ flt(self.tonnage_amount)
			+ flt(self.commission_amount)
		)
		if not self.employee and self.driver:
			self.employee = frappe.db.get_value("Driver", self.driver, "employee")
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def on_trash(self):
		if self.status == "Processed":
			frappe.throw(
				_("Cannot delete {0}: it has been paid through Driver Payroll Run {1}.").format(
					self.name, self.payroll_run
				)
			)
