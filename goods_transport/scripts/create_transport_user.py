"""Create (or update) a user with only the Transport User role.

Callable from bench in production:

    bench --site <site> execute goods_transport.scripts.create_transport_user.execute \\
        --kwargs '{"email": "ops1@mycompany.com", "full_name": "Ops One"}'

Optional kwargs:
    first_name           split from full_name if not given
    last_name            split from full_name if not given
    password             set the account password to this value (also works
                         to reset the password on an existing user). SECURITY:
                         the value is passed via --kwargs which lands in
                         shell history and any bench execute log — prefer the
                         default flow (reset link) unless you specifically
                         need a pre-set password (e.g. seeding a demo user).
    send_welcome_email   default False; True to send Frappe's password-reset
                         email. Ignored when `password` is set.
    reset_password_link  default True; if True and no welcome email and no
                         `password`, print a one-time reset link to stdout so
                         admin can share it. Ignored when `password` is set.
    extra_roles          list of extra role names (e.g. ["System Manager"] for
                         a demo admin) — for the transport-only user leave
                         empty.
    hide_non_transport_modules  default True; populate User.block_modules to
                         collapse the sidebar to Goods Transport only.
    keep_visible_modules list of extra module names to keep visible.

Idempotent:
    - If the user exists, the Transport User role is added if missing;
      no other data is overwritten (except password, if provided).
    - Ensures the Transport User role itself exists before assigning.
"""

from __future__ import annotations

import frappe

from goods_transport.setup.install_transport_user import (
	TRANSPORT_USER_ROLE,
	install_transport_user_role,
	restrict_user_to_transport_modules,
)


def execute(
	email: str,
	full_name: str | None = None,
	first_name: str | None = None,
	last_name: str | None = None,
	password: str | None = None,
	send_welcome_email: bool = False,
	reset_password_link: bool = True,
	extra_roles: list[str] | None = None,
	hide_non_transport_modules: bool = True,
	keep_visible_modules: list[str] | None = None,
) -> dict:
	if not email:
		frappe.throw("email is required")

	# Make sure the role and its permissions exist before we assign anything.
	install_transport_user_role()

	# Split names when only full_name provided.
	if full_name and not (first_name or last_name):
		parts = full_name.strip().split(" ", 1)
		first_name = parts[0]
		last_name = parts[1] if len(parts) > 1 else ""

	first_name = first_name or email.split("@")[0]
	last_name = last_name or ""

	created = False
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"send_welcome_email": 1 if send_welcome_email else 0,
				"user_type": "System User",
				"enabled": 1,
			}
		)
		user.insert(ignore_permissions=True)
		created = True

	roles_to_add = [TRANSPORT_USER_ROLE] + list(extra_roles or [])
	existing_roles = {r.role for r in user.get("roles") or []}
	added_roles = []
	for role_name in roles_to_add:
		if role_name in existing_roles:
			continue
		user.append("roles", {"role": role_name})
		added_roles.append(role_name)
	if added_roles:
		user.save(ignore_permissions=True)

	blocked_modules: list[str] = []
	if hide_non_transport_modules:
		blocked_modules = restrict_user_to_transport_modules(
			email,
			keep_visible=set(keep_visible_modules or []),
		)

	# Password handling. When an explicit password is given, set it and skip
	# both the welcome email and the reset-link flow — the caller already
	# knows the password.
	password_set = False
	if password:
		from frappe.utils.password import update_password

		update_password(user=email, pwd=password)
		password_set = True

	frappe.db.commit()

	reset_link = None
	if created and not password_set and not send_welcome_email and reset_password_link:
		# Generate a one-time password-reset link the admin can share.
		reset_link = _generate_password_reset_link(user)

	result = {
		"email": email,
		"user": user.name,
		"created": created,
		"roles_added": added_roles,
		"password_reset_link": reset_link,
		"password_set": password_set,
		"blocked_modules": blocked_modules,
	}
	# Print for bench-execute visibility (execute returns dict, but console
	# users appreciate a human-readable summary too).
	print("---- create_transport_user ----")
	print(f"  User:        {result['user']}")
	print(f"  Created:     {result['created']}")
	print(f"  Roles added: {result['roles_added'] or '(none — already had them)'}")
	if blocked_modules:
		print(f"  Blocked modules ({len(blocked_modules)}): {', '.join(blocked_modules[:6])}" + (
			f", ...(+{len(blocked_modules) - 6} more)" if len(blocked_modules) > 6 else ""
		))
	if password_set:
		print("  Password:    set from the `password` kwarg. User can log in now.")
	elif reset_link:
		print(f"  Reset link:  {reset_link}")
		print("  Share the reset link with the user; it expires per Frappe defaults.")
	elif created and send_welcome_email:
		print("  Welcome email sent (assuming outgoing email is configured).")
	elif not created:
		print("  User already existed; password unchanged.")
	print("-------------------------------")
	return result


def _generate_password_reset_link(user_doc) -> str | None:
	"""Best-effort: return a full reset URL for the given User."""
	try:
		key = frappe.generate_hash()
		user_doc.db_set("reset_password_key", key, update_modified=False)
		host = frappe.utils.get_url()
		return f"{host}/update-password?key={key}"
	except Exception:
		return None
