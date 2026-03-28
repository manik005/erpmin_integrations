import frappe
from frappe.utils import now_datetime
from erpmin_integrations.amazon.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
from erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    get_amazon_product_type,
)
from erpmin_integrations.amazon.attributes import (
    build_attributes,
    build_parent_attributes,
    build_child_attributes,
)
from erpmin_integrations.utils.cdn import get_public_urls_for_item


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

    # Template items (has_variants=1) are skipped — parent ASIN created lazily when a variant syncs
    if item.has_variants:
        return

    if item.variant_of:
        _sync_variant_item(item, client)
    else:
        _sync_flat_item(item, client)


def _sync_flat_item(item, client):
    """Sync a standalone (non-variant) item to Amazon."""
    sku = item.custom_amazon_sku or item.name
    settings = get_settings()

    product_type = (
        (item.custom_amazon_product_type or "").strip()
        or get_amazon_product_type(item.item_group)
        or "PRODUCT"
    )

    if product_type == "PRODUCT":
        frappe.logger().warning(
            f"[Amazon] Item {item.name} has no product type mapping. "
            "Using generic PRODUCT — listing may be rejected by SP-API."
        )

    public_base_url = getattr(settings, "public_base_url", "") or ""
    image_urls = get_public_urls_for_item(item, public_base_url)

    attributes = build_attributes(item, product_type, image_urls=image_urls)

    price = _get_item_price(item.name, getattr(settings, "default_price_list", None))
    has_price = price is not None and price > 0

    if has_price:
        attributes["purchasable_offer"] = [
            {
                "currency": "INR",
                "our_price": [{"schedule": [{"value_with_tax": price}]}],
                "marketplace_id": settings.marketplace_id,
            }
        ]

    payload = {
        "productType": product_type,
        "requirements": "LISTING" if has_price else "LISTING_PRODUCT_ONLY",
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
            item.name,
            {
                "custom_amazon_status": "Active",
                "custom_amazon_last_sync": now_datetime(),
                "custom_amazon_sync_error": "",
            },
        )
    except Exception as e:
        error_msg = str(e)[:500]
        frappe.log_error(frappe.get_traceback(), f"[Amazon] sync_item failed: {item.name}")
        frappe.db.set_value(
            "Item",
            item.name,
            {
                "custom_amazon_status": "Error",
                "custom_amazon_sync_error": error_msg,
            },
        )


def _sync_variant_item(item, client):
    """Sync a variant item. PUTs parent ASIN from template, then child ASIN."""
    settings = get_settings()
    template = frappe.get_doc("Item", item.variant_of)

    product_type = (
        (template.custom_amazon_product_type or "").strip()
        or get_amazon_product_type(template.item_group)
        or "PRODUCT"
    )

    parent_sku = template.custom_amazon_sku or template.name
    child_sku = item.custom_amazon_sku or item.name

    public_base_url = getattr(settings, "public_base_url", "") or ""
    template_image_urls = get_public_urls_for_item(template, public_base_url)
    item_image_urls = get_public_urls_for_item(item, public_base_url)

    # Step 1: PUT parent ASIN (always LISTING_PRODUCT_ONLY — not directly buyable)
    parent_attrs = build_parent_attributes(template, product_type, image_urls=template_image_urls)
    parent_url = (
        f"/listings/2021-08-01/items/{settings.seller_id}/{parent_sku}"
        f"?marketplaceIds={settings.marketplace_id}&productType={product_type}"
    )
    try:
        client.put_listing(parent_url, {
            "productType": product_type,
            "requirements": "LISTING_PRODUCT_ONLY",
            "attributes": parent_attrs,
        })
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"[Amazon] sync parent ASIN failed: {parent_sku}")
        frappe.db.set_value(
            "Item",
            template.name,
            {"custom_amazon_status": "Error", "custom_amazon_sync_error": f"Parent ASIN PUT failed: {parent_sku}"},
        )
        return  # Abort — don't sync child if parent failed

    # Step 2: PUT child ASIN with price + parentage relationship
    price = _get_item_price(item.name, getattr(settings, "default_price_list", None))
    has_price = price is not None and price > 0

    child_attrs = build_child_attributes(item, product_type, parent_sku=parent_sku, image_urls=item_image_urls)
    if has_price:
        child_attrs["purchasable_offer"] = [
            {
                "currency": "INR",
                "our_price": [{"schedule": [{"value_with_tax": price}]}],
                "marketplace_id": settings.marketplace_id,
            }
        ]

    child_url = (
        f"/listings/2021-08-01/items/{settings.seller_id}/{child_sku}"
        f"?marketplaceIds={settings.marketplace_id}&productType={product_type}"
    )

    try:
        client.put_listing(child_url, {
            "productType": product_type,
            "requirements": "LISTING" if has_price else "LISTING_PRODUCT_ONLY",
            "attributes": child_attrs,
        })
        frappe.db.set_value(
            "Item",
            item.name,
            {
                "custom_amazon_status": "Active",
                "custom_amazon_last_sync": now_datetime(),
                "custom_amazon_sync_error": "",
            },
        )
    except Exception as e:
        error_msg = str(e)[:500]
        frappe.log_error(frappe.get_traceback(), f"[Amazon] sync_variant failed: {item.name}")
        frappe.db.set_value(
            "Item",
            item.name,
            {
                "custom_amazon_status": "Error",
                "custom_amazon_sync_error": error_msg,
            },
        )


def _get_item_price(item_code: str, price_list: str | None) -> float | None:
    """Return selling price from Item Price for the given price list, or None."""
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
