"""
cleanup_opencart_options.py

Removes OpenCart product option / option value rows for Item Attributes
that are now marked as role=Filter or role=None. Run once after deploying
the attribute role feature.

Run from inside the ERPNext container:
    bench --site erp.local execute \
        erpmin_integrations.migrate_item_structure.cleanup_opencart_options.run
"""

import os

import frappe
import pymysql

from erpmin_integrations.opencart.api import get_client


def run():
    client = get_client()
    if not client:
        print("ERROR: OpenCart not enabled or not configured.")
        return

    # Collect all attribute names that are NOT options
    non_option_attrs = frappe.db.sql("""
        SELECT attribute_name
        FROM `tabItem Attribute`
        WHERE COALESCE(custom_opencart_role, 'Option') != 'Option'
    """, pluck="attribute_name")

    if not non_option_attrs:
        print("No non-option attributes found. Nothing to clean up.")
        return

    print(f"Attributes to remove from OpenCart options: {non_option_attrs}")

    # Get option_ids for these attribute names from OpenCart
    result = client._get("/api/v1/options")
    all_options = result.get("options", [])
    option_ids_to_remove = [
        int(o["option_id"])
        for o in all_options
        if o.get("name") in non_option_attrs
    ]

    if not option_ids_to_remove:
        print("None of these attributes exist as OpenCart options. Nothing to do.")
        return

    print(f"OpenCart option IDs to remove from products: {option_ids_to_remove}")

    db_host = os.environ.get("OPENCART_DB_HOST") or frappe.conf.get("opencart_db_host") or "mysql"
    db_user = os.environ.get("OPENCART_DB_USER") or frappe.conf.get("opencart_db_user") or "opencart_user"
    db_password = os.environ.get("OPENCART_DB_PASSWORD") or frappe.conf.get("opencart_db_password") or "opencart123"
    db_name = os.environ.get("OPENCART_DB_NAME") or frappe.conf.get("opencart_db_name") or "opencart_db"

    conn = pymysql.connect(host=db_host, user=db_user, password=db_password, database=db_name)

    try:
        cursor = conn.cursor()
        placeholders = ",".join(["%s"] * len(option_ids_to_remove))

        # Delete option value rows first (FK constraint)
        cursor.execute(f"""
            DELETE pov FROM oc_product_option_value pov
            JOIN oc_product_option po ON po.product_option_id = pov.product_option_id
            WHERE po.option_id IN ({placeholders})
        """, option_ids_to_remove)
        deleted_values = cursor.rowcount

        # Delete option rows
        cursor.execute(f"""
            DELETE FROM oc_product_option
            WHERE option_id IN ({placeholders})
        """, option_ids_to_remove)
        deleted_options = cursor.rowcount

        conn.commit()
        print(f"Removed {deleted_options} product option rows and {deleted_values} option value rows.")
    finally:
        conn.close()

    print("Done. Run full_product_sync to re-sync all products with correct roles.")
