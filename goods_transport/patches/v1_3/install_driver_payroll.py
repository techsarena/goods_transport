"""Install (or refresh) the driver-payroll layer on an existing site.

Idempotent: every installer checks before it writes, so this is safe to
re-run on each migrate.
"""

import frappe

from goods_transport.install import install_driver_payroll


def execute():
	if "hrms" not in frappe.get_installed_apps():
		frappe.log_error(
			title="Driver payroll skipped",
			message="HRMS is not installed on this site, so the driver-payroll "
			"setup was skipped. Install hrms and run `bench migrate` again.",
		)
		return
	install_driver_payroll()
