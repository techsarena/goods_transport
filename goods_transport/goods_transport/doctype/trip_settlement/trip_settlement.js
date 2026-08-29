frappe.ui.form.on("Trip Settlement", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Refresh From Source"), () => {
				frm.trigger("do_refresh");
			});
		}
		if (frm.doc.trip) {
			frm.add_custom_button(
				__("Trip"),
				() => frappe.set_route("Form", "Transport Trip", frm.doc.trip),
				__("View"),
			);
		}
	},
	do_refresh(frm) {
		frappe.call({
			doc: frm.doc,
			method: "refresh_from_source",
			callback: () => {
				frm.dirty();
				frm.save();
			},
		});
	},
});
