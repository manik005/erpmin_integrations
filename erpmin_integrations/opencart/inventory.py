import frappe
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings
from erpmin_integrations.utils.inventory import get_available_qty


def sync_all_inventory():
    client = get_client()
    if not client:
        return

    settings = get_settings()
    warehouse = settings.default_warehouse or "Main Warehouse"

    items = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "disabled": 0, "custom_opencart_id": ["!=", ""]},
        fields=["name", "custom_opencart_id"],
    )
    for item in items:
        try:
            sync_item_inventory(
                item.name,
                item.custom_opencart_id,
                warehouse=warehouse,
                client=client,
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"[OpenCart] inventory sync failed: {item.name}",
            )


def sync_item_inventory(item_code, product_id, warehouse="Main Warehouse", client=None):
    if client is None:
        client = get_client()
    if not client:
        return

    qty = get_available_qty(item_code, warehouse)
    client.update_stock(product_id, int(qty))
    frappe.logger().debug(f"[OpenCart] inventory synced {item_code}: qty={qty}")
