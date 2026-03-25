from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


class TestAmazonProduct(FrappeTestCase):
    def _make_item(self, product_type_override="", group_product_type="CLOTHING"):
        item = MagicMock()
        item.name = "ITEM-001"
        item.item_name = "Test Item"
        item.custom_sync_to_amazon = 1
        item.custom_amazon_sku = "SKU-001"
        item.custom_amazon_product_type = product_type_override
        item.item_group = "Clothing"
        item.barcodes = []
        item.description = ""
        item.custom_amazon_brand = ""
        item.custom_amazon_color = ""
        item.custom_amazon_size = ""
        item.custom_amazon_bullet_points = ""
        item.custom_amazon_description = ""
        # Flat (non-variant) item — must be explicitly falsy for routing logic
        item.has_variants = 0
        item.variant_of = None
        return item

    def _make_settings(self, price_list=None):
        settings = MagicMock()
        settings.seller_id = "SELLER123"
        settings.marketplace_id = "A21TJRUUN4KGV"
        settings.default_price_list = price_list
        return settings

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_sync_uses_group_mapping_product_type(
        self, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item(product_type_override="")
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings()
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        url = client.put_listing.call_args[0][0]
        self.assertIn("productType=CLOTHING", url)

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_item_override_takes_priority_over_group(
        self, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item(product_type_override="BEAUTY")
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings()
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        url = client.put_listing.call_args[0][0]
        self.assertIn("productType=BEAUTY", url)

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value=None)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_falls_back_to_product_when_no_mapping(
        self, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item(product_type_override="")
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings()
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        url = client.put_listing.call_args[0][0]
        self.assertIn("productType=PRODUCT", url)

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    @patch("frappe.log_error")
    def test_sets_error_status_on_failure(
        self, mock_log_error, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item()
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings()
        client = MagicMock()
        client.put_listing.side_effect = Exception("SP-API error")
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        # Should have set Error status
        set_value_calls = mock_set_value.call_args_list
        error_call = next(
            (c for c in set_value_calls if c[0][2].get("custom_amazon_status") == "Error"),
            None,
        )
        self.assertIsNotNone(error_call)

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    @patch("frappe.db.get_value", return_value=499.00)
    def test_price_included_in_payload_when_price_list_set(
        self, mock_db_get, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item()
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings(price_list="Standard Selling")
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        payload = client.put_listing.call_args[0][1]
        offer = payload["attributes"].get("purchasable_offer")
        self.assertIsNotNone(offer)
        self.assertEqual(offer[0]["our_price"][0]["schedule"][0]["value_with_tax"], 499.0)
        self.assertEqual(offer[0]["currency"], "INR")

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_price_omitted_when_no_price_list(
        self, mock_set_value, mock_get_doc, mock_get_ptype, mock_get_settings, mock_get_client
    ):
        item = self._make_item()
        mock_get_doc.return_value = item
        mock_get_settings.return_value = self._make_settings(price_list=None)
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("ITEM-001")

        payload = client.put_listing.call_args[0][1]
        self.assertNotIn("purchasable_offer", payload["attributes"])
