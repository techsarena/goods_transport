// Surfaces the Employee link requirement and outstanding advances on Driver.
frappe.ui.form.on("Driver", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (!frm.doc.employee) {
			frm.dashboard.set_headline_alert(
				__("This Driver has no Employee record linked. Trip earnings cannot be paid through payroll until one is set."),
				"orange"
			);
		}

		frm.add_custom_button(__("Trip Earnings"), () => {
			frappe.set_route("List", "Driver Trip Earning", { driver: frm.doc.name });
		}, __("View"));

		frm.add_custom_button(__("Advance Recovery Status"), () => {
			frappe.set_route("query-report", "Driver Advance Recovery Status", { driver: frm.doc.name });
		}, __("View"));
	},
});
