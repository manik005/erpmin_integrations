"""
Channel Sales Summary report.

Shows sales performance broken down by channel (Store A/B/C, OpenCart, Amazon, Wholesale)
for a given date range. Based on submitted Sales Orders.

Filters: from_date, to_date, channel (optional)
"""
import frappe
from frappe import _
from frappe.utils import today, get_first_day, get_last_day


def execute(filters=None):
    filters = frappe._dict(filters or {})
    _set_filter_defaults(filters)
    columns = _get_columns()
    data = _get_data(filters)
    chart = _get_chart(data)
    return columns, data, None, chart


def _set_filter_defaults(filters):
    if not filters.from_date:
        filters.from_date = str(get_first_day(today()))
    if not filters.to_date:
        filters.to_date = str(get_last_day(today()))


def _get_columns():
    return [
        {
            "fieldname": "channel",
            "label": _("Channel"),
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "fieldname": "order_count",
            "label": _("Orders"),
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "fieldname": "total_qty",
            "label": _("Total Qty"),
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "fieldname": "total_amount",
            "label": _("Net Amount (₹)"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "fieldname": "total_tax",
            "label": _("Tax (₹)"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "fieldname": "grand_total",
            "label": _("Grand Total (₹)"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "fieldname": "avg_order_value",
            "label": _("Avg Order Value (₹)"),
            "fieldtype": "Currency",
            "options": "currency",
            "width": 170,
        },
    ]


def _get_data(filters):
    conditions = ["so.docstatus = 1", "so.transaction_date BETWEEN %(from_date)s AND %(to_date)s"]
    if filters.get("channel"):
        conditions.append("so.custom_channel = %(channel)s")

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(so.custom_channel, ''), 'Unassigned') AS channel,
            COUNT(DISTINCT so.name)                               AS order_count,
            SUM(soi.qty)                                          AS total_qty,
            SUM(so.total)                                         AS total_amount,
            SUM(so.total_taxes_and_charges)                       AS total_tax,
            SUM(so.grand_total)                                   AS grand_total,
            ROUND(SUM(so.grand_total) / COUNT(DISTINCT so.name), 2) AS avg_order_value
        FROM `tabSales Order` so
        JOIN `tabSales Order Item` soi ON soi.parent = so.name
        WHERE {where}
        GROUP BY channel
        ORDER BY grand_total DESC
        """,
        filters,
        as_dict=True,
    )

    # Attach currency for the Currency fieldtype columns
    company_currency = frappe.defaults.get_global_default("currency") or "INR"
    for row in rows:
        row["currency"] = company_currency

    return rows


def _get_chart(data):
    if not data:
        return None

    # Exclude the Total row that Frappe auto-appends (no channel key)
    chart_data = [r for r in data if r.get("channel")]

    return {
        "data": {
            "labels": [r["channel"] for r in chart_data],
            "datasets": [
                {
                    "name": _("Grand Total (₹)"),
                    "values": [r["grand_total"] for r in chart_data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#5e64ff"],
    }
