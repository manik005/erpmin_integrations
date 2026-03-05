import frappe


def after_install():
    _add_item_custom_fields()
    _add_sales_order_custom_fields()
    frappe.db.commit()


def _add_item_custom_fields():
    fields = [
        {
            "dt": "Item",
            "fieldname": "custom_opencart_id",
            "label": "OpenCart Product ID",
            "fieldtype": "Int",
            "insert_after": "item_code",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_sku",
            "label": "Amazon SKU",
            "fieldtype": "Data",
            "insert_after": "custom_opencart_id",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_status",
            "label": "Amazon Status",
            "fieldtype": "Select",
            "options": "\nActive\nInactive\nError",
            "insert_after": "custom_amazon_sku",
        },
        {
            "dt": "Item",
            "fieldname": "custom_sync_to_opencart",
            "label": "Sync to OpenCart",
            "fieldtype": "Check",
            "insert_after": "custom_amazon_status",
        },
        {
            "dt": "Item",
            "fieldname": "custom_sync_to_amazon",
            "label": "Sync to Amazon",
            "fieldtype": "Check",
            "insert_after": "custom_sync_to_opencart",
        },
        {
            "dt": "Item",
            "fieldname": "custom_discontinued_date",
            "label": "Discontinued Date",
            "fieldtype": "Date",
            "insert_after": "custom_sync_to_amazon",
        },
    ]
    _save_fields(fields)


def _add_sales_order_custom_fields():
    fields = [
        {
            "dt": "Sales Order",
            "fieldname": "custom_channel",
            "label": "Channel",
            "fieldtype": "Select",
            "options": "\nStore A\nStore B\nStore C\nOpenCart\nAmazon\nWholesale",
            "insert_after": "customer",
        },
        {
            "dt": "Sales Order",
            "fieldname": "custom_marketplace_order_id",
            "label": "Marketplace Order ID",
            "fieldtype": "Data",
            "insert_after": "custom_channel",
        },
    ]
    _save_fields(fields)


def _save_fields(field_list):
    for field_def in field_list:
        dt = field_def.pop("dt")
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field_def["fieldname"]}):
            continue
        custom_field = frappe.new_doc("Custom Field")
        custom_field.dt = dt
        custom_field.update(field_def)
        custom_field.insert(ignore_permissions=True)
