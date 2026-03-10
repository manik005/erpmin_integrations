from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


class TestFulfillment(FrappeTestCase):
    @patch("erpmin_integrations.amazon.fulfillment.get_client")
    @patch("erpmin_integrations.amazon.fulfillment._get_marketplace_id", return_value="A21TJRUUN4KGV")
    @patch("frappe.get_doc")
    def test_uses_amazon_order_item_id(self, mock_get_doc, _, mock_get_client):
        item = MagicMock()
        item.item_code = "ITEM-001"
        item.qty = 2
        item.against_sales_order = "SO-001"
        item.so_detail = "ERPNEXT-ROW-ID"
        item.custom_amazon_order_item_id = "AMAZON-ITEM-ID-123"

        dn = MagicMock()
        dn.name = "DN-001"
        dn.items = [item]
        dn.lr_no = "TRACK123"
        dn.transporter_name = "Delhivery"
        dn.posting_date = MagicMock()
        dn.posting_date.strftime.return_value = "2026-03-10T00:00:00Z"

        mock_get_doc.return_value = dn
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.fulfillment import send_shipment_confirmation
        send_shipment_confirmation("DN-001", "AMZ-ORDER-1")

        payload = client.confirm_shipment.call_args[0][1]
        order_items = payload["packageDetail"]["orderItems"]
        self.assertEqual(order_items[0]["orderItemId"], "AMAZON-ITEM-ID-123")

    @patch("erpmin_integrations.amazon.fulfillment.get_client")
    @patch("erpmin_integrations.amazon.fulfillment._get_marketplace_id", return_value="A21TJRUUN4KGV")
    @patch("frappe.get_doc")
    def test_falls_back_to_so_detail_when_no_amazon_item_id(self, mock_get_doc, _, mock_get_client):
        item = MagicMock()
        item.item_code = "ITEM-001"
        item.qty = 1
        item.against_sales_order = "SO-001"
        item.so_detail = "ERPNEXT-ROW-ID"
        item.custom_amazon_order_item_id = ""

        dn = MagicMock()
        dn.name = "DN-001"
        dn.items = [item]
        dn.lr_no = ""
        dn.transporter_name = "Unknown"
        dn.posting_date = MagicMock()
        dn.posting_date.strftime.return_value = "2026-03-10T00:00:00Z"

        mock_get_doc.return_value = dn
        client = MagicMock()
        mock_get_client.return_value = client

        from erpmin_integrations.amazon.fulfillment import send_shipment_confirmation
        send_shipment_confirmation("DN-001", "AMZ-ORDER-1")

        payload = client.confirm_shipment.call_args[0][1]
        order_items = payload["packageDetail"]["orderItems"]
        self.assertEqual(order_items[0]["orderItemId"], "ERPNEXT-ROW-ID")
