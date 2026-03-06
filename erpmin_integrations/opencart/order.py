import frappe
from frappe.utils import now_datetime
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings


def import_orders():
    """Pull pending OpenCart orders and create ERPNext Sales Orders."""
    client = get_client()
    if not client:
        return

    settings = get_settings()
    orders = client.get_new_orders(status_id=1)

    for oc_order in orders.get("orders", []):
        order_id = str(oc_order.get("order_id"))
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

    customer = _get_or_create_customer(order)

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


def _get_or_create_customer(order):
    email = order.get("email", "")
    name = f"{order.get('firstname', '')} {order.get('lastname', '')}".strip()
    if not name:
        name = email or "OpenCart Customer"

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
