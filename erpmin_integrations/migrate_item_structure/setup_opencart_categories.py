"""
setup_opencart_categories.py

Creates the OpenCart category hierarchy matching the storefront menu, then saves
Channel Category Mapping records in ERPNext linking each item group to its category.

Run from inside the ERPNext container:
    bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.setup_opencart_categories.run

Category tree (matches storefront primary menu):
    Perfumes                         ← PY, Perfumes
      ├── Roll On                    ← Roll on
      ├── Candles                    ← Candles
      ├── Essential Oils             ← Essential oils
      └── Fragrance Oils             ← Fragrance oils
    AE Sports                        ← AES
      ├── Apparels                   ← Apparels, Full/Half sleeve cricket whites,
      │   │                             Set of jersey and trousers (full/half sleeve)
      │   ├── Jersey                 ← Jersey
      │   ├── T-Shirt                ← T-Shirt
      │   ├── Shorts                 ← Shorts
      │   ├── Bibs                   ← Bibs
      │   └── Track                  ← Track
      └── Sports Accessories         ← Sports Accessories
          ├── Bats                   ← Cricket bat type 1–5
          ├── Gloves                 ← Cricket gloves type 1–2
          ├── Balls                  ← balls
          └── Bat Grip               ← Bat Grip
    AE Stationers, Crafts & Gifts    ← AEC
      ├── Keychains                  ← Keychains
      ├── Stickers                   ← Stickers
      └── Bottles                    ← Bottles
    AE Nursery                       ← AEN
      ├── Ceramic Pots               ← Ceramic pots
      └── Nursery Pots               ← Nursery pots
"""

import frappe


# Each entry: (key, opencart_name, parent_key, is_top_nav, erp_item_groups)
# - key: unique identifier used to resolve parent references
# - is_top_nav: True → top=1 (shows in OpenCart top navigation bar)
# - erp_item_groups: list of ERPNext Item Group names mapped to this OC category
CATEGORIES = [
    # ── Top-level (primary menu) ──────────────────────────────────────────────
    ("perfumes",    "Perfumes",                      None,         True,  ["PY", "Perfumes"]),
    ("ae_sports",   "AE Sports",                     None,         True,  ["AES"]),
    ("ae_station",  "AE Stationers, Crafts & Gifts", None,         True,  ["AEC"]),
    ("ae_nursery",  "AE Nursery",                    None,         True,  ["AEN"]),

    # ── Under Perfumes ────────────────────────────────────────────────────────
    ("roll_on",         "Roll On",       "perfumes",  False, ["Roll on"]),
    ("candles",         "Candles",       "perfumes",  False, ["Candles"]),
    ("essential_oils",  "Essential Oils","perfumes",  False, ["Essential oils"]),
    ("fragrance_oils",  "Fragrance Oils","perfumes",  False, ["Fragrance oils"]),

    # ── Under AE Sports ───────────────────────────────────────────────────────
    # Cricket whites & jersey+trouser sets are clothing → map to Apparels OC category
    # NOTE: in ERPNext, move these item groups under "Apparels" parent group
    ("apparels",      "Apparels",           "ae_sports", False, [
        "Apparels",
        "Full sleeve cricket whites",
        "Half sleeve cricket whites",
        "Set of jersey and trousers (full sleeve)",
        "Set of jersey and trousers (half sleeve)",
    ]),
    ("sports_acc",  "Sports Accessories", "ae_sports",  False, ["Sports Accessories"]),
    ("bats",        "Bats",               "sports_acc", False, [
        "Cricket bat type 1", "Cricket bat type 2", "Cricket bat type 3",
        "Cricket bat type 4", "Cricket bat type 5",
    ]),
    ("gloves",      "Gloves",             "sports_acc", False, [
        "Cricket gloves type 1", "Cricket gloves type 2",
    ]),
    ("balls",       "Balls",              "sports_acc", False, ["balls"]),
    ("bat_grip",    "Bat Grip",           "sports_acc", False, ["Bat Grip"]),

    # ── Under Apparels ────────────────────────────────────────────────────────
    ("jersey",  "Jersey",  "apparels", False, ["Jersey"]),
    ("tshirt",  "T-Shirt", "apparels", False, ["T-Shirt"]),
    ("shorts",  "Shorts",  "apparels", False, ["Shorts"]),
    ("bibs",    "Bibs",    "apparels", False, ["Bibs"]),
    ("track",   "Track",   "apparels", False, ["Track"]),
]


def _save_mapping(erp_group: str, cat_id: int, oc_name: str) -> None:
    existing = frappe.db.get_value(
        "Channel Category Mapping", {"item_group": erp_group}, "name"
    )
    if existing:
        frappe.db.set_value("Channel Category Mapping", existing, {
            "opencart_category_id": cat_id,
            "opencart_category_name": oc_name,
        })
        print(f"    [UPDATE] {erp_group!r} → '{oc_name}' (id={cat_id})")
    else:
        doc = frappe.get_doc({
            "doctype": "Channel Category Mapping",
            "item_group": erp_group,
            "opencart_category_id": cat_id,
            "opencart_category_name": oc_name,
        })
        doc.insert(ignore_permissions=True)
        print(f"    [CREATE] {erp_group!r} → '{oc_name}' (id={cat_id})")


def run():
    from erpmin_integrations.opencart.api import get_client

    client = get_client()
    if not client:
        print("ERROR: OpenCart not enabled or settings not configured.")
        return

    key_to_cat_id: dict[str, int] = {}

    for key, oc_name, parent_key, is_top, item_groups in CATEGORIES:
        parent_cat_id = 0 if parent_key is None else key_to_cat_id.get(parent_key, 0)

        cat_id = client.get_or_create_category(oc_name, parent_id=parent_cat_id, top=is_top)
        key_to_cat_id[key] = cat_id
        print(f"[OK] '{oc_name}' (parent_id={parent_cat_id}) → category_id={cat_id}")

        for erp_group in item_groups:
            if not frappe.db.exists("Item Group", erp_group):
                print(f"    [SKIP] Item Group '{erp_group}' not found in ERPNext")
                continue
            _save_mapping(erp_group, cat_id, oc_name)

    frappe.db.commit()
    print("\nDone! All OpenCart categories created and ERPNext mappings saved.")
