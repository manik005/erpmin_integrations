import frappe


def after_install():
    _add_item_custom_fields()
    _add_item_variant_mode_field()
    _add_item_attribute_custom_fields()
    _add_sales_order_custom_fields()
    _add_sales_order_item_custom_fields()
    _add_customer_custom_fields()
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


def _add_item_variant_mode_field():
    fields = [
        {
            "dt": "Item",
            "fieldname": "custom_opencart_variant_mode",
            "label": "OpenCart Variant Mode",
            "fieldtype": "Select",
            "options": "\nGroup as options\nIndividual products",
            "default": "Group as options",
            "insert_after": "custom_sync_to_amazon",
            "description": "Group as options: variants appear as Size/Color selectors (apparel). Individual products: each variant is its own OpenCart product (perfumes).",
        },
    ]
    _save_fields(fields)


def _add_item_attribute_custom_fields():
    fields = [
        {
            "dt": "Item Attribute",
            "fieldname": "custom_opencart_role",
            "label": "OpenCart Role",
            "fieldtype": "Select",
            "options": "\nOption\nFilter\nNone",
            "default": "Option",
            "insert_after": "attribute_name",
            "description": "Option = customer selects when buying. Filter = sidebar filter. None = skip.",
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


def _add_customer_custom_fields():
    fields = [
        {
            "dt": "Customer",
            "fieldname": "custom_source_channel",
            "label": "Source Channel",
            "fieldtype": "Select",
            "options": "\nAmazon\nOpenCart\nPOS",
            "insert_after": "customer_group",
            "read_only": 1,
        },
    ]
    _save_fields(fields)


def set_attribute_roles():
    """Set custom_opencart_role on known Item Attributes. Safe to re-run.

    Not called from after_install — run manually once via:
        bench --site erp.local execute erpmin_integrations.install.set_attribute_roles
    """
    option_attrs = ["Size", "Color", "Age Group"]
    filter_attrs = ["Material", "Neck Type", "Sleeve", "Fit", "Gender", "Sport"]

    for name in option_attrs:
        if frappe.db.exists("Item Attribute", name):
            frappe.db.set_value("Item Attribute", name, "custom_opencart_role", "Option")

    for name in filter_attrs:
        if frappe.db.exists("Item Attribute", name):
            frappe.db.set_value("Item Attribute", name, "custom_opencart_role", "Filter")

    frappe.db.commit()


def set_perfume_variant_modes():
    """Set custom_opencart_variant_mode = Individual products on perfume templates. Safe to re-run.

    Not called from after_install — run manually once via:
        bench --site erp.local execute erpmin_integrations.install.set_perfume_variant_modes
    """
    perfume_templates = ["Perfume - Spray", "Perfume - Pocket", "Perfume - Roll On"]

    for name in perfume_templates:
        if frappe.db.exists("Item", name):
            frappe.db.set_value("Item", name, "custom_opencart_variant_mode", "Individual products")

    frappe.db.commit()


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
