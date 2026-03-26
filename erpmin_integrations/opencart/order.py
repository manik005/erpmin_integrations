import frappe
from frappe.utils import now_datetime
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings
from erpmin_integrations.customer import get_or_create_customer


@frappe.whitelist(allow_guest=True)
def order_webhook():
    """Receive a new-order webhook from OpenCart and import it into ERPNext.

    OpenCart POSTs:  { "order_id": "123" }
    with header:     X-Webhook-Secret: <shared_secret>
    """
    settings = get_settings()
    if not settings.enabled:
        frappe.throw("OpenCart integration is disabled", frappe.PermissionError)

    expected_secret = settings.get_password("webhook_secret") if settings.webhook_secret else None
    if expected_secret:
        incoming = frappe.request.headers.get("X-Webhook-Secret", "")
        if incoming != expected_secret:
            frappe.throw("Invalid webhook secret", frappe.PermissionError)

    data = frappe.request.get_json(silent=True) or {}
    order_id = str(data.get("order_id", "")).strip()
    if not order_id:
        frappe.throw("order_id is required")

    client = get_client()
    if not client:
        frappe.throw("OpenCart client could not be initialised")

    try:
        _create_sales_order(client, order_id, settings)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"[OpenCart] webhook order import failed: {order_id}")
        frappe.throw(f"Failed to import order {order_id}")

    return {"status": "ok", "order_id": order_id}


@frappe.whitelist(allow_guest=True)
def cancel_webhook():
    """Receive an order-cancellation webhook from OpenCart and cancel the ERPNext Sales Order.

    OpenCart POSTs:  { "order_id": "123" }
    with header:     X-Webhook-Secret: <shared_secret>
    """
    settings = get_settings()
    if not settings.enabled:
        frappe.throw("OpenCart integration is disabled", frappe.PermissionError)

    expected_secret = settings.get_password("webhook_secret") if settings.webhook_secret else None
    if expected_secret:
        incoming = frappe.request.headers.get("X-Webhook-Secret", "")
        if incoming != expected_secret:
            frappe.throw("Invalid webhook secret", frappe.PermissionError)

    data = frappe.request.get_json(silent=True) or {}
    order_id = str(data.get("order_id", "")).strip()
    if not order_id:
        frappe.throw("order_id is required")

    so_name = frappe.db.get_value(
        "Sales Order",
        {"custom_marketplace_order_id": order_id, "custom_channel": "OpenCart", "docstatus": 1},
    )
    if not so_name:
        return {"status": "skipped", "reason": "not found or already cancelled"}

    try:
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
        frappe.logger().info(f"[OpenCart] Cancelled SO {so_name} for order {order_id}")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"[OpenCart] cancel_webhook failed: {order_id}")
        frappe.throw(f"Failed to cancel order {order_id}")

    return {"status": "cancelled", "sales_order": so_name}


_PAGE_SIZE = 100


def import_orders():
    """Pull pending OpenCart orders across all pages and enqueue each for processing."""
    client = get_client()
    if not client:
        return

    enqueued = 0
    start = 0

    while True:
        result = client.get_new_orders(status_id=1, start=start, limit=_PAGE_SIZE)
        page = result.get("orders", [])

        for oc_order in page:
            order_id = str(oc_order.get("order_id"))
            frappe.enqueue(
                "erpmin_integrations.opencart.order._process_order_job",
                order_id=order_id,
                queue="short",
                enqueue_after_commit=True,
            )
            enqueued += 1

        if len(page) < _PAGE_SIZE:
            break
        start += _PAGE_SIZE

    if enqueued:
        frappe.logger().info(f"[OpenCart] Enqueued {enqueued} orders for processing")


def _process_order_job(order_id: str):
    """Queue job: create a Sales Order for a single OpenCart order."""
    client = get_client()
    if not client:
        return
    settings = get_settings()
    try:
        _create_sales_order(client, order_id, settings)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[OpenCart] order import failed: {order_id}",
        )


def _create_sales_order(client, order_id, settings):
    if frappe.db.exists("Sales Order", {"custom_marketplace_order_id": order_id}):
        return

    order = client.get_order(order_id)
    if not order:
        return

    customer_data = _normalize_customer_data(order)
    customer = get_or_create_customer(customer_data)

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.custom_channel = "OpenCart"
    so.custom_marketplace_order_id = order_id
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
    so.price_list = settings.default_price_list
    so.set_warehouse = settings.default_warehouse

    for product in order.get("products", []):
        sku = product.get("sku") or product.get("model")
        if not frappe.db.exists("Item", sku):
            frappe.logger().warning(f"[OpenCart] Item not found: {sku}")
            continue
        so.append(
            "items",
            {
                "item_code": sku,
                "qty": float(product.get("quantity", 1)),
                "rate": float(product.get("price", 0)),
                "warehouse": settings.default_warehouse,
            },
        )

    if not so.items:
        return

    so.insert(ignore_permissions=True)
    so.submit()

    client.update_order_status(order_id, 2, "Order imported to ERP")
    frappe.logger().info(f"[OpenCart] Imported order {order_id} → {so.name}")


def _normalize_customer_data(order: dict) -> dict:
    first = (order.get("firstname") or "").strip()
    last = (order.get("lastname") or "").strip()
    name = f"{first} {last}".strip() or order.get("email", "")

    def _build_addr(prefix):
        line1 = (order.get(f"{prefix}address_1") or "").strip()
        if not line1:
            return None
        return {
            "line1": line1,
            "line2": order.get(f"{prefix}address_2", "") or "",
            "city": order.get(f"{prefix}city", ""),
            "state": order.get(f"{prefix}zone", ""),
            "pincode": order.get(f"{prefix}postcode", ""),
            "country": order.get(f"{prefix}country") or "India",
            "phone": "",
        }

    return {
        "name": name,
        "email": order.get("email", ""),
        "phone": order.get("telephone", ""),
        "source": "OpenCart",
        "shipping_address": _build_addr("shipping_"),
        "billing_address": _build_addr("payment_"),
        "gstin": "",
    }
