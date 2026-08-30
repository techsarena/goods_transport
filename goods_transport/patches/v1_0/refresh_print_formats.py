"""Force-reinstall all shipped print formats so template changes shipped in a
release propagate to existing sites. install_all_print_formats() upserts by
name and is safe against user-duplicated formats (users are expected to copy
'X (Standard)' into their own name and edit that copy)."""

from goods_transport.setup.install_print_format import install_all_print_formats


def execute():
	install_all_print_formats()
