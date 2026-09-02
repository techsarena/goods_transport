"""Install-time setup for goods_transport.

Runs the transport masters first, then the Transport User role (which needs
the workspace it attaches visibility to), then the driver-payroll layer,
which needs HRMS (Salary Component, Salary Structure) to be present.
"""

from goods_transport.setup.install_accounting_dimensions import install_transport_accounting_dimensions
from goods_transport.setup.install_custom_fields import install_transport_custom_fields
from goods_transport.setup.install_dashboard import install_transport_dashboard
from goods_transport.setup.install_masters import install_transport_masters
from goods_transport.setup.install_pay_rules import install_default_pay_rules
from goods_transport.setup.install_payroll_custom_fields import install_payroll_custom_fields
from goods_transport.setup.install_payroll_workspace import install_payroll_workspace
from goods_transport.setup.install_print_format import install_all_print_formats
from goods_transport.setup.install_salary_components import (
	install_driver_advance_accounts,
	install_driver_salary_components,
	install_driver_salary_structure,
)
from goods_transport.setup.install_transport_user import install_transport_user_role
from goods_transport.setup.install_workspace import install_goods_transport_workspace


def after_install():
	install_transport_masters()
	install_transport_custom_fields()
	install_all_print_formats()
	install_transport_accounting_dimensions()
	install_transport_dashboard()
	install_goods_transport_workspace()
	# Role after workspace so the workspace exists when we attach role visibility.
	install_transport_user_role()
	install_driver_payroll()


def install_driver_payroll():
	"""Driver payroll layer. Requires HRMS."""
	install_payroll_custom_fields()
	install_driver_advance_accounts()
	install_driver_salary_components()
	install_driver_salary_structure()
	install_default_pay_rules()
	install_payroll_workspace()
