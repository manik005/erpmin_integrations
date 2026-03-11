import frappe
from frappe.utils import now_datetime
from erpmin_integrations.amazon.api import get_client
from erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
from erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    get_amazon_product_type,
)
from erpmin_integrations.amazon.attributes import build_attributes


def on_item_save(doc, method=None):
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return
    if not doc.custom_sync_to_amazon:
        return
    frappe.enqueue(
        "erpmin_integrations.amazon.product.sync_item",
        item_code=doc.name,
        queue="short",
        enqueue_after_commit=True,
    )


def sync_item(item_code):
    """Sync a single item to Amazon via SP-API Listings API."""
    client = get_client()
    if not client:
        return

    item = frappe.get_doc("Item", item_code)
    if not item.custom_sync_to_amazon:
        return

    sku = item.custom_amazon_sku or item_code
    settings = get_settings()

    product_type = (
        (item.custom_amazon_product_type or "").strip()
        or get_amazon_product_type(item.item_group)
        or "PRODUCT"
    )

    if product_type == "PRODUCT":
        frappe.logger().warning(
            f"[Amazon] Item {item_code} has no product type mapping. "
            "Using generic PRODUCT — listing may be rejected by SP-API."
        )

    attributes = build_attributes(item, product_type)

    price = _get_item_price(item_code, getattr(settings, "default_price_list", None))
    if price is not None:
        attributes["purchasable_offer"] = [
            {
                "currency": "INR",
                "our_price": [{"schedule": [{"value_with_tax": price}]}],
                "marketplace_id": settings.marketplace_id,
            }
        ]

    payload = {
        "productType": product_type,
        "requirements": "LISTING",
        "attributes": attributes,
    }

    url = (
        f"/listings/2021-08-01/items/{settings.seller_id}/{sku}"
        f"?marketplaceIds={settings.marketplace_id}&productType={product_type}"
    )

    try:
        client.put_listing(url, payload)
        frappe.db.set_value(
            "Item",
            item_code,
            {
                "custom_amazon_status": "Active",
                "custom_amazon_last_sync": now_datetime(),
                "custom_amazon_sync_error": "",
            },
        )
    except Exception as e:
        error_msg = str(e)[:500]
        frappe.log_error(frappe.get_traceback(), f"[Amazon] sync_item failed: {item_code}")
        frappe.db.set_value(
            "Item",
            item_code,
            {
                "custom_amazon_status": "Error",
                "custom_amazon_sync_error": error_msg,
            },
        )


def _get_item_price(item_code: str, price_list: str | None) -> float | None:
    """Return selling price (with tax) from Item Price for the given price list, or None."""
    if not price_list:
        return None
    result = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        "price_list_rate",
    )
    if result is None:
        return None
    return float(result)


def full_product_sync():
    client = get_client()
    if not client:
        return

    items = frappe.get_all(
        "Item",
        filters={"custom_sync_to_amazon": 1, "disabled": 0},
        pluck="name",
    )
    for item_code in items:
        try:
            sync_item(item_code)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"[Amazon] full_product_sync failed: {item_code}"
            )
