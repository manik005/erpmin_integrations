import frappe
from erpmin_integrations.amazon.api import get_client


def on_delivery_note_submit(doc, method=None):
    """Trigger Amazon shipment confirmation when a Delivery Note is submitted."""
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return

    # Find the linked Sales Order
    sales_order_name = None
    for item in doc.items:
        if item.against_sales_order:
            sales_order_name = item.against_sales_order
            break

    if not sales_order_name:
        return

    channel = frappe.db.get_value("Sales Order", sales_order_name, "custom_channel")
    if channel != "Amazon":
        return

    marketplace_order_id = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_marketplace_order_id"
    )
    if not marketplace_order_id:
        return

    frappe.enqueue(
        "erpmin_integrations.amazon.fulfillment.send_shipment_confirmation",
        delivery_note=doc.name,
        amazon_order_id=marketplace_order_id,
        queue="short",
        enqueue_after_commit=True,
    )


def send_shipment_confirmation(delivery_note, amazon_order_id):
    client = get_client()
    if not client:
        return

    dn = frappe.get_doc("Delivery Note", delivery_note)

    tracking_no = dn.lr_no or ""
    carrier = _map_carrier(dn.transporter_name or "")

    ship_items = []
    for item in dn.items:
        sku = item.item_code
        amazon_sku = frappe.db.get_value("Item", sku, "custom_amazon_sku") or sku
        ship_items.append(
            {
                "orderItemId": getattr(item, "custom_amazon_order_item_id", "") or item.so_detail or "",
                "quantity": int(item.qty),
                "itemLevelSellerInputsList": [],
            }
        )

    payload = {
        "marketplaceId": _get_marketplace_id(),
        "packageDetail": {
            "packageClientReferenceId": delivery_note,
            "carrierCode": carrier,
            "trackingId": tracking_no,
            "shipDate": dn.posting_date.strftime("%Y-%m-%dT00:00:00Z"),
            "orderItems": ship_items,
        },
    }

    try:
        client.confirm_shipment(amazon_order_id, payload)
        frappe.logger().info(
            f"[Amazon] Shipment confirmed: order={amazon_order_id} dn={delivery_note}"
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"[Amazon] shipment confirmation failed: {amazon_order_id}",
        )


def _get_marketplace_id():
    from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings
    return get_settings().marketplace_id


def _map_carrier(transporter_name):
    """Map ERPNext transporter names to Amazon carrier codes."""
    mapping = {
        "delhivery": "DELHIVERY_IN",
        "ekart": "EKART_IN",
        "bluedart": "BLUE_DART",
        "dtdc": "DTDC",
        "shiprocket": "SHIPROCKET",
        "amazon": "AMAZON_IN",
    }
    key = transporter_name.lower().strip()
    for name, code in mapping.items():
        if name in key:
            return code
    return "Other"
