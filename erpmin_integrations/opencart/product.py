import frappe
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings
from erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    get_category_id,
)


def on_item_save(doc, method=None):
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return
    if not doc.custom_sync_to_opencart:
        return
    frappe.enqueue(
        "erpmin_integrations.opencart.product.sync_item",
        item_code=doc.name,
        queue="short",
        enqueue_after_commit=True,
    )


def sync_item(item_code):
    client = get_client()
    if not client:
        return

    item = frappe.get_doc("Item", item_code)
    if not item.custom_sync_to_opencart:
        return

    settings = get_settings()
    price = _get_item_price(item_code, settings.default_price_list)
    category_id = get_category_id(item.item_group)

    product_data = {
        "sku": item_code,
        "model": item_code,
        "name": {"1": item.item_name},
        "description": {"1": item.description or ""},
        "price": price,
        "quantity": 0,
        "status": 1 if not item.disabled else 0,
        "category_id": [category_id] if category_id else [],
    }

    existing = client.get_product_by_sku(item_code)
    if existing:
        product_id = existing.get("product_id")
        client.update_product(product_id, product_data)
        if item.custom_opencart_id != product_id:
            frappe.db.set_value("Item", item_code, "custom_opencart_id", product_id)
    else:
        result = client.create_product(product_data)
        product_id = result.get("product_id")
        if product_id:
            frappe.db.set_value("Item", item_code, "custom_opencart_id", product_id)

    frappe.logger().info(f"[OpenCart] Synced product: {item_code}")


def full_product_sync():
    client = get_client()
    if not client:
        return

    items = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "disabled": 0},
        pluck="name",
    )
    for item_code in items:
        try:
            sync_item(item_code)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"[OpenCart] full_product_sync failed: {item_code}"
            )


def _get_item_price(item_code, price_list):
    price = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list},
        "price_list_rate",
    )
    return float(price or 0)
