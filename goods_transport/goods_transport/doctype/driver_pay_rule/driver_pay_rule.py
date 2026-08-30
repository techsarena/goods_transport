import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DriverPayRule(Document):
	def validate(self):
		self._validate_components()
		self._validate_overlap()

	def _validate_components(self):
		"""Every non-zero rate needs a Salary Component to post against."""
		pairs = [
			(self.per_trip_amount, "trip_component", _("Amount Per Trip")),
			(self.rate_per_km, "km_component", _("Rate Per KM")),
			(self.rate_per_ton, "tonnage_component", _("Rate Per Ton")),
			(self.commission_percent, "commission_component", _("Commission %")),
		]
		for rate, field, label in pairs:
			if flt(rate) and not self.get(field):
				frappe.throw(
					_("{0} is set, so its Salary Component is required.").format(label)
				)
			if self.get(field):
				ctype = frappe.db.get_value("Salary Component", self.get(field), "type")
				if ctype != "Earning":
					frappe.throw(
						_("Salary Component {0} must be of type Earning.").format(self.get(field))
					)

		if self.recover_advances:
			if not self.recovery_component:
				frappe.throw(_("Recovery Component is required when advances are recovered from salary."))
			ctype = frappe.db.get_value("Salary Component", self.recovery_component, "type")
			if ctype != "Deduction":
				frappe.throw(
					_("Recovery Component {0} must be of type Deduction.").format(self.recovery_component)
				)

	def _validate_overlap(self):
		"""Two active rules with the same scope would make resolution arbitrary."""
		other = frappe.db.get_value(
			"Driver Pay Rule",
			{
				"name": ["!=", self.name or "__new__"],
				"company": self.company,
				"is_active": 1,
				"driver": self.driver or "",
				"vehicle_type": self.vehicle_type or "",
				"route": self.route or "",
			},
			"name",
		)
		if other:
			frappe.msgprint(
				_("Active Driver Pay Rule {0} already covers the same scope. The most recently "
				  "modified rule will win.").format(other),
				indicator="orange",
				alert=True,
			)
