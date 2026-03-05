import frappe
from erpmin_integrations.amazon.api import get_client
from erpmin_integrations.amazon.feeds import build_inventory_feed, submit_feed, poll_feed
from erpmin_integrations.utils.inventory import get_available_qty

BATCH_SIZE = 100


def sync_all_inventory():
    client = get_client()
    if not client:
        return

    items = frappe.get_all(
        "Item",
        filters={"custom_sync_to_amazon": 1, "disabled": 0},
        fields=["name", "custom_amazon_sku"],
    )
    if not items:
        return

    feed_items = []
    for item in items:
        sku = item.custom_amazon_sku or item.name
        qty = get_available_qty(item.name)
        feed_items.append({"sku": sku, "qty": qty})

    # Submit in batches to avoid large feed documents
    for i in range(0, len(feed_items), BATCH_SIZE):
        batch = feed_items[i : i + BATCH_SIZE]
        _submit_inventory_batch(batch)


def _submit_inventory_batch(batch):
    xml_content = build_inventory_feed(batch)
    feed_id = submit_feed("POST_INVENTORY_AVAILABILITY_DATA", xml_content)
    if not feed_id:
        return

    result = poll_feed(feed_id)
    if result and result.get("processingStatus") != "DONE":
        frappe.log_error(
            f"Feed {feed_id} status: {result.get('processingStatus')}",
            "[Amazon] inventory feed did not complete successfully",
        )
    else:
        frappe.logger().info(f"[Amazon] inventory feed {feed_id} complete")
