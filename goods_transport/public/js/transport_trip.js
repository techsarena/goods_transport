// Adds driver-earning visibility to the Transport Trip form.
frappe.ui.form.on("Transport Trip", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.driver) return;

		frm.add_custom_button(
			__("Driver Earning"),
			() => {
				frappe.call({
					method: "goods_transport.goods_transport.services.earnings.generate_for_trip",
					args: { trip: frm.doc.name },
					freeze: true,
					freeze_message: __("Calculating driver earning..."),
					callback: (r) => {
						if (r.message) frappe.set_route("Form", "Driver Trip Earning", r.message);
					},
				});
			},
			__("Create")
		);

		frappe.db.get_value("Driver Trip Earning", { trip: frm.doc.name },
			["name", "total_earning", "status"], (r) => {
				if (!r || !r.name) return;
				frm.dashboard.add_indicator(
					__("Driver Earning: {0} ({1})", [
						format_currency(r.total_earning, frm.doc.currency),
						r.status,
					]),
					r.status === "Processed" ? "green" : "orange"
				);
			});
	},
});
