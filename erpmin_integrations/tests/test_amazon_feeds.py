from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.amazon.feeds import build_inventory_feed


class TestFeeds(FrappeTestCase):
    def test_merchant_identifier_in_feed(self):
        xml = build_inventory_feed([{"sku": "SKU-1", "qty": 5}], seller_id="SELLER123")
        self.assertIn("SELLER123", xml)
        self.assertNotIn(">_<", xml)

    def test_feed_contains_all_skus(self):
        items = [{"sku": f"SKU-{i}", "qty": i} for i in range(3)]
        xml = build_inventory_feed(items, seller_id="S")
        for i in range(3):
            self.assertIn(f"SKU-{i}", xml)

    @patch("erpmin_integrations.amazon.feeds.get_client")
    @patch("erpmin_integrations.amazon.feeds.get_settings")
    @patch("frappe.new_doc")
    def test_submit_feed_saves_feed_log(self, mock_new_doc, mock_settings, mock_client):
        settings = MagicMock()
        settings.marketplace_id = "MKT1"
        settings.seller_id = "S1"
        mock_settings.return_value = settings

        client = MagicMock()
        client.post.side_effect = [
            {"feedDocumentId": "doc1", "url": "https://example.com/upload"},
            {"feedId": "feed1"},
        ]
        mock_client.return_value = client

        log_doc = MagicMock()
        mock_new_doc.return_value = log_doc

        with patch("requests.put") as mock_put:
            mock_put.return_value = MagicMock(ok=True, raise_for_status=lambda: None)
            from erpmin_integrations.amazon.feeds import submit_feed
            feed_id = submit_feed("POST_INVENTORY_AVAILABILITY_DATA", "<xml/>", item_count=1)

        self.assertEqual(feed_id, "feed1")
        mock_new_doc.assert_called_with("Amazon Feed Log")
        self.assertEqual(log_doc.feed_id, "feed1")
        log_doc.insert.assert_called_once()
