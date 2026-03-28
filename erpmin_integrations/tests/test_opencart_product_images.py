from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase


def _make_image_row(file_path, media_type="Image", sort_order=0):
    row = MagicMock()
    row.file = file_path
    row.media_type = media_type
    row.sort_order = sort_order
    return row


def _make_item(name="ITEM-001", image=None, product_images=None):
    item = MagicMock()
    item.name = name
    item.image = image or ""
    item.custom_product_images = product_images or []
    return item


class TestGetOcImages(FrappeTestCase):

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    @patch("os.path.join", side_effect=lambda *a: "/".join(a))
    def test_returns_empty_when_no_images(self, mock_join, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item()
        client = MagicMock()
        client.upload_image.return_value = None
        result = _get_oc_images(item, client)
        self.assertEqual(result, [])

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_falls_back_to_item_image(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(image="/files/photo.jpg")
        client = MagicMock()
        client.upload_image.return_value = "catalog/erpmin/ITEM-001.jpg"
        result = _get_oc_images(item, client)
        self.assertEqual(result, ["catalog/erpmin/ITEM-001.jpg"])
        client.upload_image.assert_called_once_with("ITEM-001", "/site/public/files/photo.jpg")

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_child_table_takes_priority_over_item_image(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(
            image="/files/old.jpg",
            product_images=[_make_image_row("/files/new.jpg", sort_order=0)],
        )
        client = MagicMock()
        client.upload_image.return_value = "catalog/erpmin/ITEM-001.jpg"
        result = _get_oc_images(item, client)
        self.assertEqual(len(result), 1)
        # Should upload the child table image, not item.image
        client.upload_image.assert_called_once_with("ITEM-001", "/site/public/files/new.jpg")

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_multiple_images_returned_in_sort_order(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(product_images=[
            _make_image_row("/files/b.jpg", sort_order=2),
            _make_image_row("/files/a.jpg", sort_order=0),
            _make_image_row("/files/c.jpg", sort_order=5),
        ])
        client = MagicMock()
        client.upload_image.side_effect = lambda name, path: f"catalog/erpmin/{name}.jpg"
        result = _get_oc_images(item, client)
        # Order: sort_order 0 → 2 → 5
        self.assertEqual(len(result), 3)
        self.assertIn("ITEM-001", result[0])
        self.assertIn("ITEM-001_1", result[1])
        self.assertIn("ITEM-001_2", result[2])

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_video_rows_skipped(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(product_images=[
            _make_image_row("/files/photo.jpg", media_type="Image", sort_order=0),
            _make_image_row("/files/demo.mp4", media_type="Video", sort_order=1),
        ])
        client = MagicMock()
        client.upload_image.return_value = "catalog/erpmin/ITEM-001.jpg"
        result = _get_oc_images(item, client)
        self.assertEqual(len(result), 1)
        client.upload_image.assert_called_once()

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_private_files_skipped(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(product_images=[
            _make_image_row("/private/files/secret.jpg", sort_order=0),
        ])
        client = MagicMock()
        result = _get_oc_images(item, client)
        self.assertEqual(result, [])
        client.upload_image.assert_not_called()

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_cached_image_not_reuploaded(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = "catalog/erpmin/cached.jpg"
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(image="/files/photo.jpg")
        client = MagicMock()
        result = _get_oc_images(item, client)
        self.assertEqual(result, ["catalog/erpmin/cached.jpg"])
        client.upload_image.assert_not_called()

    @patch("erpmin_integrations.opencart.product.frappe.cache")
    @patch("erpmin_integrations.opencart.product.frappe.get_site_path", return_value="/site")
    def test_failed_upload_skipped_gracefully(self, mock_site, mock_cache):
        mock_cache.return_value.get_value.return_value = None
        from erpmin_integrations.opencart.product import _get_oc_images
        item = _make_item(product_images=[
            _make_image_row("/files/a.jpg", sort_order=0),
            _make_image_row("/files/b.jpg", sort_order=1),
        ])
        client = MagicMock()
        client.upload_image.side_effect = [Exception("network error"), "catalog/erpmin/ITEM-001_1.jpg"]
        result = _get_oc_images(item, client)
        # First failed, second succeeded
        self.assertEqual(result, ["catalog/erpmin/ITEM-001_1.jpg"])
