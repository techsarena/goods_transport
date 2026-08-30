frappe.ui.form.on("Driver Payroll Run", {
	setup(frm) {
		frm.set_query("company", () => ({ filters: { is_group: 0 } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch Trip Earnings"), () => {
				frm.call({
					doc: frm.doc,
					method: "fetch_earnings",
					freeze: true,
					freeze_message: __("Reading completed trips..."),
					callback: (r) => {
						frm.refresh_field("details");
						frm.refresh_fields();
						const m = r.message || {};
						frappe.show_alert({
							message: __("{0} driver(s), {1} trip(s) loaded", [m.drivers || 0, m.trips || 0]),
							indicator: (m.drivers ? "green" : "orange"),
						});
					},
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Additional Salaries"), () => {
				frappe.set_route("List", "Additional Salary", {
					ref_docname: frm.doc.name,
				});
			}, __("View"));

			frm.add_custom_button(__("Payroll Entry"), () => {
				frappe.new_doc("Payroll Entry", {
					company: frm.doc.company,
					posting_date: frm.doc.payroll_date,
					start_date: frm.doc.from_date,
					end_date: frm.doc.to_date,
				});
			}, __("Create"));

			frm.dashboard.add_comment(
				__("Trip earnings are now Additional Salary records. Run Payroll Entry for {0} – {1} to generate the Salary Slips that pay them.",
					[frappe.datetime.str_to_user(frm.doc.from_date), frappe.datetime.str_to_user(frm.doc.to_date)]),
				"blue", true
			);
		}
	},

	from_date(frm) {
		if (frm.doc.from_date && !frm.doc.to_date) {
			frm.set_value("to_date", frappe.datetime.month_end(frm.doc.from_date));
		}
	},

	to_date(frm) {
		if (frm.doc.to_date && !frm.doc.payroll_date) {
			frm.set_value("payroll_date", frm.doc.to_date);
		}
	},
});

frappe.ui.form.on("Driver Payroll Detail", {
	advance_recovery(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (flt(row.advance_recovery) > flt(row.outstanding_advance)) {
			frappe.msgprint(__("Recovery cannot exceed the outstanding advance of {0}.",
				[format_currency(row.outstanding_advance, frm.doc.currency)]));
			frappe.model.set_value(cdt, cdn, "advance_recovery", row.outstanding_advance);
			return;
		}
		frappe.model.set_value(cdt, cdn, "net_addition",
			flt(row.gross_earning) - flt(row.advance_recovery));
	},
});
