import frappe
from frappe.utils import now_datetime
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings
from erpmin_integrations.customer import get_or_create_customer


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
