frappe.query_reports["Unbilled Bilties"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "billing_customer", label: __("Billing Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "to_date",
			label: __("Up To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
