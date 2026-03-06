"""
Amazon SP-API Feeds — build XML feed documents, submit, and poll until done.
Used for inventory and product updates in bulk.
"""
import time
import xml.etree.ElementTree as ET

import frappe
from erpmin_integrations.amazon.api import get_client, AmazonAPIError

FEEDS_API = "/feeds/2021-06-30"


def build_inventory_feed(items):
    """Build AmazonEnvelope XML for inventory quantity update.

    items: list of {"sku": str, "qty": int}
    Returns XML string.
    """
    root = ET.Element("AmazonEnvelope")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "amzn-envelope.xsd")

    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "DocumentVersion").text = "1.01"
    ET.SubElement(header, "MerchantIdentifier").text = "_"

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


def submit_feed(feed_type, content, content_type="text/xml; charset=UTF-8"):
    """Submit a feed document and return feed_id."""
    client = get_client()
    if not client:
        return None

    # Step 1: create feed document
    doc_resp = client.post(
        f"{FEEDS_API}/documents",
        {"contentType": content_type},
    )
    doc_id = doc_resp["feedDocumentId"]
    upload_url = doc_resp["url"]

    # Step 2: upload content
    import requests
    put_resp = requests.put(
        upload_url,
        data=content.encode("utf-8"),
        headers={"Content-Type": content_type},
        timeout=60,
    )
    put_resp.raise_for_status()

    # Step 3: create feed
    from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
    settings = get_settings()
    feed_resp = client.post(
        f"{FEEDS_API}/feeds",
        {
            "feedType": feed_type,
            "marketplaceIds": [settings.marketplace_id],
            "inputFeedDocumentId": doc_id,
        },
    )
    return feed_resp.get("feedId")


def poll_feed(feed_id, max_wait_seconds=300, interval=15):
    """Poll until feed is done. Returns final feed result dict or None on timeout."""
    client = get_client()
    if not client:
        return None

    elapsed = 0
    while elapsed < max_wait_seconds:
        result = client.get(f"{FEEDS_API}/feeds/{feed_id}")
        status = result.get("processingStatus")
        if status in ("DONE", "FATAL", "CANCELLED"):
            return result
        time.sleep(interval)
        elapsed += interval

    frappe.log_error(
        f"Feed {feed_id} did not complete within {max_wait_seconds}s",
        "[Amazon] feed timeout",
    )
    return None
