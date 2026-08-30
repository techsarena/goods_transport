"""Migration patch: install the Cargo Items group and 10 seeded cargo items.

Runs on `bench migrate` after the DocType schema is synced. Idempotent —
skips records that already exist so nothing user-modified is overwritten.
Fresh installs get the same records via after_install → install_transport_masters.
"""

from goods_transport.setup.install_masters import install_cargo_item_group_and_items


def execute():
	install_cargo_item_group_and_items()
