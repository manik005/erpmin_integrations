"""
Two operations, run in this order inside the ERPNext container:

  1. rename_cavron_shorts() — renames AESAL006–033 → AESAN001–028
  2. run()                  — sets variant_of on all 211 AES items

Run:
    docker exec erpnext-app bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.update_aes_variants.rename_cavron_shorts

    docker exec erpnext-app bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.update_aes_variants.run
"""
import json

import frappe

_MAP_PATH = "/home/frappe/frappe-bench/sites/erp.local/private/files/variant-update-map-aes.json"


def fix_cavron_pants_and_shorts():
    """Fix the AESAL001–005 code collision between Cavron Shorts and Cavron Body Fit Pants.

    AESAL001–005 currently hold Cavron Body Fit Pants metadata (from fix_cavron_pants)
    but their stock history belongs to Cavron Shorts Black 24–32.

    Steps:
      1. Revert AESAL001–005 metadata back to Cavron Shorts Black 24–32
      2. Rename AESAL001–005 → AESAN024–028 (stock history follows)
      3. Create fresh AESAL001–005 as Cavron Body Fit Pants S/M/L/XL/XXL
    """
    _SHORTS_BLACK_KIDS = [
        ("AESAL001", "AESAN024", "Cavron Shorts - Black 24", "Black", "24"),
        ("AESAL002", "AESAN025", "Cavron Shorts - Black 26", "Black", "26"),
        ("AESAL003", "AESAN026", "Cavron Shorts - Black 28", "Black", "28"),
        ("AESAL004", "AESAN027", "Cavron Shorts - Black 30", "Black", "30"),
        ("AESAL005", "AESAN028", "Cavron Shorts - Black 32", "Black", "32"),
    ]
    _PANTS = [
        ("AESAL001", "Cavron Body fit - Pants S",   "S"),
        ("AESAL002", "Cavron Body fit - Pants M",   "M"),
        ("AESAL003", "Cavron Body fit - Pants L",   "L"),
        ("AESAL004", "Cavron Body fit - Pants XL",  "XL"),
        ("AESAL005", "Cavron Body fit - Pants XXL", "XXL"),
    ]

    errors = []

    # Step 1: revert AESAL001–005 metadata to Cavron Shorts Black 24–32
    print("Step 1: reverting AESAL001–005 to Cavron Shorts Black metadata…")
    for old_code, _, item_name, color, size in _SHORTS_BLACK_KIDS:
        if not frappe.db.exists("Item", old_code):
            errors.append(f"{old_code}: not found for revert")
            continue
        frappe.db.set_value(
            "Item", old_code,
            {"item_name": item_name, "variant_of": "Cavron Shorts - Kids",
             "item_group": "AES", "has_variants": 0},
            update_modified=False,
        )
        frappe.db.delete("Item Variant Attribute", {"parent": old_code})
        for idx, (attr, val) in enumerate([("Color", color), ("Size", size)], start=1):
            frappe.db.sql(
                """INSERT INTO `tabItem Variant Attribute`
                    (name, creation, modified, modified_by, owner, docstatus,
                     parent, parenttype, parentfield, idx, attribute, attribute_value)
                   VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
                           %s, 'Item', 'attributes', %s, %s, %s)""",
                (frappe.generate_hash(length=10), old_code, idx, attr, val),
            )
    frappe.db.commit()
    print("  done.")

    # Step 2: rename AESAL001–005 → AESAN024–028
    print("Step 2: renaming AESAL001–005 → AESAN024–028…")
    renamed = 0
    for old_code, new_code, _, _, _ in _SHORTS_BLACK_KIDS:
        if frappe.db.exists("Item", new_code):
            print(f"  {new_code} already exists, skipping rename of {old_code}")
            continue
        if not frappe.db.exists("Item", old_code):
            errors.append(f"{old_code}: not found for rename")
            continue
        frappe.rename_doc("Item", old_code, new_code, force=True)
        renamed += 1
    frappe.db.commit()
    print(f"  renamed {renamed} items.")

    # Step 2b: remove stale barcodes left on AESAN024–028 after rename
    # (ERPNext auto-creates a barcode matching the item code; after rename the
    # old code value remains and blocks re-use of the code for a new item)
    print("Step 2b: clearing stale barcodes AESAL001–005…")
    for item_code, _, _ in _PANTS:
        frappe.db.delete("Item Barcode", {"barcode": item_code})
    frappe.db.commit()
    print("  done.")

    # Step 3: create fresh AESAL001–005 as Cavron Body Fit Pants
    print("Step 3: creating AESAL001–005 as Cavron Body Fit Pants…")
    created = 0
    for item_code, item_name, size in _PANTS:
        if frappe.db.exists("Item", item_code):
            print(f"  {item_code} already exists, skipping create")
            continue
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": "AES",
            "stock_uom": "Nos",
            "has_variants": 0,
            "variant_of": "Cavron Body Fit Pants",
            "is_stock_item": 1,
            "gst_hsn_code": "000000",
            "taxes": [{"item_tax_template": "GST 5% - AE"}],
            "attributes": [{"attribute": "Size", "attribute_value": size}],
        })
        doc.insert(ignore_permissions=True)
        created += 1
    frappe.db.commit()
    print(f"  created {created} items.")

    print(f"\n✓ Done. Renamed={renamed}, Created={created}")
    if errors:
        print(f"✗ {len(errors)} errors:")
        for e in errors:
            print(f"  {e}")


def fix_aesan_variants():
    """Patch all Cavron Shorts variant items to the new Kids/Adults templates.

    Queries by item_name to handle whatever item codes exist in ERPNext
    (AESAL or AESAN), parses Color and numeric size from the name, and
    applies the correct template + attribute rows.
    """
    import re

    _KIDS_SIZES = {24, 26, 28, 30, 32, 34}
    _ADULTS_SIZES = {36, 38, 40, 42, 44, 46, 48, 50}
    _TEMPLATE_NAMES = {"Cavron Shorts - Kids", "Cavron Shorts - Adults"}

    rows = frappe.db.sql(
        """SELECT name, item_name FROM `tabItem`
           WHERE item_name LIKE %s AND name NOT IN ('Cavron Shorts - Kids', 'Cavron Shorts - Adults')
           ORDER BY name""",
        ("%Cavron Shorts%",),
        as_dict=True,
    )

    updated, errors = 0, []
    for row in rows:
        item_code = row["name"]
        item_name = row["item_name"]
        # Pattern: "Cavron Shorts - {Color} {size}"
        m = re.search(r"-\s+(\w+)\s+(\d{2})\s*$", item_name)
        if not m:
            errors.append(f"{item_code}: cannot parse name {item_name!r}")
            continue
        color, size = m.group(1), int(m.group(2))
        if size in _KIDS_SIZES:
            template = "Cavron Shorts - Kids"
        elif size in _ADULTS_SIZES:
            template = "Cavron Shorts - Adults"
        else:
            errors.append(f"{item_code}: size {size} not in Kids/Adults sets")
            continue
        try:
            frappe.db.set_value(
                "Item", item_code,
                {"variant_of": template, "item_group": "AES", "has_variants": 0},
                update_modified=False,
            )
            frappe.db.delete("Item Variant Attribute", {"parent": item_code})
            for idx, (attr, val) in enumerate(
                [("Color", color), ("Size", str(size))], start=1
            ):
                frappe.db.sql(
                    """INSERT INTO `tabItem Variant Attribute`
                        (name, creation, modified, modified_by, owner, docstatus,
                         parent, parenttype, parentfield, idx, attribute, attribute_value)
                       VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
                               %s, 'Item', 'attributes', %s, %s, %s)""",
                    (frappe.generate_hash(length=10), item_code, idx, attr, val),
                )
            updated += 1
        except Exception as e:
            errors.append(f"{item_code}: {e}")

    frappe.db.commit()
    print(f"✓ Fixed {updated} Cavron Shorts variants")
    if errors:
        print(f"✗ {len(errors)} errors:")
        for e in errors:
            print(f"  {e}")


def find_cavron_shorts():
    """Print all Item records whose name contains 'Cavron Shorts' or 'AESAL'."""
    rows = frappe.db.sql(
        "SELECT name, item_name, variant_of FROM `tabItem` WHERE item_name LIKE %s ORDER BY name",
        ("%Cavron Shorts%",),
        as_dict=True,
    )
    print(f"Found {len(rows)} Cavron Shorts items:")
    for r in rows:
        print(f"  {r['name']:20s}  {r['item_name']:50s}  variant_of={r['variant_of']}")


def rename_cavron_shorts():
    """
    Rename Cavron Shorts from AESAL006–033 to AESAN001–028.
    AESAL001–005 (Cavron Body Fit Pants) are left untouched.
    Safe to run multiple times — skips codes that already exist as AESAN.
    """
    renamed, skipped, errors = 0, 0, []
    for i in range(1, 29):
        old_code = f"AESAL{i + 5:03d}"  # AESAL006 → AESAL033
        new_code = f"AESAN{i:03d}"
        if not frappe.db.exists("Item", old_code):
            skipped += 1
            continue
        if frappe.db.exists("Item", new_code):
            skipped += 1
            continue
        try:
            frappe.rename_doc("Item", old_code, new_code, force=True)
            renamed += 1
        except Exception as e:
            errors.append(f"{old_code} → {new_code}: {e}")

    frappe.db.commit()
    print(f"✓ Renamed {renamed} Cavron Shorts items (skipped {skipped})")
    for e in errors:
        print(f"  ✗ {e}")


def run():
    """Sets variant_of, item_group, and attribute child rows on all 211 AES items.

    Uses frappe.db.set_value to bypass the ORM stock-transaction guard, then
    directly inserts rows into tabItem Variant Attribute.
    """
    with open(_MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)

    vm = data["variant_template_map"]
    gm = data["variant_group_map"]
    am = data.get("variant_attributes_map", {})
    updated, errors = 0, []

    for item_code, new_template in vm.items():
        new_group = gm.get(item_code, "AES")
        if not frappe.db.exists("Item", item_code):
            errors.append(f"{item_code}: not found (rename step may be needed first)")
            continue
        try:
            # Bypass ORM variant guard
            frappe.db.set_value(
                "Item", item_code,
                {"variant_of": new_template, "item_group": new_group, "has_variants": 0},
                update_modified=False,
            )

            # Replace attribute child rows
            frappe.db.delete("Item Variant Attribute", {"parent": item_code})
            for idx, attr in enumerate(am.get(item_code, []), start=1):
                frappe.db.sql(
                    """
                    INSERT INTO `tabItem Variant Attribute`
                        (name, creation, modified, modified_by, owner, docstatus,
                         parent, parenttype, parentfield, idx, attribute, attribute_value)
                    VALUES
                        (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
                         %s, 'Item', 'attributes', %s, %s, %s)
                    """,
                    (
                        frappe.generate_hash(length=10),
                        item_code,
                        idx,
                        attr["attribute"],
                        attr["attribute_value"],
                    ),
                )
            updated += 1
        except Exception as e:
            errors.append(f"{item_code}: {e}")

    frappe.db.commit()
    print(f"✓ Updated {updated} AES variants")
    if errors:
        print(f"✗ {len(errors)} errors:")
        for e in errors:
            print(f"  {e}")
