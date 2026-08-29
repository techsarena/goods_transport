frappe.query_reports["Trip Expense Analysis"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -3) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "trip", label: __("Trip"), fieldtype: "Link", options: "Transport Trip" },
		{
			fieldname: "group_by", label: __("Group By"), fieldtype: "Select",
			options: "Expense Type\nPayment Mode\nTrip\nVehicle\nDriver",
			default: "Expense Type",
		},
	],
};
