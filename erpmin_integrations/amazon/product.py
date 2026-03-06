import frappe
from erpmin_integrations.amazon.api import get_client


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
    from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
    settings = get_settings()

    payload = {
        "productType": "PRODUCT",
        "requirements": "LISTING",
        "attributes": {
            "item_name": [{"value": item.item_name, "language_tag": "en_IN"}],
            "externally_assigned_product_identifier": [
                {"type": "ean", "value": item.barcodes[0].barcode}
            ] if item.barcodes else [],
        },
    }

    try:
        client.post(
            f"/listings/2021-08-01/items/{settings.seller_id}/{sku}"
            f"?marketplaceIds={settings.marketplace_id}",
            payload,
        )
        frappe.db.set_value("Item", item_code, "custom_amazon_status", "Active")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"[Amazon] sync_item failed: {item_code}")
        frappe.db.set_value("Item", item_code, "custom_amazon_status", "Error")


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
