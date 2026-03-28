from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase


def _make_error_log(method="[OpenCart] sync failed", error="Traceback...", creation="2026-03-28 08:00:00"):
    e = MagicMock()
    e.method = method
    e.error = error
    e.creation = creation
    return e


def _make_bin_row(item_code, item_name, available_qty, warehouse="Main Warehouse",
                   sync_opencart=1, sync_amazon=0):
    row = MagicMock()
    row.item_code = item_code
    row.item_name = item_name
    row.available_qty = available_qty
    row.warehouse = warehouse
    row.custom_sync_to_opencart = sync_opencart
    row.custom_sync_to_amazon = sync_amazon
    return row


class TestGetAlertRecipients(FrappeTestCase):

    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_returns_list_of_emails(self, mock_gsv):
        mock_gsv.return_value = "admin@example.com, ops@example.com"
        from erpmin_integrations.utils.alerts import _get_alert_recipients
        result = _get_alert_recipients()
        self.assertEqual(result, ["admin@example.com", "ops@example.com"])

    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_returns_empty_when_not_configured(self, mock_gsv):
        mock_gsv.return_value = ""
        from erpmin_integrations.utils.alerts import _get_alert_recipients
        result = _get_alert_recipients()
        self.assertEqual(result, [])

    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_strips_whitespace(self, mock_gsv):
        mock_gsv.return_value = "  a@b.com  ,  c@d.com  "
        from erpmin_integrations.utils.alerts import _get_alert_recipients
        result = _get_alert_recipients()
        self.assertEqual(result, ["a@b.com", "c@d.com"])


class TestSendErrorDigest(FrappeTestCase):

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.get_all")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_sends_email_when_errors_exist(self, mock_gsv, mock_get_all, mock_sendmail):
        mock_gsv.side_effect = lambda doctype, field: (
            1 if field == "enable_error_digest" else "admin@example.com"
        )
        mock_get_all.return_value = [_make_error_log()]
        from erpmin_integrations.utils.alerts import send_error_digest
        send_error_digest()
        mock_sendmail.assert_called_once()
        subject = mock_sendmail.call_args[1]["subject"]
        self.assertIn("Integration Errors", subject)

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.get_all")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_disabled(self, mock_gsv, mock_get_all, mock_sendmail):
        mock_gsv.return_value = 0  # digest disabled
        from erpmin_integrations.utils.alerts import send_error_digest
        send_error_digest()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.get_all")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_no_errors(self, mock_gsv, mock_get_all, mock_sendmail):
        mock_gsv.side_effect = lambda doctype, field: (
            1 if field == "enable_error_digest" else "admin@example.com"
        )
        mock_get_all.return_value = []
        from erpmin_integrations.utils.alerts import send_error_digest
        send_error_digest()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.get_all")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_no_recipients(self, mock_gsv, mock_get_all, mock_sendmail):
        mock_gsv.side_effect = lambda doctype, field: (
            1 if field == "enable_error_digest" else ""
        )
        mock_get_all.return_value = [_make_error_log()]
        from erpmin_integrations.utils.alerts import send_error_digest
        send_error_digest()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.get_all")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_error_count_in_subject(self, mock_gsv, mock_get_all, mock_sendmail):
        mock_gsv.side_effect = lambda doctype, field: (
            1 if field == "enable_error_digest" else "admin@example.com"
        )
        mock_get_all.return_value = [_make_error_log(), _make_error_log("[Amazon] feed failed")]
        from erpmin_integrations.utils.alerts import send_error_digest
        send_error_digest()
        subject = mock_sendmail.call_args[1]["subject"]
        self.assertIn("2", subject)


class TestSendLowStockAlert(FrappeTestCase):

    def _gsv(self, warehouses=("Main Warehouse",), threshold=10, enabled=True, recipients="admin@example.com"):
        """Return a side_effect function for frappe.db.get_single_value."""
        def _side_effect(doctype, field):
            if field == "enable_low_stock_alerts":
                return 1 if enabled else 0
            if field == "low_stock_threshold":
                return threshold
            if field == "alert_email":
                return recipients
            if field == "default_warehouse":
                return warehouses[0] if warehouses else None
            return None
        return _side_effect

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.sql")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_sends_alert_for_low_stock_items(self, mock_gsv, mock_sql, mock_sendmail):
        mock_gsv.side_effect = self._gsv()
        mock_sql.return_value = [_make_bin_row("ITEM-001", "Test Item", 3)]
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        mock_sendmail.assert_called_once()
        subject = mock_sendmail.call_args[1]["subject"]
        self.assertIn("Low Stock", subject)

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_disabled(self, mock_gsv, mock_sendmail):
        mock_gsv.side_effect = self._gsv(enabled=False)
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.sql")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_no_low_stock_items(self, mock_gsv, mock_sql, mock_sendmail):
        mock_gsv.side_effect = self._gsv()
        mock_sql.return_value = []
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_skips_when_no_warehouse_configured(self, mock_gsv, mock_sendmail):
        mock_gsv.side_effect = self._gsv(warehouses=())
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        mock_sendmail.assert_not_called()

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.sql")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_item_count_in_subject(self, mock_gsv, mock_sql, mock_sendmail):
        mock_gsv.side_effect = self._gsv()
        mock_sql.return_value = [
            _make_bin_row("ITEM-001", "Item One", 2),
            _make_bin_row("ITEM-002", "Item Two", 0),
        ]
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        subject = mock_sendmail.call_args[1]["subject"]
        self.assertIn("2", subject)

    @patch("erpmin_integrations.utils.alerts.frappe.sendmail")
    @patch("erpmin_integrations.utils.alerts.frappe.db.sql")
    @patch("erpmin_integrations.utils.alerts.frappe.db.get_single_value")
    def test_custom_threshold_used(self, mock_gsv, mock_sql, mock_sendmail):
        mock_gsv.side_effect = self._gsv(threshold=5)
        mock_sql.return_value = [_make_bin_row("ITEM-001", "Item", 4)]
        from erpmin_integrations.utils.alerts import send_low_stock_alert
        send_low_stock_alert()
        # Verify threshold was passed to the SQL query
        sql_kwargs = mock_sql.call_args[0][1]
        self.assertEqual(sql_kwargs["threshold"], 5)
