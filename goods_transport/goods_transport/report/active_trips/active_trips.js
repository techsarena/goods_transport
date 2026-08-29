frappe.query_reports["Active Trips"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "transporter", label: __("Transporter"), fieldtype: "Link", options: "Supplier" },
	],
};
