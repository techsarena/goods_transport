frappe.query_reports["Transport Order Status"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "status", label: __("Status"), fieldtype: "Select",
			options: "\nDraft\nConfirmed\nPartially Dispatched\nFully Dispatched\nDelivered\nClosed\nCancelled",
		},
		{ fieldname: "open_only", label: __("Open Only"), fieldtype: "Check", default: 1 },
	],
};
