"""Install-time setup for goods_transport."""

from goods_transport.setup.install_accounting_dimensions import install_transport_accounting_dimensions
from goods_transport.setup.install_custom_fields import install_transport_custom_fields
from goods_transport.setup.install_dashboard import install_transport_dashboard
from goods_transport.setup.install_masters import install_transport_masters
from goods_transport.setup.install_print_format import install_all_print_formats
from goods_transport.setup.install_workspace import install_goods_transport_workspace


def after_install():
	install_transport_masters()
	install_transport_custom_fields()
	install_all_print_formats()
	install_transport_accounting_dimensions()
	install_transport_dashboard()
	install_goods_transport_workspace()
