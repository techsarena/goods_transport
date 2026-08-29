frappe.query_reports["Pending POD"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "days_since", label: __("Min Days Open"), fieldtype: "Int", default: 0 },
	],
};
