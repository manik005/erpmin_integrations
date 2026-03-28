from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase


def _make_dn(items=None, lr_no="", transporter_name=""):
    dn = MagicMock()
    dn.name = "DN-001"
    dn.lr_no = lr_no
    dn.transporter_name = transporter_name
    dn.items = items or []
    return dn


def _make_dn_item(against_sales_order="SO-001"):
    item = MagicMock()
    item.against_sales_order = against_sales_order
    return item


class TestOnDeliveryNoteSubmit(FrappeTestCase):

    @patch("erpmin_integrations.opencart.fulfillment.frappe.enqueue")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.db.get_value")
    def test_enqueues_when_opencart_order(self, mock_get_value, mock_enqueue):
        mock_get_value.side_effect = lambda dt, name, field: (
            "OpenCart" if field == "custom_channel" else "OC-12345"
        )
        from erpmin_integrations.opencart.fulfillment import on_delivery_note_submit
        dn = _make_dn(items=[_make_dn_item("SO-001")])
        on_delivery_note_submit(dn)
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        self.assertEqual(call_kwargs["opencart_order_id"], "OC-12345")

    @patch("erpmin_integrations.opencart.fulfillment.frappe.enqueue")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.db.get_value")
    def test_skips_non_opencart_channel(self, mock_get_value, mock_enqueue):
        mock_get_value.return_value = "Amazon"
        from erpmin_integrations.opencart.fulfillment import on_delivery_note_submit
        dn = _make_dn(items=[_make_dn_item("SO-001")])
        on_delivery_note_submit(dn)
        mock_enqueue.assert_not_called()

    @patch("erpmin_integrations.opencart.fulfillment.frappe.enqueue")
    def test_skips_when_no_sales_order(self, mock_enqueue):
        from erpmin_integrations.opencart.fulfillment import on_delivery_note_submit
        dn = _make_dn(items=[_make_dn_item(against_sales_order=None)])
        on_delivery_note_submit(dn)
        mock_enqueue.assert_not_called()

    @patch("erpmin_integrations.opencart.fulfillment.frappe.enqueue")
    def test_skips_when_no_items(self, mock_enqueue):
        from erpmin_integrations.opencart.fulfillment import on_delivery_note_submit
        dn = _make_dn(items=[])
        on_delivery_note_submit(dn)
        mock_enqueue.assert_not_called()

    @patch("erpmin_integrations.opencart.fulfillment.frappe.enqueue")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.db.get_value")
    def test_skips_when_no_marketplace_order_id(self, mock_get_value, mock_enqueue):
        mock_get_value.side_effect = lambda dt, name, field: (
            "OpenCart" if field == "custom_channel" else ""
        )
        from erpmin_integrations.opencart.fulfillment import on_delivery_note_submit
        dn = _make_dn(items=[_make_dn_item("SO-001")])
        on_delivery_note_submit(dn)
        mock_enqueue.assert_not_called()


class TestSendShipmentUpdate(FrappeTestCase):

    def _mock_dn(self, lr_no="", transporter_name="", so_name="SO-001"):
        dn = MagicMock()
        dn.name = "DN-001"
        dn.lr_no = lr_no
        dn.transporter_name = transporter_name
        item = MagicMock()
        item.against_sales_order = so_name
        dn.items = [item]
        return dn

    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.get_doc")
    def test_calls_update_order_status_with_shipped_id(self, mock_get_doc, mock_get_client):
        mock_get_doc.return_value = self._mock_dn()
        client = MagicMock()
        mock_get_client.return_value = client
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        send_shipment_update("DN-001", "OC-123")
        client.update_order_status.assert_called_once_with("OC-123", 5, "Shipped")

    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.get_doc")
    def test_comment_includes_carrier_and_tracking(self, mock_get_doc, mock_get_client):
        mock_get_doc.return_value = self._mock_dn(lr_no="TRK123", transporter_name="Delhivery")
        client = MagicMock()
        mock_get_client.return_value = client
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        send_shipment_update("DN-001", "OC-123")
        _, _, comment = client.update_order_status.call_args[0]
        self.assertIn("Delhivery", comment)
        self.assertIn("TRK123", comment)

    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.get_doc")
    def test_comment_includes_tracking_only(self, mock_get_doc, mock_get_client):
        mock_get_doc.return_value = self._mock_dn(lr_no="TRK999", transporter_name="")
        client = MagicMock()
        mock_get_client.return_value = client
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        send_shipment_update("DN-001", "OC-123")
        _, _, comment = client.update_order_status.call_args[0]
        self.assertIn("TRK999", comment)
        self.assertNotIn("via", comment)

    @patch("erpmin_integrations.opencart.fulfillment.frappe.db.get_value")
    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.get_doc")
    def test_falls_back_to_so_shipping_method_when_no_transporter(
        self, mock_get_doc, mock_get_client, mock_db_get
    ):
        mock_get_doc.return_value = self._mock_dn(transporter_name="")
        mock_db_get.return_value = "Ekart"
        client = MagicMock()
        mock_get_client.return_value = client
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        send_shipment_update("DN-001", "OC-123")
        _, _, comment = client.update_order_status.call_args[0]
        self.assertIn("Ekart", comment)

    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    def test_does_nothing_when_client_unavailable(self, mock_get_client):
        mock_get_client.return_value = None
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        # Should not raise
        send_shipment_update("DN-001", "OC-123")

    @patch("erpmin_integrations.opencart.fulfillment.frappe.log_error")
    @patch("erpmin_integrations.opencart.fulfillment.get_client")
    @patch("erpmin_integrations.opencart.fulfillment.frappe.get_doc")
    def test_logs_error_on_api_failure(self, mock_get_doc, mock_get_client, mock_log_error):
        mock_get_doc.return_value = self._mock_dn()
        client = MagicMock()
        client.update_order_status.side_effect = Exception("API down")
        mock_get_client.return_value = client
        from erpmin_integrations.opencart.fulfillment import send_shipment_update
        # Should not raise — logs the error instead
        send_shipment_update("DN-001", "OC-123")
        mock_log_error.assert_called_once()
