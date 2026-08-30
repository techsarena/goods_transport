frappe.ui.form.on("Transport Order", {
	setup(frm) {
		// Commodity must be a physical-cargo Item — filter picker to the
		// Cargo Items group and its descendants. Server-side validate() is
		// the actual enforcement; this is the UX hint.
		frm.set_query("commodity", () => ({
			query: "goods_transport.goods_transport.services.cargo.cargo_item_query",
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(
				__("Transport Trip"),
				() => {
					const d = new frappe.ui.Dialog({
						title: __("Create Trip for Order {0}", [frm.doc.name]),
						fields: [
							{
								label: __("Vehicle"),
								fieldname: "vehicle",
								fieldtype: "Link",
								options: "Vehicle",
								reqd: 1,
							},
							{
								label: __("Quantity Allocated"),
								fieldname: "quantity",
								fieldtype: "Float",
								description: __("Informational; used later by Bilties created under this Trip."),
							},
						],
						primary_action_label: __("Create Trip"),
						primary_action(values) {
							frappe.call({
								method: "goods_transport.goods_transport.services.operations.create_trip_from_order",
								args: {
									transport_order: frm.doc.name,
									vehicle: values.vehicle,
									quantity: values.quantity,
								},
								freeze: true,
								callback: (r) => {
									if (r.message) {
										d.hide();
										frappe.set_route("Form", "Transport Trip", r.message);
									}
								},
							});
						},
					});
					d.show();
				},
				__("Create"),
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Bilties under this Order"),
				() => frappe.set_route("List", "Bilty", { transport_order: frm.doc.name }),
				__("View"),
			);
		}
	},
});
