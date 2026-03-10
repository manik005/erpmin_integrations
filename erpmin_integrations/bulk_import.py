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
