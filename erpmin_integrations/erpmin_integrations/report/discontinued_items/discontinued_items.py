"""
Discontinued Items report.

Lists all items that have a custom_discontinued_date set, showing current
stock levels across warehouses and sync channel flags.

Filters:
  - as_of_date  — show items discontinued on or before this date (default: today)
  - include_future — also show items with future discontinuation dates
  - channel — filter to items synced to a specific channel
"""
import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.as_of_date:
        filters.as_of_date = today()
    columns = _get_columns()
    data = _get_data(filters)
    return columns, data


def _get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 160,
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 140,
        },
        {
            "fieldname": "custom_discontinued_date",
            "label": _("Discontinued Date"),
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "fieldname": "days_since_discontinued",
            "label": _("Days Since"),
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "fieldname": "actual_qty",
            "label": _("Stock on Hand"),
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "fieldname": "reserved_qty",
            "label": _("Reserved Qty"),
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "fieldname": "available_qty",
            "label": _("Available Qty"),
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 160,
        },
        {
            "fieldname": "sync_to_opencart",
            "label": _("OpenCart"),
            "fieldtype": "Check",
            "width": 90,
        },
        {
            "fieldname": "sync_to_amazon",
            "label": _("Amazon"),
            "fieldtype": "Check",
            "width": 80,
        },
        {
            "fieldname": "disabled",
            "label": _("Disabled"),
            "fieldtype": "Check",
            "width": 80,
        },
    ]


def _get_data(filters):
    conditions = ["i.custom_discontinued_date IS NOT NULL"]

    if filters.get("include_future"):
        # All items with any discontinued date
        pass
    else:
        conditions.append("i.custom_discontinued_date <= %(as_of_date)s")

    if filters.get("channel") == "OpenCart":
        conditions.append("i.custom_sync_to_opencart = 1")
    elif filters.get("channel") == "Amazon":
        conditions.append("i.custom_sync_to_amazon = 1")

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            i.name                                              AS item_code,
            i.item_name,
            i.item_group,
            i.custom_discontinued_date,
            DATEDIFF(%(as_of_date)s, i.custom_discontinued_date) AS days_since_discontinued,
            COALESCE(b.actual_qty, 0)                           AS actual_qty,
            COALESCE(b.reserved_qty, 0)                         AS reserved_qty,
            COALESCE(b.actual_qty - b.reserved_qty, 0)          AS available_qty,
            b.warehouse,
            i.custom_sync_to_opencart                           AS sync_to_opencart,
            i.custom_sync_to_amazon                             AS sync_to_amazon,
            i.disabled
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.name
        WHERE {where}
        ORDER BY i.custom_discontinued_date DESC, i.name
        """,
        {"as_of_date": filters.as_of_date},
        as_dict=True,
    )

    return rows
