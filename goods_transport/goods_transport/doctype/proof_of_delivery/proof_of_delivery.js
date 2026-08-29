frappe.ui.form.on("Proof of Delivery", {
	bilty(frm) {
		if (frm.doc.bilty) {
			frappe.db.get_value("Bilty", frm.doc.bilty, "total_quantity").then((r) => {
				if (r && r.message) {
					frm.set_value("delivered_quantity", r.message.total_quantity);
				}
			});
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Bilty"), () => frappe.set_route("Form", "Bilty", frm.doc.bilty), __("View"));
			if (frm.doc.trip) {
				frm.add_custom_button(
					__("Trip"),
					() => frappe.set_route("Form", "Transport Trip", frm.doc.trip),
					__("View"),
				);
			}
		}
	},
});
