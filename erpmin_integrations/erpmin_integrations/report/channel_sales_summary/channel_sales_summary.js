frappe.query_reports['Channel Sales Summary'] = {
    filters: [
        {
            fieldname: 'from_date',
            label: __('From Date'),
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: 'to_date',
            label: __('To Date'),
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: 'channel',
            label: __('Channel'),
            fieldtype: 'Select',
            options: '\nStore A\nStore B\nStore C\nOpenCart\nAmazon\nWholesale',
        },
    ],
};
