import frappe
from erpmin_integrations.opencart.api import get_client

_SHIPPED_STATUS_ID = 5  # OpenCart default "Shipped" status


def on_delivery_note_submit(doc, method=None):
    """Trigger OpenCart order status update when a Delivery Note is submitted."""
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return

    sales_order_name = None
    for item in doc.items:
        if item.against_sales_order:
            sales_order_name = item.against_sales_order
            break

    if not sales_order_name:
        return

    channel = frappe.db.get_value("Sales Order", sales_order_name, "custom_channel")
    if channel != "OpenCart":
        return

    marketplace_order_id = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_marketplace_order_id"
    )
    if not marketplace_order_id:
        return

    frappe.enqueue(
        "erpmin_integrations.opencart.fulfillment.send_shipment_update",
        delivery_note=doc.name,
        opencart_order_id=marketplace_order_id,
        queue="short",
        enqueue_after_commit=True,
    )


def send_shipment_update(delivery_note, opencart_order_id):
    client = get_client()
    if not client:
        return

    dn = frappe.get_doc("Delivery Note", delivery_note)

    tracking_no = (dn.lr_no or "").strip()
    carrier = (dn.transporter_name or "").strip()

    # Fall back to the shipping method stored on the Sales Order
    if not carrier:
        so_name = next(
            (item.against_sales_order for item in dn.items if item.against_sales_order),
            None,
        )
        if so_name:
            carrier = frappe.db.get_value("Sales Order", so_name, "custom_shipping_method") or ""

    comment = "Shipped"
    if carrier and tracking_no:
        comment = f"Shipped via {carrier}. Tracking: {tracking_no}"
    elif tracking_no:
        comment = f"Shipped. Tracking: {tracking_no}"
    elif carrier:
        comment = f"Shipped via {carrier}"

    try:
        client.update_order_status(opencart_order_id, _SHIPPED_STATUS_ID, comment)
        frappe.logger().info(
            f"[OpenCart] Order {opencart_order_id} marked shipped (DN: {delivery_note})"
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[OpenCart] shipment update failed: {opencart_order_id}",
        )
