"""
Amazon SP-API Feeds — build XML feed documents, submit, and record to Amazon Feed Log.
Feed status is polled asynchronously by check_pending_feeds (called by scheduler).
"""
import xml.etree.ElementTree as ET

import frappe
import requests
from frappe.utils import now_datetime
from erpmin_integrations.amazon.api import get_client, AmazonAPIError
from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings

FEEDS_API = "/feeds/2021-06-30"
_PENDING_STATUSES = ("IN_QUEUE", "IN_PROGRESS")
_TERMINAL_STATUSES = ("DONE", "FATAL", "CANCELLED")


def build_inventory_feed(items, seller_id: str) -> str:
    """Build AmazonEnvelope XML for inventory quantity update.

    Args:
        items: list of {"sku": str, "qty": int}
        seller_id: Amazon Seller ID (used as MerchantIdentifier)

    Returns:
        XML string.
    """
    root = ET.Element("AmazonEnvelope")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")

    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "DocumentVersion").text = "1.01"
    ET.SubElement(header, "MerchantIdentifier").text = seller_id

    ET.SubElement(root, "MessageType").text = "Inventory"

    for i, item in enumerate(items, start=1):
        msg = ET.SubElement(root, "Message")
        ET.SubElement(msg, "MessageID").text = str(i)
        ET.SubElement(msg, "OperationType").text = "Update"

        inv = ET.SubElement(msg, "Inventory")
        ET.SubElement(inv, "SKU").text = item["sku"]
        ET.SubElement(inv, "Quantity").text = str(int(item["qty"]))
        ET.SubElement(inv, "FulfillmentLatency").text = "3"

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def submit_feed(
    feed_type: str,
    content: str,
    item_count: int = 0,
    content_type: str = "text/xml; charset=UTF-8",
) -> str | None:
    """Submit a feed document. Saves an Amazon Feed Log record and returns feed_id.

    Does NOT poll. Polling is handled by check_pending_feeds().
    """
    client = get_client()
    if not client:
        return None

    settings = get_settings()

    # Step 1: create feed document slot
    doc_resp = client.post(f"{FEEDS_API}/documents", {"contentType": content_type})
    doc_id = doc_resp["feedDocumentId"]
    upload_url = doc_resp["url"]

    # Step 2: upload content to pre-signed S3 URL
    put_resp = requests.put(
        upload_url,
        data=content.encode("utf-8"),
        headers={"Content-Type": content_type},
        timeout=60,
    )
    put_resp.raise_for_status()

    # Step 3: create feed
    feed_resp = client.post(
        f"{FEEDS_API}/feeds",
        {
            "feedType": feed_type,
            "marketplaceIds": [settings.marketplace_id],
            "inputFeedDocumentId": doc_id,
        },
    )
    feed_id = feed_resp.get("feedId")
    if not feed_id:
        frappe.log_error(f"SP-API did not return a feedId: {feed_resp}", "[Amazon] submit_feed")
        return None

    # Record for async polling
    log = frappe.new_doc("Amazon Feed Log")
    log.feed_id = feed_id
    log.feed_type = feed_type
    log.status = "IN_QUEUE"
    log.item_count = item_count
    log.submitted_at = now_datetime()
    log.insert(ignore_permissions=True)

    return feed_id


def check_pending_feeds():
    """Scheduler job (*/5 * * * *): poll IN_QUEUE/IN_PROGRESS feeds and update status."""
    client = get_client()
    if not client:
        return

    pending = frappe.get_all(
        "Amazon Feed Log",
        filters={"status": ["in", list(_PENDING_STATUSES)]},
        fields=["name", "feed_id", "submitted_at"],
        limit=50,
    )

    from frappe.utils import time_diff_in_seconds
    now = now_datetime()

    for log in pending:
        try:
            result = client.get(f"{FEEDS_API}/feeds/{log.feed_id}")
            raw_status = result.get("processingStatus", "IN_QUEUE")
            _ALL_KNOWN_STATUSES = _PENDING_STATUSES + _TERMINAL_STATUSES
            if raw_status not in _ALL_KNOWN_STATUSES:
                frappe.logger().warning(
                    f"[Amazon] Feed {log.feed_id} returned unknown status '{raw_status}'. Skipping update."
                )
                continue
            status = raw_status

            update = {"status": status}
            if status in _TERMINAL_STATUSES:
                update["resolved_at"] = now
                if status == "FATAL":
                    update["error_message"] = str(result)
                    frappe.log_error(
                        f"Feed {log.feed_id} FATAL: {result}",
                        "[Amazon] feed processing failed",
                    )

            # Mark timed-out feeds (> 2 hours)
            elif time_diff_in_seconds(now, log.submitted_at) > 7200:
                update["status"] = "TIMEOUT"
                update["resolved_at"] = now
                frappe.log_error(
                    f"Feed {log.feed_id} timed out after 2 hours",
                    "[Amazon] feed timeout",
                )

            frappe.db.set_value("Amazon Feed Log", log.name, update)

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"[Amazon] check_pending_feeds error for {log.feed_id}",
            )

    frappe.db.commit()
