import csv
import io

import frappe
from frappe import whitelist
from frappe.model.document import Document


class ChannelCategoryMapping(Document):
    pass


def get_category_id(item_group):
    result = frappe.db.get_value(
        "Channel Category Mapping",
        {"item_group": item_group},
        "opencart_category_id",
    )
    return result or 0


def get_amazon_product_type(item_group):
    return frappe.db.get_value(
        "Channel Category Mapping",
        {"item_group": item_group},
        "amazon_product_type",
    ) or None


@whitelist()
def import_category_mappings(csv_data: str) -> dict:
    """Upsert Channel Category Mapping rows from a CSV string.

    CSV columns: item_group, opencart_category_id, opencart_category_name, amazon_product_type

    Returns:
        {"imported": N, "skipped": N, "errors": [{"row": R, "reason": "..."}]}
    """
    reader = csv.DictReader(io.StringIO(csv_data))
    imported = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):  # row 1 is header
        item_group = (row.get("item_group") or "").strip()
        if not item_group:
            skipped += 1
            errors.append({"row": row_num, "reason": "item_group is empty"})
            continue

        if not frappe.db.exists("Item Group", item_group):
            skipped += 1
            errors.append({"row": row_num, "reason": f"Item Group '{item_group}' not found in ERPNext"})
            continue

        existing_name = frappe.db.get_value(
            "Channel Category Mapping", {"item_group": item_group}
        )

        try:
            if existing_name:
                doc = frappe.get_doc("Channel Category Mapping", existing_name)
            else:
                doc = frappe.new_doc("Channel Category Mapping")
                doc.item_group = item_group

            oc_id = row.get("opencart_category_id", "")
            doc.opencart_category_id = int(oc_id) if oc_id.strip().isdigit() else 0
            doc.opencart_category_name = (row.get("opencart_category_name") or "").strip()
            doc.amazon_product_type = (row.get("amazon_product_type") or "").strip().upper()

            if existing_name:
                doc.save(ignore_permissions=True)
            else:
                doc.insert(ignore_permissions=True)

            imported += 1
        except Exception as e:
            skipped += 1
            errors.append({"row": row_num, "reason": str(e)})

    frappe.db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}


def enqueue_resync_for_group(item_group: str):
    """Enqueue Amazon re-sync for all items in the given Item Group."""
    items = frappe.get_all(
        "Item",
        filters={"item_group": item_group, "custom_sync_to_amazon": 1, "disabled": 0},
        pluck="name",
    )
    for item_code in items:
        frappe.enqueue(
            "erpmin_integrations.amazon.product.sync_item",
            item_code=item_code,
            queue="long",
            enqueue_after_commit=True,
        )


def on_mapping_save(doc, method=None):
    """Trigger Amazon re-sync when a category mapping is saved."""
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return
    enqueue_resync_for_group(doc.item_group)


@whitelist()
def get_category_mapping_template() -> str:
    """Return a blank CSV template with headers and example rows."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["item_group", "opencart_category_id", "opencart_category_name", "amazon_product_type"],
    )
    writer.writeheader()
    writer.writerows([
        {"item_group": "Clothing", "opencart_category_id": "10",
         "opencart_category_name": "Clothing", "amazon_product_type": "CLOTHING"},
        {"item_group": "Electronics", "opencart_category_id": "11",
         "opencart_category_name": "Electronics", "amazon_product_type": "CONSUMER_ELECTRONICS"},
    ])
    return buf.getvalue()
