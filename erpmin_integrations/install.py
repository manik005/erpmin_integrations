import frappe


def after_install():
    _add_item_custom_fields()
    _add_sales_order_custom_fields()
    _add_sales_order_item_custom_fields()
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
        {
            "dt": "Item",
            "fieldname": "custom_amazon_product_type",
            "label": "Amazon Product Type (Override)",
            "fieldtype": "Data",
            "insert_after": "custom_discontinued_date",
            "description": "Overrides the group-level Amazon product type",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_brand",
            "label": "Amazon Brand",
            "fieldtype": "Data",
            "insert_after": "custom_amazon_product_type",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_color",
            "label": "Amazon Color",
            "fieldtype": "Data",
            "insert_after": "custom_amazon_brand",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_size",
            "label": "Amazon Size",
            "fieldtype": "Data",
            "insert_after": "custom_amazon_color",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_bullet_points",
            "label": "Amazon Bullet Points",
            "fieldtype": "Small Text",
            "insert_after": "custom_amazon_size",
            "description": "One bullet point per line. Maximum 5 lines.",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_description",
            "label": "Amazon Description",
            "fieldtype": "Long Text",
            "insert_after": "custom_amazon_bullet_points",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_last_sync",
            "label": "Amazon Last Synced At",
            "fieldtype": "Datetime",
            "insert_after": "custom_amazon_status",
            "read_only": 1,
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_sync_error",
            "label": "Amazon Last Sync Error",
            "fieldtype": "Small Text",
            "insert_after": "custom_amazon_last_sync",
            "read_only": 1,
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


def _add_sales_order_item_custom_fields():
    fields = [
        {
            "dt": "Sales Order Item",
            "fieldname": "custom_amazon_order_item_id",
            "label": "Amazon Order Item ID",
            "fieldtype": "Data",
            "insert_after": "item_code",
            "read_only": 1,
        },
    ]
    _save_fields(fields)


def _save_fields(field_list):
    for field_def in field_list:
        dt = field_def.get("dt")
        field_data = {k: v for k, v in field_def.items() if k != "dt"}
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field_data["fieldname"]}):
            continue
        custom_field = frappe.new_doc("Custom Field")
        custom_field.dt = dt
        custom_field.update(field_data)
        custom_field.insert(ignore_permissions=True)
