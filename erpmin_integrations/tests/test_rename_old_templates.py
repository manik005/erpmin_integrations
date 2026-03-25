# custom-apps/erpmin_integrations/erpmin_integrations/tests/test_rename_old_templates.py
import pytest
from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.migrate_item_structure.rename_old_templates import run


EXPECTED_RENAMES = [
    ("JERSEY",  "JERSEY-OLD"),
    ("T-SHIRT", "TSHIRT-OLD"),
    ("SHORTS",  "SHORTS-OLD"),
    ("BIBS",    "BIBS-OLD"),
    ("TRACK",   "TRACK-OLD"),
    ("PANTS",   "PANTS-OLD"),
]


class TestRenameOldTemplates(FrappeTestCase):

    def _make_mock_frappe(self):
        """Build a mock frappe where db.exists returns True for all old templates."""
        mock_frappe = MagicMock()
        mock_frappe.rename_doc.return_value = None
        mock_frappe.db.set_value.return_value = None
        mock_frappe.db.savepoint.return_value = None        # bare call, not context manager
        mock_frappe.db.rollback.return_value = None
        mock_frappe.db.commit.return_value = None
        mock_frappe.db.exists.return_value = True           # all old templates exist
        return mock_frappe

    def test_calls_rename_doc_for_all_templates(self):
        with patch("erpmin_integrations.migrate_item_structure.rename_old_templates.frappe",
                   self._make_mock_frappe()) as mock_frappe:
            run()

            actual_calls = [
                (c.args[1], c.args[2])
                for c in mock_frappe.rename_doc.call_args_list
            ]
            for old, new in EXPECTED_RENAMES:
                assert (old, new) in actual_calls, f"Expected rename {old} → {new}"

    def test_disables_all_renamed_templates(self):
        with patch("erpmin_integrations.migrate_item_structure.rename_old_templates.frappe",
                   self._make_mock_frappe()) as mock_frappe:
            run()

            disabled_items = [
                c.args[1]
                for c in mock_frappe.db.set_value.call_args_list
                if c.args[0] == "Item" and c.args[3] == 1  # disabled=1
            ]
            for _, new_name in EXPECTED_RENAMES:
                assert new_name in disabled_items, f"{new_name} not disabled"

    def test_savepoint_called_once(self):
        """Verify savepoint is issued exactly once — all renames in one transaction."""
        mock_frappe = self._make_mock_frappe()
        with patch("erpmin_integrations.migrate_item_structure.rename_old_templates.frappe",
                   mock_frappe):
            run()
        mock_frappe.db.savepoint.assert_called_once_with("rename_old_templates")

    def test_rollback_called_on_rename_failure(self):
        """If a rename raises, rollback is called and the exception propagates."""
        mock_frappe = self._make_mock_frappe()
        mock_frappe.rename_doc.side_effect = Exception("rename failed")
        with patch("erpmin_integrations.migrate_item_structure.rename_old_templates.frappe",
                   mock_frappe):
            with pytest.raises(Exception, match="rename failed"):
                run()
        mock_frappe.db.rollback.assert_called_once_with(save_point="rename_old_templates")
