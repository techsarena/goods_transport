"""Seed the 'Transport User' Role, its Custom DocPerms across the DocTypes
this role must be able to work with, and add it to the Goods Transport
workspace so those users see the workspace in their sidebar.

The role gets full operational access (create/read/write/submit/cancel/amend)
on every transport DocType and on the ERPNext accounting docs the transport
workflow produces (Sales Invoice, Purchase Invoice, Journal Entry, Payment
Entry — every one of these is created programmatically from Bilty / Trip
Expense / Trip Advance and must remain end-to-end operable by the same user).

Read-only access on the reference masters the transport workflow needs to
look up (Company, Currency, UOM, Account, Cost Center, Item Group, etc.).

Idempotent — safe to run repeatedly. Preserves any user-added permissions
on top of what this installer sets.

User creation is intentionally NOT part of this installer — running it on
an existing production site should not fabricate users. Use
`scripts/create_transport_user.py` (bench-executable) to create actual
users and assign the role.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property


TRANSPORT_USER_ROLE = "Transport User"

# Own DocTypes — full operational access.
_OWN_DOCTYPES = [
	"Transport Order",
	"Transport Trip",
	"Bilty",
	"Bilty Item",
	"Bilty Charge",
	"Bilty Reference",
	"Proof of Delivery",
	"Trip Advance",
	"Trip Expense",
	"Trip Expense Type",
	"Trip Settlement",
	"Transport Location",
	"Transport Route",
	"Transport Rate Contract",
	"Vehicle Type",
]

# ERPNext / Frappe DocTypes — access level depends on how the role uses them.
# (doctype, permlevel, flags to set)
_STANDARD_PERMS = [
	# Accounting outputs — full lifecycle, because Bilty → SI, Trip Expense → JE/PI etc.
	("Sales Invoice", 0, ("read", "write", "create", "submit", "cancel", "amend", "email", "print", "report", "export")),
	("Sales Invoice Item", 0, ("read", "write", "create")),
	("Purchase Invoice", 0, ("read", "write", "create", "submit", "cancel", "amend", "email", "print", "report", "export")),
	("Purchase Invoice Item", 0, ("read", "write", "create")),
	("Journal Entry", 0, ("read", "write", "create", "submit", "cancel", "amend", "email", "print", "report", "export")),
	("Journal Entry Account", 0, ("read", "write", "create")),
	("Payment Entry", 0, ("read", "write", "create", "submit", "cancel", "amend", "email", "print", "report", "export")),
	# Party masters — used everywhere in the workflow.
	("Customer", 0, ("read", "write", "create", "report", "email", "print", "export")),
	("Supplier", 0, ("read", "write", "create", "report", "email", "print", "export")),
	("Address", 0, ("read", "write", "create")),
	("Contact", 0, ("read", "write", "create")),
	# Fleet masters — standard ERPNext.
	("Vehicle", 0, ("read", "write", "create", "report", "print", "email", "export")),
	("Driver", 0, ("read", "write", "create", "report", "print", "email", "export")),
	# Items — need to add cargo Items on the fly.
	("Item", 0, ("read", "write", "create", "report", "print", "export")),
	# Reference lookups — read-only.
	("Item Group", 0, ("read",)),
	("Supplier Group", 0, ("read",)),
	("Customer Group", 0, ("read",)),
	("Territory", 0, ("read",)),
	("Brand", 0, ("read",)),
	("Company", 0, ("read",)),
	("Fiscal Year", 0, ("read",)),
	("Currency", 0, ("read",)),
	("UOM", 0, ("read",)),
	("Country", 0, ("read",)),
	("Account", 0, ("read", "report")),
	("Cost Center", 0, ("read",)),
	("Print Format", 0, ("read",)),
	("Report", 0, ("read",)),
	# Desk essentials — attachments, comments, todos.
	("File", 0, ("read", "write", "create", "delete")),
	("Comment", 0, ("read", "write", "create")),
	("ToDo", 0, ("read", "write", "create", "delete")),
	("Note", 0, ("read", "write", "create")),
]

_WORKSPACE_NAME = "Goods Transport"


def install_transport_user_role():
	_ensure_role()
	_ensure_own_doctype_perms()
	_ensure_standard_perms()
	_ensure_workspace_visibility()
	frappe.db.commit()


def _ensure_role():
	if frappe.db.exists("Role", TRANSPORT_USER_ROLE):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": TRANSPORT_USER_ROLE,
			"desk_access": 1,
			"is_custom": 1,
			"disabled": 0,
		}
	).insert(ignore_permissions=True)


def _ensure_own_doctype_perms():
	# Full operational access on our own DocTypes.
	flags = ("read", "write", "create", "submit", "cancel", "amend", "delete", "email", "print", "report", "export", "share")
	for dt in _OWN_DOCTYPES:
		if not frappe.db.exists("DocType", dt):
			continue
		# For child tables the standard practice is NOT to give submit/cancel/amend
		is_child = frappe.db.get_value("DocType", dt, "istable")
		row_flags = ("read", "write", "create") if is_child else flags
		_ensure_perm(dt, row_flags)


def _ensure_standard_perms():
	for dt, permlevel, flags in _STANDARD_PERMS:
		if not frappe.db.exists("DocType", dt):
			continue
		_ensure_perm(dt, flags, permlevel=permlevel)


def _ensure_perm(doctype: str, flags: tuple, permlevel: int = 0):
	"""Ensure a Custom DocPerm exists for Transport User on the DocType
	with all `flags` set to 1. Existing rows are updated in place — no
	duplicates, no lost user-added flags on other roles."""
	existing = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": TRANSPORT_USER_ROLE, "permlevel": permlevel},
		"name",
	)
	if not existing:
		try:
			add_permission(doctype, TRANSPORT_USER_ROLE, permlevel)
		except frappe.exceptions.ValidationError:
			# Some core DocTypes reject add_permission (e.g. locked list). Skip.
			return
	for f in flags:
		try:
			update_permission_property(doctype, TRANSPORT_USER_ROLE, permlevel, f, 1)
		except Exception:
			# Individual flag failures shouldn't nuke the whole seed.
			pass


def _ensure_workspace_visibility():
	if not frappe.db.exists("Workspace", _WORKSPACE_NAME):
		return
	ws = frappe.get_doc("Workspace", _WORKSPACE_NAME)
	# Workspace 'roles' child table — if empty, the workspace is visible to all
	# roles (public). We want Transport User visibility whether or not roles
	# have been restricted, so append the role if it isn't already present.
	if not any((r.role == TRANSPORT_USER_ROLE) for r in (ws.get("roles") or [])):
		ws.append("roles", {"role": TRANSPORT_USER_ROLE})
		ws.save(ignore_permissions=True)


# Modules whose workspaces stay visible for a transport-only user. Everything
# else is hidden via User.block_modules — DocType permissions already forbid
# access, but Frappe workspaces are public by default and clutter the sidebar
# even when the user cannot open any of their DocTypes. `Goods Transport` is
# the only module a pure transport user needs to see in the sidebar.
KEEP_VISIBLE_MODULES = {"Goods Transport"}


def restrict_user_to_transport_modules(user_email: str, keep_visible: set[str] | None = None) -> list[str]:
	"""Populate `User.block_modules` for the given user so every Module Def
	except the transport ones is hidden from their sidebar.

	Idempotent — recomputes the full list every time it runs, so newly
	installed apps are picked up on the next call.

	Returns the list of module names that ended up blocked.
	"""
	if not frappe.db.exists("User", user_email):
		return []

	whitelist = set(keep_visible or set()) | KEEP_VISIBLE_MODULES
	all_modules = frappe.get_all("Module Def", pluck="name")
	to_block = sorted(m for m in all_modules if m not in whitelist)

	user = frappe.get_doc("User", user_email)
	user.set("block_modules", [])
	for m in to_block:
		user.append("block_modules", {"module": m})
	user.save(ignore_permissions=True)
	return to_block
