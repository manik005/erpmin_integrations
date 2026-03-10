import csv
import io

import frappe
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.bulk_import import import_item_amazon_fields, get_item_amazon_template


_UPDATABLE_FIELDS = [
    "custom_amazon_product_type",
    "custom_amazon_brand",
    "custom_amazon_color",
    "custom_amazon_size",
    "custom_amazon_bullet_points",
    "custom_amazon_description",
]


class TestImportItemAmazonFields(FrappeTestCase):
    def setUp(self):
        if not frappe.db.exists("Item", "_TestAmazonItem"):
            item = frappe.new_doc("Item")
            item.item_code = "_TestAmazonItem"
            item.item_name = "_TestAmazonItem"
            item.item_group = "All Item Groups"
            item.stock_uom = "Nos"
            item.gst_hsn_code = "000000"
            item.insert(ignore_permissions=True)

    def tearDown(self):
        if frappe.db.exists("Item", "_TestAmazonItem"):
            frappe.delete_doc("Item", "_TestAmazonItem", ignore_permissions=True, force=True)

    def _make_csv(self, rows):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["item_code"] + _UPDATABLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    def test_updates_item_fields(self):
        csv_data = self._make_csv([{
            "item_code": "_TestAmazonItem",
            "custom_amazon_product_type": "BEAUTY",
            "custom_amazon_brand": "TestBrand",
            "custom_amazon_color": "",
            "custom_amazon_size": "",
            "custom_amazon_bullet_points": "",
            "custom_amazon_description": "",
        }])
        result = import_item_amazon_fields(csv_data)
        self.assertEqual(result["imported"], 1)
        val = frappe.db.get_value("Item", "_TestAmazonItem", "custom_amazon_product_type")
        self.assertEqual(val, "BEAUTY")

    def test_unknown_item_code_reported_in_errors(self):
        csv_data = self._make_csv([{
            "item_code": "_NonExistentItem9999",
            "custom_amazon_product_type": "CLOTHING",
            "custom_amazon_brand": "", "custom_amazon_color": "",
            "custom_amazon_size": "", "custom_amazon_bullet_points": "",
            "custom_amazon_description": "",
        }])
        result = import_item_amazon_fields(csv_data)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["errors"][0]["row"], 2)

    def test_template_has_item_code_column(self):
        template = get_item_amazon_template()
        reader = csv.DictReader(io.StringIO(template))
        self.assertIn("item_code", reader.fieldnames)
        self.assertIn("custom_amazon_product_type", reader.fieldnames)
