import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from goods_transport.goods_transport.services.cargo import validate_cargo_item


class Bilty(Document):
	def validate(self):
		self._default_billing_customer()
		self._default_currency()
		self._inherit_from_trip()
		self._inherit_from_order()
		self._validate_cargo_items()
		self._compute_item_totals()
		self._compute_charges()
		self._compute_freight_amount()
		self._compute_grand_total()
		self._resolve_rate_contract()
		self._set_pod_status()
		self._set_status()

	def _validate_cargo_items(self):
		# Server-side enforcement for every cargo row. Freight and additional
		# service Items live elsewhere on this doc; they must not leak in here
		# via imports, APIs, or scripts.
		for row in self.items or []:
			validate_cargo_item(row.item, row_idx=row.idx)

	def before_submit(self):
		self._snapshot_vehicle_plate()

	def on_submit(self):
		if self.status == "Draft":
			self.db_set("status", "Issued")
		self._notify_parents()

	def on_update_after_submit(self):
		self._notify_parents()

	def on_cancel(self):
		if self.sales_invoice:
			frappe.throw(
				_("Cannot cancel Bilty {0}: it is linked to Sales Invoice {1}. Cancel the invoice first.").format(
					self.name, self.sales_invoice
				)
			)
		self.db_set("status", "Cancelled")
		self._notify_parents()

	def _notify_parents(self):
		if self.transport_trip:
			try:
				frappe.get_doc("Transport Trip", self.transport_trip).refresh_load()
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Bilty parent Trip refresh failed")
		if self.transport_order:
			try:
				frappe.get_doc("Transport Order", self.transport_order).refresh_progress()
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Bilty parent Order refresh failed")

	def _inherit_from_trip(self):
		if not self.transport_trip:
			return
		trip = frappe.db.get_value(
			"Transport Trip",
			self.transport_trip,
			["vehicle", "vehicle_license_plate", "driver", "transporter", "company", "origin", "destination", "freight_item"],
			as_dict=True,
		)
		if not trip:
			return
		if trip.company and trip.company != self.company:
			frappe.throw(
				_("Bilty company {0} does not match Trip company {1}.").format(self.company, trip.company)
			)
		self.vehicle = self.vehicle or trip.vehicle
		self.vehicle_license_plate = self.vehicle_license_plate or trip.vehicle_license_plate
		self.driver = self.driver or trip.driver
		self.transporter = self.transporter or trip.transporter
		# Freight service Item: Trip carries the default for its whole journey;
		# every Bilty billed off this Trip goes through the same SI line item
		# unless the user overrides on the Bilty itself.
		self.freight_item = self.freight_item or trip.freight_item

	def _inherit_from_order(self):
		if not self.transport_order:
			return
		order = frappe.db.get_value(
			"Transport Order",
			self.transport_order,
			[
				"customer", "company", "origin", "destination", "loading_location",
				"delivery_location", "pod_required", "commodity", "currency",
				"rate_basis", "rate",
			],
			as_dict=True,
		)
		if not order:
			return
		if order.company and order.company != self.company:
			frappe.throw(
				_("Bilty company {0} does not match Order company {1}.").format(self.company, order.company)
			)
		if not self.customer:
			self.customer = order.customer
		self.origin = self.origin or order.origin
		self.destination = self.destination or order.destination
		self.loading_location = self.loading_location or order.loading_location
		self.delivery_location = self.delivery_location or order.delivery_location
		if not self.currency and order.currency:
			self.currency = order.currency
		if order.pod_required and not self.pod_required:
			self.pod_required = 1
		# Commercial terms (rate, rate_basis) are resolved by the calling
		# service — the JS "Create Bilty" dialog and create_bilty_from_trip
		# both pull from the Order at their entry point. Not inherited here
		# because rate_basis is a reqd Select that auto-defaults to the first
		# option ("Per Trip"), which would defeat a `not self.rate_basis`
		# check on validate().

	# --- helpers ---------------------------------------------------------

	def _default_billing_customer(self):
		if not self.billing_customer:
			self.billing_customer = self.customer

	def _default_currency(self):
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def _compute_item_totals(self):
		self.total_quantity = sum(flt(r.quantity) for r in (self.items or []))
		self.total_packages = sum(int(r.packages or 0) for r in (self.items or []))
		self.total_gross_weight = sum(flt(r.gross_weight) for r in (self.items or []))
		self.total_net_weight = sum(flt(r.net_weight) for r in (self.items or []))

	def _compute_charges(self):
		total_billable = 0.0
		for row in self.charges or []:
			row.amount = flt(row.quantity) * flt(row.rate)
			if row.billable_to_customer:
				total_billable += row.amount
		self.additional_charges_total = total_billable

	def _compute_freight_amount(self):
		self.freight_amount = flt(self.rate) * flt(self.freight_quantity or 1)

	def _compute_grand_total(self):
		self.grand_total = flt(self.freight_amount) + flt(self.additional_charges_total)

	def _resolve_rate_contract(self):
		# Best-effort lookup; user is free to override rate manually.
		if self.rate_contract:
			return
		if not (self.customer and self.company and self.origin and self.destination and self.bilty_date):
			return
		try:
			from goods_transport.goods_transport.services.rates import find_matching_contract

			contract = find_matching_contract(
				customer=self.customer,
				company=self.company,
				origin=self.origin,
				destination=self.destination,
				commodity=(self.items[0].item if self.items else None),
				on_date=self.bilty_date,
			)
		except Exception:
			contract = None
		if contract:
			self.rate_contract = contract

	def _snapshot_vehicle_plate(self):
		if self.vehicle and not self.vehicle_license_plate:
			plate = frappe.db.get_value("Vehicle", self.vehicle, "license_plate")
			if plate:
				self.vehicle_license_plate = plate

	def _set_pod_status(self):
		if not self.pod_required:
			self.pod_status = "Not Required"
		elif self.pod_status in (None, "", "Not Required"):
			self.pod_status = "Pending"

	def _set_status(self):
		# Draft-time status only; post-submit transitions handled elsewhere.
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 2:
			self.status = "Cancelled"
		# Post-submit intermediate states (Issued/In Transit/Delivered/POD Received/Billed/Closed)
		# are advanced by their respective actions (submit, POD, billing). Preserve current value.


@frappe.whitelist()
def get_unbilled_bilties(customer: str | None = None, company: str | None = None):
	"""Return submitted Bilties for the customer that are not yet linked to a Sales Invoice."""
	filters = {"docstatus": 1, "sales_invoice": ["in", ["", None]]}
	if customer:
		filters["billing_customer"] = customer
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Bilty",
		filters=filters,
		fields=[
			"name",
			"bilty_date",
			"customer",
			"billing_customer",
			"origin",
			"destination",
			"grand_total",
			"currency",
			"status",
		],
		order_by="bilty_date asc, name asc",
	)
