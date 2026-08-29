frappe.query_reports["Driver Advance Settlement"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "recipient_type", label: __("Recipient Type"), fieldtype: "Select", options: "\nDriver\nEmployee\nSupplier" },
		{ fieldname: "driver", label: __("Driver"), fieldtype: "Link", options: "Driver" },
		{ fieldname: "outstanding_only", label: __("Outstanding Only"), fieldtype: "Check" },
	],
};
