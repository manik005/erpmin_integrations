frappe.query_reports['Discontinued Items'] = {
    filters: [
        {
            fieldname: 'as_of_date',
            label: __('As Of Date'),
            fieldtype: 'Date',
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: 'include_future',
            label: __('Include Future Discontinuations'),
            fieldtype: 'Check',
            default: 0,
        },
        {
            fieldname: 'channel',
            label: __('Channel'),
            fieldtype: 'Select',
            options: '\nOpenCart\nAmazon',
        },
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Highlight items still in stock after discontinuation in orange
        if (column.fieldname === 'available_qty' && data && data.available_qty > 0) {
            value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
        }

        // Highlight still-enabled items that are discontinued in red
        if (column.fieldname === 'disabled' && data && !data.disabled) {
            value = `<span style="color: red;">Not Disabled</span>`;
        }

        return value;
    },
};
