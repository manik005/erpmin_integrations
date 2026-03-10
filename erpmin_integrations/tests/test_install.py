import frappe
from frappe.tests.utils import FrappeTestCase


class TestInstall(FrappeTestCase):
    def _field_exists(self, dt, fieldname):
        return frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})

    def test_item_amazon_fields_exist(self):
        new_fields = [
            "custom_amazon_product_type",
            "custom_amazon_brand",
            "custom_amazon_color",
            "custom_amazon_size",
            "custom_amazon_bullet_points",
            "custom_amazon_description",
            "custom_amazon_last_sync",
            "custom_amazon_sync_error",
        ]
        for fn in new_fields:
            self.assertTrue(self._field_exists("Item", fn), f"Missing Item field: {fn}")

    def test_so_item_amazon_order_item_id_exists(self):
        self.assertTrue(
            self._field_exists("Sales Order Item", "custom_amazon_order_item_id"),
            "Missing Sales Order Item field: custom_amazon_order_item_id",
        )
