import frappe


def after_install():
    _add_item_custom_fields()
    _add_item_variant_mode_field()
    _add_item_product_images_field()
    _add_item_attribute_custom_fields()
    _add_sales_order_custom_fields()
    _add_sales_order_item_custom_fields()
    _add_customer_custom_fields()
    migrate_item_fields_to_tabs()
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


def _add_item_product_images_field():
    fields = [
        {
            "dt": "Item",
            "fieldname": "custom_product_images",
            "label": "Product Images",
            "fieldtype": "Table",
            "options": "Item Product Image",
            "insert_after": "custom_opencart_name",
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
        {
            "dt": "Sales Order",
            "fieldname": "custom_shipping_method",
            "label": "Shipping Method",
            "fieldtype": "Data",
            "insert_after": "custom_marketplace_order_id",
            "read_only": 1,
            "description": "Shipping method selected by the customer in OpenCart",
        },
        {
            "dt": "Sales Order",
            "fieldname": "custom_amazon_acknowledged_at",
            "label": "Amazon Acknowledged At",
            "fieldtype": "Datetime",
            "insert_after": "custom_shipping_method",
            "read_only": 1,
            "description": "Timestamp when this order was acknowledged (imported into ERPNext) from Amazon",
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


def migrate_item_fields_to_tabs():
    """Add OpenCart and Amazon tabs to the Item form and reorganise custom fields under them.

    Safe to re-run. Creates Tab Break + channel-name fields if missing, then
    updates insert_after on all existing Item custom fields to achieve the layout:

        [OpenCart tab]
          OpenCart Name, OpenCart Product ID, Sync to OpenCart, OpenCart Variant Mode

        [Amazon tab]
          Amazon Title, Amazon SKU, Sync to Amazon, Amazon Status, Amazon Last Synced At,
          Amazon Last Sync Error, Amazon Product Type (Override), Amazon Brand, Amazon Color,
          Amazon Size, Amazon Bullet Points, Amazon Description

    Run once on existing installations:
        bench --site erp.local execute erpmin_integrations.install.migrate_item_fields_to_tabs
    """
    # Step 1: add new fields (idempotent — skipped if already exist)
    _save_fields([
        {
            "dt": "Item",
            "fieldname": "custom_tab_opencart",
            "label": "OpenCart",
            "fieldtype": "Tab Break",
            "insert_after": "total_projected_qty",
        },
        {
            "dt": "Item",
            "fieldname": "custom_opencart_name",
            "label": "OpenCart Name",
            "fieldtype": "Data",
            "insert_after": "custom_tab_opencart",
            "description": "Product name shown on OpenCart. Falls back to Item Name if empty.",
        },
        {
            "dt": "Item",
            "fieldname": "custom_product_images",
            "label": "Product Images",
            "fieldtype": "Table",
            "options": "Item Product Image",
            "insert_after": "custom_opencart_name",
        },
        {
            "dt": "Item",
            "fieldname": "custom_tab_amazon",
            "label": "Amazon",
            "fieldtype": "Tab Break",
            "insert_after": "custom_opencart_variant_mode",
        },
        {
            "dt": "Item",
            "fieldname": "custom_amazon_title",
            "label": "Amazon Title",
            "fieldtype": "Data",
            "insert_after": "custom_tab_amazon",
            "description": "Listing title sent to Amazon. Falls back to Item Name if empty.",
        },
    ])

    # Step 2: update insert_after on existing fields to put them in the right tabs
    reorder = [
        # Details tab — anchor after 'disabled' (stays in native Details tab).
        # Anchoring to item_code caused the entire Details tab content to be
        # pulled into the Amazon tab because our Tab Breaks interrupted the chain.
        ("custom_discontinued_date",     "disabled"),
        # Tab Breaks — anchor after the last native Item field so our custom tabs
        # appear at the END of the tab bar (after Details, Inventory, Variants, etc.)
        ("custom_tab_opencart",          "total_projected_qty"),
        # OpenCart tab
        ("custom_product_images",        "custom_opencart_name"),
        ("custom_opencart_id",           "custom_product_images"),
        ("custom_sync_to_opencart",      "custom_opencart_id"),
        ("custom_opencart_variant_mode", "custom_sync_to_opencart"),
        # Amazon tab
        ("custom_amazon_sku",            "custom_amazon_title"),
        ("custom_sync_to_amazon",        "custom_amazon_sku"),
        ("custom_amazon_status",         "custom_sync_to_amazon"),
        ("custom_amazon_last_sync",      "custom_amazon_status"),
        ("custom_amazon_sync_error",     "custom_amazon_last_sync"),
        ("custom_amazon_product_type",   "custom_amazon_sync_error"),
        ("custom_amazon_brand",          "custom_amazon_product_type"),
        ("custom_amazon_color",          "custom_amazon_brand"),
        ("custom_amazon_size",           "custom_amazon_color"),
        ("custom_amazon_bullet_points",  "custom_amazon_size"),
        ("custom_amazon_description",    "custom_amazon_bullet_points"),
    ]

    for fieldname, insert_after in reorder:
        cf_name = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": fieldname})
        if cf_name:
            frappe.db.set_value("Custom Field", cf_name, "insert_after", insert_after)

    frappe.db.commit()
    frappe.logger().info("[install] Item custom fields reorganised into OpenCart / Amazon tabs")


def debug_field_order():
    """Print all custom Item fields and their insert_after values for debugging tab layout."""
    rows = frappe.db.sql("""
        SELECT fieldname, label, fieldtype, insert_after
        FROM `tabCustom Field`
        WHERE dt='Item'
        ORDER BY fieldname
    """, as_dict=True)
    for r in rows:
        print(r.fieldname, "|", r.fieldtype, "| after:", r.insert_after)


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
