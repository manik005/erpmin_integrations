# custom-apps/erpmin_integrations/erpmin_integrations/migrate_item_structure/rename_old_templates.py
"""
Phase 4 Step 6 — Rename old template items.

Run inside container:
  docker exec erpnext-app bench --site erp.local execute \
    erpmin_integrations.migrate_item_structure.rename_old_templates.run

All 6 renames are wrapped in a single savepoint — if any fails, all are rolled back.
"""
import frappe

RENAMES = [
    ("JERSEY",  "JERSEY-OLD"),
    ("T-SHIRT", "TSHIRT-OLD"),
    ("SHORTS",  "SHORTS-OLD"),
    ("BIBS",    "BIBS-OLD"),
    ("TRACK",   "TRACK-OLD"),
    ("PANTS",   "PANTS-OLD"),
]


def run():
    print("=== Rename Old Templates ===")
    # Use explicit savepoint/rollback pattern (safe across all Frappe v15 versions).
    # frappe.db.savepoint() issues SQL SAVEPOINT; frappe.db.rollback(save_point=)
    # rolls back to it. We do NOT use `with frappe.db.savepoint(...)` because
    # the context-manager form was not available in all Frappe v15 patch releases.
    frappe.db.savepoint("rename_old_templates")
    try:
        for old_name, new_name in RENAMES:
            if not frappe.db.exists("Item", old_name):
                print(f"  SKIP: {old_name} not found (already renamed?)")
                continue
            frappe.rename_doc("Item", old_name, new_name, force=True)
            frappe.db.set_value("Item", new_name, "disabled", 1)
            print(f"  ✓ {old_name} → {new_name} (disabled)")
    except Exception:
        frappe.db.rollback(save_point="rename_old_templates")
        raise
    frappe.db.commit()
    print("\n✓ All renames complete and committed.")
