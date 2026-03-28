from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe


def _make_doc(channel="Wholesale", customer="CUST-001", items=None):
    doc = MagicMock()
    doc.custom_channel = channel
    doc.customer = customer
    doc.items = items or []
    return doc


def _make_row(item_code, qty, idx=1):
    row = MagicMock()
    row.item_code = item_code
    row.qty = qty
    row.idx = idx
    return row


class TestWholesaleMinQty(FrappeTestCase):

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_passes_when_qty_meets_minimum(self, mock_get_value):
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 10
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[_make_row("ITEM-001", 10)])
        # Should not raise
        _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_raises_when_qty_below_minimum(self, mock_get_value):
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 50
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[_make_row("ITEM-001", 5)])
        with self.assertRaises(frappe.exceptions.ValidationError):
            _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_skips_item_with_min_qty_zero(self, mock_get_value):
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 0
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[_make_row("ITEM-001", 1)])
        # min_order_qty=0 means no restriction — should not raise
        _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_skips_non_wholesale_channel(self, mock_get_value):
        # Customer is not Wholesale, channel is Amazon
        mock_get_value.side_effect = lambda dt, name, field: (
            "Individual" if dt == "Customer" else 100
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(channel="Amazon", items=[_make_row("ITEM-001", 1)])
        # Should not raise — not a wholesale order
        _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_triggers_via_customer_group_fallback(self, mock_get_value):
        """Channel may be blank but customer group is Wholesale — should still enforce."""
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 20
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(channel="", items=[_make_row("ITEM-001", 5)])
        with self.assertRaises(frappe.exceptions.ValidationError):
            _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_multiple_rows_all_errors_reported(self, mock_get_value):
        """All failing rows should appear in the error message, not just the first."""
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 50
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[
            _make_row("ITEM-001", 5, idx=1),
            _make_row("ITEM-002", 3, idx=2),
        ])
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            _enforce_wholesale_min_qty(doc)
        msg = str(ctx.exception)
        self.assertIn("ITEM-001", msg)
        self.assertIn("ITEM-002", msg)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_passes_when_qty_exceeds_minimum(self, mock_get_value):
        mock_get_value.side_effect = lambda dt, name, field: (
            "Wholesale" if dt == "Customer" else 10
        )
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[_make_row("ITEM-001", 200)])
        _enforce_wholesale_min_qty(doc)

    @patch("erpmin_integrations.sales_order.frappe.db.get_value")
    def test_empty_items_list_does_not_raise(self, mock_get_value):
        mock_get_value.return_value = "Wholesale"
        from erpmin_integrations.sales_order import _enforce_wholesale_min_qty
        doc = _make_doc(items=[])
        _enforce_wholesale_min_qty(doc)
