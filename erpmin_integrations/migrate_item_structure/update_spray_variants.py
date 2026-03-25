"""
Changes variant_of on 24 spray perfume items from the old "Perfume - Spray"
template to the new per-fragrance templates (e.g. "Spray Perfume - Paris").
Also replaces attribute child rows so only Size (30ml/50ml/100ml) remains —
the fragrance is now encoded in the template name, not an attribute.

Uses frappe.db.set_value to bypass the ORM stock-transaction guard.

Run:
    docker exec erpnext-app bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.update_spray_variants.run
"""
import json

import frappe

_MAP_PATH = "/home/frappe/frappe-bench/sites/erp.local/private/files/variant-update-map-spray.json"

# Series → Size attribute value
_SERIES_SIZE = {"PYAC": "30ml", "PYAD": "50ml", "PYAE": "100ml"}

_NEW_TEMPLATES = [f"Spray Perfume - {f}" for f in
    ["Paris", "Milan", "Madrid", "Munich", "Tokyo", "Venice", "Zurich", "London"]]


def reset_spray_opencart_ids():
    """Clear custom_opencart_id on spray variants and their new templates.

    The 24 spray variants carry the old 'Perfume - Spray' product ID (66)
    from before the migration. This causes _sync_variant_item to skip the
    new-variant creation path and try to update the stale product ID.
    Clearing the IDs forces a clean re-sync under the new per-fragrance products.
    """
    # Clear on variants
    variant_codes = [f"{s}{i:04d}" for s in _SERIES_SIZE for i in range(1, 9)]
    frappe.db.sql(
        "UPDATE `tabItem` SET custom_opencart_id = NULL WHERE name IN %(codes)s",
        {"codes": variant_codes},
    )
    # Clear on new fragrance templates (may have gotten stale IDs too)
    frappe.db.sql(
        "UPDATE `tabItem` SET custom_opencart_id = NULL WHERE name IN %(codes)s",
        {"codes": _NEW_TEMPLATES},
    )
    frappe.db.commit()
    print(f"✓ Cleared custom_opencart_id on {len(variant_codes)} variants and {len(_NEW_TEMPLATES)} templates")


def run():
    with open(_MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)

    vm = data["variant_template_map"]
    gm = data["variant_group_map"]
    updated, errors = 0, []

    for item_code, new_template in vm.items():
        if not frappe.db.exists("Item", item_code):
            errors.append(f"{item_code}: not found")
            continue

        series = item_code[:4]  # PYAC / PYAD / PYAE
        size = _SERIES_SIZE.get(series)
        if not size:
            errors.append(f"{item_code}: unknown series {series!r}")
            continue

        try:
            frappe.db.set_value(
                "Item", item_code,
                {"variant_of": new_template, "item_group": gm.get(item_code, "PY")},
                update_modified=False,
            )

            # Replace attribute rows — keep only Size, drop Fragrance
            frappe.db.delete("Item Variant Attribute", {"parent": item_code})
            frappe.db.sql(
                """INSERT INTO `tabItem Variant Attribute`
                    (name, creation, modified, modified_by, owner, docstatus,
                     parent, parenttype, parentfield, idx, attribute, attribute_value)
                   VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
                           %s, 'Item', 'attributes', 1, 'Size', %s)""",
                (frappe.generate_hash(length=10), item_code, size),
            )
            updated += 1
        except Exception as e:
            errors.append(f"{item_code}: {e}")

    frappe.db.commit()
    print(f"✓ Updated {updated} spray variants")
    if errors:
        print(f"✗ {len(errors)} errors:")
        for e in errors:
            print(f"  {e}")
