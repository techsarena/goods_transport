frappe.ui.form.on("Trip Expense", {
	setup(frm) {
		// Only active expense types appear in the picker.
		frm.set_query("expense_type", () => ({
			filters: { is_active: 1 },
		}));

		// The default_expense_account we may pull from the Trip Expense Type
		// must belong to the Trip's company. If the user changes company we
		// want the account picker to only show that company's expense accounts.
		frm.set_query("expense_account", () => ({
			filters: {
				company: frm.doc.company,
				root_type: "Expense",
				is_group: 0,
			},
		}));
	},

	async expense_type(frm) {
		if (!frm.doc.expense_type) {
			return;
		}

		// Fill Description with the type name only when the field is empty.
		// Never overwrite user-entered text.
		if (!frm.doc.description) {
			frm.set_value("description", frm.doc.expense_type);
		}

		// Prefill Expense Account from the Trip Expense Type's default only
		// when it exists AND belongs to the Trip's company. Never seed an
		// account from another company.
		if (!frm.doc.expense_account && frm.doc.company) {
			const type_defaults = await frappe.db.get_value(
				"Trip Expense Type",
				frm.doc.expense_type,
				"default_expense_account",
			);
			const default_account = type_defaults && type_defaults.message && type_defaults.message.default_expense_account;
			if (default_account) {
				const acc = await frappe.db.get_value("Account", default_account, "company");
				const account_company = acc && acc.message && acc.message.company;
				if (account_company === frm.doc.company) {
					frm.set_value("expense_account", default_account);
				}
			}
		}
	},
});
