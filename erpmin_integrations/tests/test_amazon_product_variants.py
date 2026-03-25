from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


def _make_settings():
    s = MagicMock()
    s.seller_id = "SELLER123"
    s.marketplace_id = "A21TJRUUN4KGV"
    s.default_price_list = "Standard Selling"
    return s


def _make_template(item_code="TSHIRT"):
    t = MagicMock()
    t.name = item_code
    t.item_name = "Cotton T-Shirt"
    t.item_group = "Apparel"
    t.description = ""
    t.barcodes = []
    t.custom_amazon_brand = ""
    t.custom_amazon_bullet_points = ""
    t.custom_amazon_description = ""
    t.custom_amazon_sku = ""
    t.custom_amazon_product_type = ""
    t.has_variants = 1
    t.variant_of = None
    t.custom_sync_to_amazon = 1
    t.attributes = []
    return t


def _make_variant(item_code="TSHIRT-RED-L", template_code="TSHIRT"):
    v = MagicMock()
    v.name = item_code
    v.item_name = "Cotton T-Shirt"
    v.item_group = "Apparel"
    v.description = ""
    v.barcodes = []
    v.custom_amazon_brand = ""
    v.custom_amazon_bullet_points = ""
    v.custom_amazon_description = ""
    v.custom_amazon_sku = item_code
    v.custom_amazon_product_type = ""
    v.has_variants = 0
    v.variant_of = template_code
    v.custom_sync_to_amazon = 1
    v.attributes = []

    attr = MagicMock()
    attr.attribute = "Color"
    attr.attribute_value = "Red"
    v.attributes = [attr]
    return v


class TestAmazonVariantSync(FrappeTestCase):

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    @patch("frappe.db.get_value", return_value=499.0)
    def test_variant_sync_puts_parent_and_child_asin(
        self, mock_db_get, mock_set_value, mock_get_doc, mock_ptype, mock_settings, mock_client
    ):
        template = _make_template()
        variant = _make_variant()

        def _get_doc(doctype, name=None, **kwargs):
            if doctype != "Item":
                raise ValueError(f"Unexpected get_doc call: {doctype!r}")
            return variant if name == "TSHIRT-RED-L" else template

        mock_get_doc.side_effect = _get_doc
        mock_settings.return_value = _make_settings()
        client = MagicMock()
        mock_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        with patch("erpmin_integrations.amazon.product.now_datetime", return_value="2026-01-01 00:00:00"):
            sync_item("TSHIRT-RED-L")

        # Two put_listing calls: parent + child
        self.assertEqual(client.put_listing.call_count, 2)

        # One call should be for the parent ASIN (parentage=parent)
        all_payloads = [c[0][1] for c in client.put_listing.call_args_list]
        parent_payloads = [
            p for p in all_payloads
            if p.get("attributes", {}).get("parentage", [{}])[0].get("value") == "parent"
        ]
        self.assertEqual(len(parent_payloads), 1, "Expected exactly one parent ASIN payload")

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("erpmin_integrations.amazon.product.get_amazon_product_type", return_value="CLOTHING")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    @patch("frappe.db.get_value", return_value=499.0)
    def test_variant_sync_child_has_parentage_child(
        self, mock_db_get, mock_set_value, mock_get_doc, mock_ptype, mock_settings, mock_client
    ):
        template = _make_template()
        variant = _make_variant()

        def _get_doc(doctype, name=None, **kwargs):
            if doctype != "Item":
                raise ValueError(f"Unexpected get_doc call: {doctype!r}")
            return variant if name == "TSHIRT-RED-L" else template

        mock_get_doc.side_effect = _get_doc
        mock_settings.return_value = _make_settings()
        client = MagicMock()
        mock_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        with patch("erpmin_integrations.amazon.product.now_datetime", return_value="2026-01-01 00:00:00"):
            sync_item("TSHIRT-RED-L")

        all_payloads = [c[0][1] for c in client.put_listing.call_args_list]
        child_payloads = [
            p for p in all_payloads
            if p.get("attributes", {}).get("parentage", [{}])[0].get("value") == "child"
        ]
        self.assertEqual(len(child_payloads), 1)
        child_attrs = child_payloads[0]["attributes"]
        self.assertIn("child_parent_sku_relationship", child_attrs)
        self.assertEqual(child_attrs["child_parent_sku_relationship"][0]["parent_sku"], "TSHIRT")

    @patch("erpmin_integrations.amazon.product.get_client")
    @patch("erpmin_integrations.amazon.product.get_settings")
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_template_item_is_skipped(
        self, mock_set_value, mock_get_doc, mock_settings, mock_client
    ):
        template = _make_template()
        mock_get_doc.return_value = template
        mock_settings.return_value = _make_settings()
        client = MagicMock()
        mock_client.return_value = client

        from erpmin_integrations.amazon.product import sync_item
        sync_item("TSHIRT")

        client.put_listing.assert_not_called()
