import csv
import io

import frappe
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    import_category_mappings,
    get_category_mapping_template,
)


class TestImportCategoryMappings(FrappeTestCase):
    def setUp(self):
        frappe.db.delete("Channel Category Mapping", {"item_group": ["like", "_BulkTest%"]})
        for g in ("_BulkTest Group A", "_BulkTest Group B"):
            if not frappe.db.exists("Item Group", g):
                doc = frappe.new_doc("Item Group")
                doc.item_group_name = g
                doc.parent_item_group = "All Item Groups"
                doc.insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.delete("Channel Category Mapping", {"item_group": ["like", "_BulkTest%"]})

    def _make_csv(self, rows):
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["item_group", "opencart_category_id", "opencart_category_name", "amazon_product_type"],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    def test_import_creates_new_records(self):
        csv_data = self._make_csv([
            {"item_group": "_BulkTest Group A", "opencart_category_id": "10",
             "opencart_category_name": "Cat A", "amazon_product_type": "CLOTHING"},
        ])
        result = import_category_mappings(csv_data)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], 0)
        val = frappe.db.get_value(
            "Channel Category Mapping",
            {"item_group": "_BulkTest Group A"},
            "amazon_product_type",
        )
        self.assertEqual(val, "CLOTHING")

    def test_import_upserts_existing(self):
        csv_data = self._make_csv([
            {"item_group": "_BulkTest Group A", "opencart_category_id": "10",
             "opencart_category_name": "Cat A", "amazon_product_type": "CLOTHING"},
        ])
        import_category_mappings(csv_data)
        csv_data2 = self._make_csv([
            {"item_group": "_BulkTest Group A", "opencart_category_id": "10",
             "opencart_category_name": "Cat A Updated", "amazon_product_type": "BEAUTY"},
        ])
        result = import_category_mappings(csv_data2)
        self.assertEqual(result["imported"], 1)
        val = frappe.db.get_value(
            "Channel Category Mapping",
            {"item_group": "_BulkTest Group A"},
            "amazon_product_type",
        )
        self.assertEqual(val, "BEAUTY")

    def test_unknown_item_group_reported_in_errors(self):
        csv_data = self._make_csv([
            {"item_group": "_BulkTest NONEXISTENT", "opencart_category_id": "99",
             "opencart_category_name": "X", "amazon_product_type": "PRODUCT"},
        ])
        result = import_category_mappings(csv_data)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["row"], 2)

    def test_template_has_correct_headers(self):
        template = get_category_mapping_template()
        reader = csv.DictReader(io.StringIO(template))
        self.assertIn("item_group", reader.fieldnames)
        self.assertIn("amazon_product_type", reader.fieldnames)
