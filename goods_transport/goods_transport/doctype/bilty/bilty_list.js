frappe.listview_settings["Bilty"] = {
	add_fields: ["status", "sales_invoice", "grand_total", "currency"],
	get_indicator(doc) {
		const map = {
			Draft: "red",
			Issued: "orange",
			"In Transit": "blue",
			Delivered: "purple",
			"POD Received": "green",
			Billed: "green",
			Closed: "grey",
			Cancelled: "grey",
		};
		return [__(doc.status || "Draft"), map[doc.status] || "grey", "status,=," + (doc.status || "Draft")];
	},
	onload(listview) {
		listview.page.add_action_item(__("Create Sales Invoice"), () => {
			const selected = listview.get_checked_items().map((d) => d.name);
			if (!selected.length) {
				frappe.msgprint(__("Select at least one Bilty."));
				return;
			}
			frappe.call({
				method: "goods_transport.goods_transport.services.billing.create_sales_invoice_from_bilties",
				args: { bilties: selected },
				freeze: true,
				freeze_message: __("Creating Sales Invoice..."),
				callback: (r) => {
					if (r.message) {
						frappe.set_route("Form", "Sales Invoice", r.message);
					}
				},
			});
		});
	},
};
