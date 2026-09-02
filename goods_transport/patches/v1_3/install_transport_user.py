"""Migration patch: seed the Transport User role, its Custom DocPerms, and
workspace visibility. Idempotent. User records are NOT created here — use
scripts/create_transport_user.py for that."""

from goods_transport.setup.install_transport_user import install_transport_user_role


def execute():
	install_transport_user_role()
