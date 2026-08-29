"""Transport Rate Contract resolution.

The Bilty controller uses `find_matching_contract` as a best-effort prefill.
V1 policy is manual-with-lookup: the rate is always editable by the user, and
the resolved contract is stored on the Bilty for auditability.
"""

from __future__ import annotations

import frappe


def find_matching_contract(
	customer: str,
	company: str,
	origin: str,
	destination: str,
	commodity: str | None = None,
	vehicle_type: str | None = None,
	on_date=None,
) -> str | None:
	"""Return the most specific active Rate Contract matching the given criteria.

	Preference order (most specific first):
	    1. Matches commodity AND vehicle_type
	    2. Matches commodity
	    3. Matches vehicle_type
	    4. Origin + destination only
	"""
	if not (customer and company and origin and destination and on_date):
		return None

	base_conditions = [
		["customer", "=", customer],
		["company", "=", company],
		["origin", "=", origin],
		["destination", "=", destination],
		["is_active", "=", 1],
		["valid_from", "<=", on_date],
	]

	# valid_to is optional; open-ended contracts have valid_to = None.
	def _search(extra_conditions: list[list]) -> str | None:
		filters = base_conditions + extra_conditions
		open_ended = frappe.get_all(
			"Transport Rate Contract",
			filters=filters + [["valid_to", "is", "not set"]],
			pluck="name",
			order_by="valid_from desc",
			limit=1,
		)
		if open_ended:
			return open_ended[0]
		bounded = frappe.get_all(
			"Transport Rate Contract",
			filters=filters + [["valid_to", ">=", on_date]],
			pluck="name",
			order_by="valid_from desc",
			limit=1,
		)
		return bounded[0] if bounded else None

	if commodity and vehicle_type:
		hit = _search([["commodity", "=", commodity], ["vehicle_type", "=", vehicle_type]])
		if hit:
			return hit
	if commodity:
		hit = _search([["commodity", "=", commodity]])
		if hit:
			return hit
	if vehicle_type:
		hit = _search([["vehicle_type", "=", vehicle_type]])
		if hit:
			return hit
	return _search([])


@frappe.whitelist()
def get_matching_contract_rate(
	customer: str,
	company: str,
	origin: str,
	destination: str,
	commodity: str | None = None,
	vehicle_type: str | None = None,
	on_date: str | None = None,
) -> dict | None:
	"""Whitelisted wrapper — returns {contract, rate, rate_basis, currency} or None."""
	name = find_matching_contract(
		customer=customer,
		company=company,
		origin=origin,
		destination=destination,
		commodity=commodity,
		vehicle_type=vehicle_type,
		on_date=on_date or frappe.utils.today(),
	)
	if not name:
		return None
	c = frappe.db.get_value(
		"Transport Rate Contract",
		name,
		["name", "rate", "rate_basis", "currency", "minimum_charge"],
		as_dict=True,
	)
	return {
		"contract": c.name,
		"rate": c.rate,
		"rate_basis": c.rate_basis,
		"currency": c.currency,
		"minimum_charge": c.minimum_charge,
	}
