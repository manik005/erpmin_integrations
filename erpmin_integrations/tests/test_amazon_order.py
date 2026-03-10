import frappe
from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


class TestGetOrCreateCustomer(FrappeTestCase):
    @patch("frappe.db.get_value")
    @patch("frappe.new_doc")
    def test_deduplicates_by_email(self, mock_new_doc, mock_get_value):
        # first call (by email) returns existing customer; second call (by name) should not be needed
        mock_get_value.side_effect = lambda dt, filters, field=None: (
            "Existing Customer" if filters.get("email_id") else None
        )
        buyer = {"BuyerEmail": "email@test.com", "BuyerName": "Test Buyer"}
        settings = MagicMock()
        settings.default_customer_group = "Individual"
        settings.default_territory = "India"

        from erpmin_integrations.amazon.order import _get_or_create_customer
        result = _get_or_create_customer(buyer, "ORDER-1", settings)
        self.assertEqual(result, "Existing Customer")
        mock_new_doc.assert_not_called()

    @patch("frappe.db.get_value", return_value=None)
    @patch("frappe.new_doc")
    def test_creates_customer_with_email(self, mock_new_doc, _):
        customer_doc = MagicMock()
        customer_doc.name = "New Customer"
        mock_new_doc.return_value = customer_doc

        buyer = {"BuyerEmail": "new@test.com", "BuyerName": "New Buyer"}
        settings = MagicMock()
        settings.default_customer_group = "Individual"
        settings.default_territory = "India"

        from erpmin_integrations.amazon.order import _get_or_create_customer
        _get_or_create_customer(buyer, "ORDER-2", settings)
        self.assertEqual(customer_doc.email_id, "new@test.com")
        customer_doc.insert.assert_called_once()


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
