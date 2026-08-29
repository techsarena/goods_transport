frappe.ui.form.on("Bilty", {
	refresh(frm) {
		if (
			frm.doc.docstatus === 1 &&
			frm.doc.pod_required &&
			frm.doc.pod_status === "Pending"
		) {
			frm.add_custom_button(
				__("Record POD"),
				() => {
					frappe.prompt(
						[
							{
								fieldname: "delivered_quantity",
								label: __("Delivered Quantity"),
								fieldtype: "Float",
								default: frm.doc.total_quantity,
								reqd: 1,
							},
							{ fieldname: "receiver_name", label: __("Receiver Name"), fieldtype: "Data", reqd: 1 },
						],
						(v) => {
							frappe.call({
								method: "goods_transport.goods_transport.services.operations.create_pod_from_bilty",
								args: {
									bilty: frm.doc.name,
									delivered_quantity: v.delivered_quantity,
									receiver_name: v.receiver_name,
								},
								freeze: true,
								callback: (r) => {
									if (r.message) {
										frappe.msgprint(__("POD {0} created and submitted.", [r.message]));
										frm.reload_doc();
									}
								},
							});
						},
						__("Record Proof of Delivery"),
					);
				},
				__("Actions"),
			);
		}
		if (frm.doc.docstatus === 1 && !frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => {
					frappe.call({
						method: "goods_transport.goods_transport.services.billing.create_sales_invoice_from_bilties",
						args: { bilties: [frm.doc.name] },
						freeze: true,
						freeze_message: __("Creating Sales Invoice..."),
						callback: (r) => {
							if (r.message) {
								frappe.set_route("Form", "Sales Invoice", r.message);
							}
						},
					});
				},
				__("Create"),
			);
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice),
				__("View"),
			);
		}
	},
});
