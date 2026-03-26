import frappe
from frappe.utils import now_datetime, add_days, today, get_datetime
from erpmin_integrations.amazon.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
from erpmin_integrations.customer import get_or_create_customer


def import_orders():
    """Poll Amazon SP-API for new orders across all pages and enqueue each for processing."""
    client = get_client()
    if not client:
        return

    settings = get_settings()
    last_sync = settings.last_order_sync_time

    if last_sync:
        created_after = get_datetime(last_sync).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        from datetime import datetime, timedelta, timezone
        created_after = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    sync_start = now_datetime()
    enqueued = 0

    try:
        response = client.get_orders(created_after)
        while True:
            payload = response.get("payload", {})
            for amz_order in payload.get("Orders", []):
                frappe.enqueue(
                    "erpmin_integrations.amazon.order._process_order_job",
                    amz_order=amz_order,
                    queue="short",
                    enqueue_after_commit=True,
                )
                enqueued += 1

            next_token = payload.get("NextToken")
            if not next_token:
                break
            response = client.get_orders_next_page(next_token)

        frappe.logger().info(f"[Amazon] Enqueued {enqueued} orders for processing")
    finally:
        frappe.db.set_value(
            "Amazon Settings", "Amazon Settings", "last_order_sync_time", sync_start
        )
        frappe.db.commit()


def _process_order_job(amz_order: dict):
    """Queue job: create a Sales Order for a single Amazon order."""
    settings = get_settings()
    order_id = amz_order.get("AmazonOrderId")
    try:
        client = get_client()
        _create_sales_order(client, amz_order, settings)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[Amazon] order import failed: {order_id}",
        )


def _create_sales_order(client, amz_order, settings):
    order_id = amz_order.get("AmazonOrderId")

    if frappe.db.exists("Sales Order", {"custom_marketplace_order_id": order_id}):
        return

    order_status = amz_order.get("OrderStatus", "")
    if order_status not in ("Unshipped", "PartiallyShipped", "Pending"):
        return

    items_resp = client.get_order_items(order_id)
    order_items = items_resp.get("payload", {}).get("OrderItems", [])
    if not order_items:
        return

    customer_data = _normalize_customer_data(amz_order)
    customer = get_or_create_customer(customer_data)

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.custom_channel = "Amazon"
    so.custom_marketplace_order_id = order_id
    so.delivery_date = add_days(today(), 3)
    so.set_warehouse = settings.default_warehouse

    for oi in order_items:
        sku = oi.get("SellerSKU") or oi.get("ASIN")
        item_code = _resolve_item_code(sku)
        if not item_code:
            frappe.logger().warning(f"[Amazon] Item not found for SKU: {sku}, order: {order_id}")
            continue

        qty = float(oi.get("QuantityOrdered", 1))
        price_data = oi.get("ItemPrice", {})
        amount = float(price_data.get("Amount", 0))
        rate = amount / qty if qty else 0

        so.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "rate": rate,
                "warehouse": so.set_warehouse,
                "custom_amazon_order_item_id": oi.get("OrderItemId", ""),
            },
        )

    if not so.items:
        frappe.logger().warning(f"[Amazon] No valid items for order {order_id}, skipping.")
        return

    so.insert(ignore_permissions=True)

    try:
        so.submit()
        frappe.logger().info(f"[Amazon] Imported order {order_id} → {so.name}")
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[Amazon] SO {so.name} insert OK but submit failed for order {order_id}. "
            "Review and submit manually.",
        )


def sync_order_statuses():
    """Poll Amazon for recently cancelled orders and cancel matching ERPNext Sales Orders."""
    client = get_client()
    if not client:
        return

    settings = get_settings()
    last_sync = settings.last_status_sync_time

    if last_sync:
        updated_after = get_datetime(last_sync).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        from datetime import datetime, timedelta, timezone
        updated_after = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    sync_start = now_datetime()

    try:
        response = client.get_orders_updated_after(updated_after, statuses=["Cancelled"])
        orders = response.get("payload", {}).get("Orders", [])

        for amz_order in orders:
            order_id = amz_order.get("AmazonOrderId")
            if amz_order.get("OrderStatus") != "Cancelled":
                continue
            try:
                _cancel_sales_order(order_id)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"[Amazon] order cancellation failed: {order_id}",
                )
    finally:
        frappe.db.set_value(
            "Amazon Settings", "Amazon Settings", "last_status_sync_time", sync_start
        )
        frappe.db.commit()


def _cancel_sales_order(amazon_order_id: str):
    """Cancel the ERPNext Sales Order (and any Delivery Notes) for a cancelled Amazon order."""
    so_name = frappe.db.get_value(
        "Sales Order",
        {"custom_marketplace_order_id": amazon_order_id, "docstatus": 1},
    )
    if not so_name:
        return  # already cancelled or never imported

    # Cancel submitted Delivery Notes first
    dn_names = frappe.get_all(
        "Delivery Note Item",
        filters={"against_sales_order": so_name},
        pluck="parent",
    )
    for dn_name in set(dn_names):
        dn = frappe.get_doc("Delivery Note", dn_name)
        if dn.docstatus == 1:
            dn.cancel()

    so = frappe.get_doc("Sales Order", so_name)
    so.cancel()
    frappe.logger().info(f"[Amazon] Cancelled SO {so_name} for Amazon order {amazon_order_id}")


def _resolve_item_code(sku: str | None) -> str | None:
    """Find ERPNext item_code for an Amazon SKU. Returns None if not found."""
    if not sku:
        return None
    if frappe.db.exists("Item", sku):
        return sku
    matched = frappe.db.get_value("Item", {"custom_amazon_sku": sku})
    return matched or None


def _normalize_customer_data(amz_order: dict) -> dict:
    """Map a raw Amazon order dict to the common customer data shape."""
    buyer = amz_order.get("BuyerInfo", {})
    tax_info = buyer.get("BuyerTaxInfo") or {}
    shipping_raw = amz_order.get("ShippingAddress") or {}

    shipping = None
    if shipping_raw.get("AddressLine1"):
        shipping = {
            "line1": shipping_raw.get("AddressLine1", ""),
            "line2": (
                (shipping_raw.get("AddressLine2") or "")
                + " "
                + (shipping_raw.get("AddressLine3") or "")
            ).strip(),
            "city": shipping_raw.get("City", ""),
            "state": shipping_raw.get("StateOrRegion", ""),
            "pincode": shipping_raw.get("PostalCode", ""),
            "country": shipping_raw.get("CountryCode") or "India",
            "phone": shipping_raw.get("Phone", ""),
        }

    return {
        "name": buyer.get("BuyerName", ""),
        "email": buyer.get("BuyerEmail", ""),
        "phone": "",
        "source": "Amazon",
        "shipping_address": shipping,
        "billing_address": None,
        "gstin": tax_info.get("TaxingRegion", ""),
    }
