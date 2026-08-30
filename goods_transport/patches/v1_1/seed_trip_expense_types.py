"""Migration patch: seed the seven default Trip Expense Type master records.

Existing sites installed before this feature will not re-run the v1_0
install_masters patch, so we ship a fresh patch that calls the reusable
installer. Idempotent — skips names that already exist so user changes are
preserved."""

from goods_transport.setup.install_masters import install_trip_expense_types


def execute():
	install_trip_expense_types()
