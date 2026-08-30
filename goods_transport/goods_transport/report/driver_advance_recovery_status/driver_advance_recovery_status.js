frappe.query_reports["Driver Advance Recovery Status"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
		  default: frappe.defaults.get_user_default("Company"), reqd: 1 },
		{ fieldname: "driver", label: __("Driver"), fieldtype: "Link", options: "Driver" },
	],
};
