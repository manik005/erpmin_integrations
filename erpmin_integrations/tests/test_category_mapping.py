import frappe
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    get_category_id,
    get_amazon_product_type,
)


class TestChannelCategoryMapping(FrappeTestCase):
    def setUp(self):
        if not frappe.db.exists("Item Group", "_Test CCM Group"):
            ig = frappe.new_doc("Item Group")
            ig.item_group_name = "_Test CCM Group"
            ig.parent_item_group = "All Item Groups"
            ig.insert(ignore_permissions=True)

        frappe.db.delete("Channel Category Mapping", {"item_group": "_Test CCM Group"})
        doc = frappe.new_doc("Channel Category Mapping")
        doc.item_group = "_Test CCM Group"
        doc.opencart_category_id = 99
        doc.opencart_category_name = "Test"
        doc.amazon_product_type = "CLOTHING"
        doc.insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.delete("Channel Category Mapping", {"item_group": "_Test CCM Group"})
        if frappe.db.exists("Item Group", "_Test CCM Group"):
            frappe.delete_doc("Item Group", "_Test CCM Group", ignore_permissions=True, force=True)

    def test_get_category_id(self):
        self.assertEqual(get_category_id("_Test CCM Group"), 99)

    def test_get_amazon_product_type(self):
        self.assertEqual(get_amazon_product_type("_Test CCM Group"), "CLOTHING")

    def test_get_amazon_product_type_missing(self):
        self.assertIsNone(get_amazon_product_type("_Nonexistent Group"))
