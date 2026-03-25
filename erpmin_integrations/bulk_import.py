"""
Bulk import utilities for erpmin_integrations.
Exposed as whitelisted Frappe API endpoints.
"""
import csv
import io

import frappe
from frappe import whitelist

_ITEM_AMAZON_FIELDS = [
    "custom_amazon_product_type",
    "custom_amazon_brand",
    "custom_amazon_color",
    "custom_amazon_size",
    "custom_amazon_bullet_points",
    "custom_amazon_description",
]


@whitelist()
def import_item_amazon_fields(csv_data: str) -> dict:
    """Bulk update Amazon fields on Item records from a CSV string.

    CSV columns: item_code, custom_amazon_product_type, custom_amazon_brand,
                 custom_amazon_color, custom_amazon_size,
                 custom_amazon_bullet_points, custom_amazon_description

    All columns except item_code are optional (sparse update).

    Returns:
        {"imported": N, "skipped": N, "errors": [{"row": R, "reason": "..."}]}
    """
    reader = csv.DictReader(io.StringIO(csv_data))
    imported = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            skipped += 1
            errors.append({"row": row_num, "reason": "item_code is empty"})
            continue

        if not frappe.db.exists("Item", item_code):
            skipped += 1
            errors.append({"row": row_num, "reason": f"Item '{item_code}' not found"})
            continue

        try:
            updates = {
                field: row[field].strip()
                for field in _ITEM_AMAZON_FIELDS
                if field in row and row[field].strip() != ""
            }
            if updates:
                frappe.db.set_value("Item", item_code, updates)
            imported += 1
        except Exception as e:
            skipped += 1
            errors.append({"row": row_num, "reason": str(e)})

    frappe.db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}


@whitelist()
def trigger_opencart_product_sync() -> dict:
    """Enqueue a full OpenCart product sync (ERPNext → OpenCart).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.opencart.product.full_product_sync
    """
    frappe.enqueue(
        "erpmin_integrations.opencart.product.full_product_sync",
        queue="long",
        enqueue_after_commit=True,
    )
    return {"message": "OpenCart product sync enqueued"}


@whitelist()
def trigger_opencart_inventory_sync() -> dict:
    """Enqueue an OpenCart inventory sync (ERPNext stock → OpenCart quantities).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.opencart.inventory.sync_all_inventory
    """
    frappe.enqueue(
        "erpmin_integrations.opencart.inventory.sync_all_inventory",
        queue="long",
        enqueue_after_commit=True,
    )
    return {"message": "OpenCart inventory sync enqueued"}


@whitelist()
def trigger_opencart_order_import() -> dict:
    """Enqueue an OpenCart order import (OpenCart → ERPNext Sales Orders).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.opencart.order.import_orders
    """
    frappe.enqueue(
        "erpmin_integrations.opencart.order.import_orders",
        queue="short",
        enqueue_after_commit=True,
    )
    return {"message": "OpenCart order import enqueued"}


@whitelist()
def trigger_amazon_product_sync() -> dict:
    """Enqueue a full Amazon product sync (ERPNext → Amazon Listings API).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.amazon.product.full_product_sync
    """
    frappe.enqueue(
        "erpmin_integrations.amazon.product.full_product_sync",
        queue="long",
        enqueue_after_commit=True,
    )
    return {"message": "Amazon product sync enqueued"}


@whitelist()
def trigger_amazon_inventory_sync() -> dict:
    """Enqueue an Amazon inventory sync (ERPNext stock → Amazon Feeds API).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.amazon.inventory.sync_all_inventory
    """
    frappe.enqueue(
        "erpmin_integrations.amazon.inventory.sync_all_inventory",
        queue="long",
        enqueue_after_commit=True,
    )
    return {"message": "Amazon inventory sync enqueued"}


@whitelist()
def trigger_opencart_category_resync() -> dict:
    """Re-enqueue OpenCart product sync for all items in mapped item groups.

    Use this after updating Channel Category Mappings to push the new
    category assignments to OpenCart.

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.bulk_import.trigger_opencart_category_resync
    """
    item_groups = frappe.get_all("Channel Category Mapping", pluck="item_group")
    if not item_groups:
        return {"message": "No category mappings found"}

    count = 0
    for item_group in item_groups:
        items = frappe.get_all(
            "Item",
            filters={"item_group": item_group, "custom_sync_to_opencart": 1, "disabled": 0},
            pluck="name",
        )
        for item_code in items:
            frappe.enqueue(
                "erpmin_integrations.opencart.product.sync_item",
                item_code=item_code,
                queue="long",
                enqueue_after_commit=True,
            )
            count += 1

    return {"message": f"Enqueued OpenCart sync for {count} item(s) across {len(item_groups)} group(s)"}


@whitelist()
def trigger_amazon_category_resync() -> dict:
    """Re-enqueue Amazon product sync for all items in mapped item groups.

    Use this after updating Channel Category Mappings to push the new
    product type assignments to Amazon.

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.bulk_import.trigger_amazon_category_resync
    """
    from erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
        enqueue_resync_for_group,
    )

    item_groups = frappe.get_all("Channel Category Mapping", pluck="item_group")
    if not item_groups:
        return {"message": "No category mappings found"}

    count = 0
    for item_group in item_groups:
        items = frappe.get_all(
            "Item",
            filters={"item_group": item_group, "custom_sync_to_amazon": 1, "disabled": 0},
            pluck="name",
        )
        count += len(items)
        enqueue_resync_for_group(item_group)

    return {"message": f"Enqueued Amazon sync for {count} item(s) across {len(item_groups)} group(s)"}


@whitelist()
def trigger_amazon_order_import() -> dict:
    """Enqueue an Amazon order import (Amazon SP-API → ERPNext Sales Orders).

    Bench equivalent:
        bench --site erp.local execute erpmin_integrations.amazon.order.import_orders
    """
    frappe.enqueue(
        "erpmin_integrations.amazon.order.import_orders",
        queue="short",
        enqueue_after_commit=True,
    )
    return {"message": "Amazon order import enqueued"}


@whitelist()
def get_item_amazon_template() -> str:
    """Return a blank CSV template for Item Amazon fields bulk update."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["item_code"] + _ITEM_AMAZON_FIELDS)
    writer.writeheader()
    writer.writerow({
        "item_code": "ITEM-001",
        "custom_amazon_product_type": "CLOTHING",
        "custom_amazon_brand": "Brand Name",
        "custom_amazon_color": "Red",
        "custom_amazon_size": "M",
        "custom_amazon_bullet_points": "Feature one\nFeature two",
        "custom_amazon_description": "Full product description for Amazon",
    })
    return buf.getvalue()
