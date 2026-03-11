from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase


class TestOpenCartCustomerNormalizer(FrappeTestCase):
    def test_normalizes_full_order(self):
        from erpmin_integrations.opencart.order import _normalize_customer_data
        oc_order = {
            "firstname": "Jane",
            "lastname": "Doe",
            "email": "jane@example.com",
            "telephone": "9876540001",
            "shipping_address_1": "44 Anna Salai",
            "shipping_address_2": "",
            "shipping_city": "Chennai",
            "shipping_zone": "Tamil Nadu",
            "shipping_postcode": "600002",
            "shipping_country": "India",
            "payment_address_1": "1 Billing St",
            "payment_address_2": "",
            "payment_city": "Chennai",
            "payment_zone": "Tamil Nadu",
            "payment_postcode": "600001",
            "payment_country": "India",
        }
        data = _normalize_customer_data(oc_order)
        self.assertEqual(data["name"], "Jane Doe")
        self.assertEqual(data["email"], "jane@example.com")
        self.assertEqual(data["phone"], "9876540001")
        self.assertEqual(data["source"], "OpenCart")
        self.assertEqual(data["shipping_address"]["line1"], "44 Anna Salai")
        self.assertEqual(data["billing_address"]["line1"], "1 Billing St")

    def test_no_name_falls_back_to_email(self):
        from erpmin_integrations.opencart.order import _normalize_customer_data
        data = _normalize_customer_data({"firstname": "", "lastname": "", "email": "anon@example.com", "telephone": ""})
        self.assertEqual(data["name"], "anon@example.com")

    def test_missing_shipping_address_returns_none(self):
        from erpmin_integrations.opencart.order import _normalize_customer_data
        data = _normalize_customer_data({"firstname": "Jane", "lastname": "Doe",
                                          "email": "jane2@example.com", "telephone": ""})
        self.assertIsNone(data["shipping_address"])
        self.assertIsNone(data["billing_address"])
