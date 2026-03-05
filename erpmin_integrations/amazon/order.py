import frappe
from frappe.utils import now_datetime, add_days, today, get_datetime
from erpmin_integrations.amazon.api import get_client
from erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings


def import_orders():
    """Poll Amazon SP-API for new orders and create ERPNext Sales Orders."""
    client = get_client()
    if not client:
        return

    settings = get_settings()
    last_sync = settings.last_order_sync_time

    if last_sync:
        created_after = get_datetime(last_sync).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        # Default: last 24 hours on first run
        from datetime import datetime, timedelta, timezone
        created_after = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    sync_start = now_datetime()

    try:
        response = client.get_orders(created_after)
        orders = response.get("payload", {}).get("Orders", [])

        for amz_order in orders:
            order_id = amz_order.get("AmazonOrderId")
            try:
                _create_sales_order(client, amz_order, settings)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"[Amazon] order import failed: {order_id}",
                )
    finally:
        # Always advance the sync cursor even on partial failure
        frappe.db.set_value(
            "Amazon Settings", "Amazon Settings", "last_order_sync_time", sync_start
        )
        frappe.db.commit()


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

    buyer = amz_order.get("BuyerInfo", {})
    customer = _get_or_create_customer(buyer, order_id)

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.custom_channel = "Amazon"
    so.custom_marketplace_order_id = order_id
    so.delivery_date = add_days(today(), 3)
    so.set_warehouse = settings.default_warehouse if hasattr(settings, "default_warehouse") else "Main Warehouse"

    for oi in order_items:
        sku = oi.get("SellerSKU") or oi.get("ASIN")
        if not frappe.db.exists("Item", sku):
            # Try matching by custom_amazon_sku
            matched = frappe.db.get_value("Item", {"custom_amazon_sku": sku})
            if not matched:
                frappe.logger().warning(f"[Amazon] Item not found for SKU: {sku}")
                continue
            sku = matched

        qty = float(oi.get("QuantityOrdered", 1))
        price_data = oi.get("ItemPrice", {})
        amount = float(price_data.get("Amount", 0))
        rate = amount / qty if qty else 0

        so.append(
            "items",
            {
                "item_code": sku,
                "qty": qty,
                "rate": rate,
                "warehouse": so.set_warehouse,
            },
        )

    if not so.items:
        return

    so.insert(ignore_permissions=True)
    so.submit()
    frappe.logger().info(f"[Amazon] Imported order {order_id} → {so.name}")


def _get_or_create_customer(buyer, order_id):
    name = buyer.get("BuyerName") or f"Amazon Customer {order_id}"

    existing = frappe.db.get_value("Customer", {"customer_name": name})
    if existing:
        return existing

    customer = frappe.new_doc("Customer")
    customer.customer_name = name
    customer.customer_type = "Individual"
    customer.customer_group = "Individual"
    customer.territory = "India"
    customer.insert(ignore_permissions=True)
    return customer.name
