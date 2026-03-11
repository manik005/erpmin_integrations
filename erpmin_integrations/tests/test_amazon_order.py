import frappe
from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


class TestCreateSalesOrderCustomerHandoff(FrappeTestCase):
    """Verify _create_sales_order delegates customer lookup to the shared module."""

    @patch("erpmin_integrations.amazon.order.get_or_create_customer", return_value="Amazon Customer")
    @patch("erpmin_integrations.amazon.order._normalize_customer_data")
    def test_calls_shared_get_or_create_customer(self, mock_normalize, mock_get_or_create):
        mock_normalize.return_value = {
            "name": "Test Buyer",
            "email": "email@test.com",
            "phone": "",
            "source": "Amazon",
            "shipping_address": None,
            "billing_address": None,
            "gstin": "",
        }

        amz_order = {
            "AmazonOrderId": "ORDER-1",
            "OrderStatus": "Unshipped",
            "BuyerInfo": {"BuyerEmail": "email@test.com", "BuyerName": "Test Buyer"},
        }
        settings = MagicMock()
        settings.default_warehouse = "Main Warehouse - ERP"
        client = MagicMock()
        client.get_order_items.return_value = {
            "payload": {
                "OrderItems": [
                    {
                        "SellerSKU": "SKU-1",
                        "QuantityOrdered": 1,
                        "ItemPrice": {"Amount": "100.0"},
                        "OrderItemId": "OI-1",
                    }
                ]
            }
        }

        so_doc = MagicMock()
        so_doc.items = []

        with patch("frappe.db.exists", return_value=False), \
             patch("frappe.new_doc", return_value=so_doc), \
             patch("erpmin_integrations.amazon.order._resolve_item_code", return_value="SKU-1"):
            from erpmin_integrations.amazon.order import _create_sales_order
            _create_sales_order(client, amz_order, settings)

        mock_normalize.assert_called_once_with(amz_order)
        mock_get_or_create.assert_called_once_with(mock_normalize.return_value)


class TestResolveItemCode(FrappeTestCase):
    @patch("frappe.db.exists", return_value=True)
    def test_direct_match_by_item_code(self, _):
        from erpmin_integrations.amazon.order import _resolve_item_code
        self.assertEqual(_resolve_item_code("SKU-1"), "SKU-1")

    @patch("frappe.db.exists", return_value=False)
    @patch("frappe.db.get_value", return_value="ITEM-001")
    def test_fallback_to_amazon_sku_field(self, _, __):
        from erpmin_integrations.amazon.order import _resolve_item_code
        self.assertEqual(_resolve_item_code("AMZ-SKU"), "ITEM-001")

    @patch("frappe.db.exists", return_value=False)
    @patch("frappe.db.get_value", return_value=None)
    def test_returns_none_when_not_found(self, _, __):
        from erpmin_integrations.amazon.order import _resolve_item_code
        self.assertIsNone(_resolve_item_code("UNKNOWN"))

    def test_returns_none_for_none_sku(self):
        from erpmin_integrations.amazon.order import _resolve_item_code
        self.assertIsNone(_resolve_item_code(None))


class TestAmazonCustomerNormalizer(FrappeTestCase):
    def test_normalizes_full_order(self):
        from erpmin_integrations.amazon.order import _normalize_customer_data
        amz_order = {
            "BuyerInfo": {
                "BuyerEmail": "buyer@example.com",
                "BuyerName": "John Smith",
                "BuyerTaxInfo": {"TaxingRegion": "29ABCDE1234F1Z5"},
            },
            "ShippingAddress": {
                "AddressLine1": "12 MG Road",
                "AddressLine2": "",
                "City": "Bengaluru",
                "StateOrRegion": "Karnataka",
                "PostalCode": "560001",
                "CountryCode": "IN",
                "Phone": "9876543210",
            },
        }
        data = _normalize_customer_data(amz_order)
        self.assertEqual(data["name"], "John Smith")
        self.assertEqual(data["email"], "buyer@example.com")
        self.assertEqual(data["source"], "Amazon")
        self.assertEqual(data["gstin"], "29ABCDE1234F1Z5")
        self.assertEqual(data["shipping_address"]["line1"], "12 MG Road")
        self.assertEqual(data["shipping_address"]["phone"], "9876543210")
        self.assertIsNone(data["billing_address"])
