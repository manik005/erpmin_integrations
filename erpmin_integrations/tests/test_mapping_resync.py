from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    enqueue_resync_for_group,
)


class TestMappingResync(FrappeTestCase):
    @patch("frappe.get_all")
    @patch("frappe.enqueue")
    def test_enqueues_resync_for_affected_items(self, mock_enqueue, mock_get_all):
        mock_get_all.return_value = ["ITEM-001", "ITEM-002"]

        enqueue_resync_for_group("Clothing")

        self.assertEqual(mock_enqueue.call_count, 2)
        call_args_list = [c[1]["item_code"] for c in mock_enqueue.call_args_list]
        self.assertIn("ITEM-001", call_args_list)
        self.assertIn("ITEM-002", call_args_list)

    @patch("frappe.get_all", return_value=[])
    @patch("frappe.enqueue")
    def test_no_enqueue_when_no_items(self, mock_enqueue, _):
        enqueue_resync_for_group("EmptyGroup")
        mock_enqueue.assert_not_called()
