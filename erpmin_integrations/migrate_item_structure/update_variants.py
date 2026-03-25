"""
Phase 4 — Update variant_of and item_group on all apparel variants.

Uses frappe.db.set_value to bypass the ORM validation that blocks changes to
variant_of when stock transactions exist (validate_stock_exists_for_template_item).

Run:
    docker exec erpnext-app bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.update_variants.run
"""
import json

import frappe

# Path inside the container — written by 02_generate_imports.py on the host,
# accessible via the bind-mounted sites directory.
_MAP_PATH = "/home/frappe/frappe-bench/sites/erp.local/private/files/variant-update-map.json"


def run():
    with open(_MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)

    variant_template_map = data["variant_template_map"]
    variant_group_map = data["variant_group_map"]

    updated = 0
    errors = []

    for item_code, new_template in variant_template_map.items():
        new_group = variant_group_map.get(item_code)
        if not new_group:
            errors.append(f"{item_code}: no group in map")
            continue
        try:
            frappe.db.set_value(
                "Item", item_code,
                {"variant_of": new_template, "item_group": new_group},
                update_modified=False,
            )
            updated += 1
        except Exception as e:
            errors.append(f"{item_code}: {e}")

    frappe.db.commit()

    print(f"✓ Updated {updated} variants")
    if errors:
        print(f"✗ {len(errors)} errors:")
        for e in errors:
            print(f"  {e}")
