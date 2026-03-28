from unittest.mock import MagicMock
from frappe.tests.utils import FrappeTestCase


def _make_image_row(file_path, media_type="Image", sort_order=0):
    row = MagicMock()
    row.file = file_path
    row.media_type = media_type
    row.sort_order = sort_order
    return row


def _make_item(image=None, product_images=None):
    item = MagicMock()
    item.image = image or ""
    item.custom_product_images = product_images or []
    return item


class TestGetPublicUrlsForItem(FrappeTestCase):

    def test_returns_empty_when_no_base_url(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(image="/files/photo.jpg")
        result = get_public_urls_for_item(item, "")
        self.assertEqual(result, [])

    def test_falls_back_to_item_image(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(image="/files/photo.jpg")
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(result, ["https://erp.example.com/files/photo.jpg"])

    def test_child_table_takes_priority_over_item_image(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(
            image="/files/old.jpg",
            product_images=[_make_image_row("/files/new.jpg", sort_order=0)],
        )
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(result, ["https://erp.example.com/files/new.jpg"])

    def test_multiple_images_returned_in_sort_order(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(product_images=[
            _make_image_row("/files/c.jpg", sort_order=5),
            _make_image_row("/files/a.jpg", sort_order=0),
            _make_image_row("/files/b.jpg", sort_order=2),
        ])
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(result, [
            "https://erp.example.com/files/a.jpg",
            "https://erp.example.com/files/b.jpg",
            "https://erp.example.com/files/c.jpg",
        ])

    def test_trailing_slash_stripped_from_base_url(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(image="/files/photo.jpg")
        result = get_public_urls_for_item(item, "https://erp.example.com/")
        self.assertEqual(result, ["https://erp.example.com/files/photo.jpg"])

    def test_private_files_skipped(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(
            product_images=[_make_image_row("/private/files/secret.jpg", sort_order=0)]
        )
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(result, [])

    def test_videos_included_in_urls(self):
        """Videos are included — Amazon supports video via other_product_image_locator_N."""
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(product_images=[
            _make_image_row("/files/photo.jpg", media_type="Image", sort_order=0),
            _make_image_row("/files/demo.mp4", media_type="Video", sort_order=1),
        ])
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(len(result), 2)
        self.assertIn("demo.mp4", result[1])

    def test_returns_empty_when_item_image_is_private(self):
        from erpmin_integrations.utils.cdn import get_public_urls_for_item
        item = _make_item(image="/private/files/hidden.jpg")
        result = get_public_urls_for_item(item, "https://erp.example.com")
        self.assertEqual(result, [])


class TestAmazonImageAttributes(FrappeTestCase):

    def _make_item(self, **kwargs):
        item = MagicMock()
        item.item_name = "Test Item"
        item.description = ""
        item.barcodes = []
        item.custom_amazon_brand = ""
        item.custom_amazon_description = ""
        item.custom_amazon_bullet_points = ""
        item.attributes = []
        for k, v in kwargs.items():
            setattr(item, k, v)
        return item

    def test_main_image_locator_set(self):
        from erpmin_integrations.amazon.attributes import build_attributes
        item = self._make_item()
        attrs = build_attributes(item, "PRODUCT", image_urls=["https://erp.example.com/files/a.jpg"])
        self.assertIn("main_product_image_locator", attrs)
        self.assertEqual(
            attrs["main_product_image_locator"][0]["media_location"],
            "https://erp.example.com/files/a.jpg",
        )

    def test_other_image_locators_set(self):
        from erpmin_integrations.amazon.attributes import build_attributes
        item = self._make_item()
        urls = [f"https://erp.example.com/files/img{i}.jpg" for i in range(4)]
        attrs = build_attributes(item, "PRODUCT", image_urls=urls)
        self.assertIn("main_product_image_locator", attrs)
        self.assertIn("other_product_image_locator_1", attrs)
        self.assertIn("other_product_image_locator_2", attrs)
        self.assertIn("other_product_image_locator_3", attrs)
        self.assertNotIn("other_product_image_locator_4", attrs)
        self.assertEqual(
            attrs["other_product_image_locator_1"][0]["media_location"],
            "https://erp.example.com/files/img1.jpg",
        )

    def test_max_8_other_locators(self):
        from erpmin_integrations.amazon.attributes import build_attributes
        item = self._make_item()
        # 10 images: 1 main + 8 other (9th should be ignored)
        urls = [f"https://erp.example.com/files/img{i}.jpg" for i in range(10)]
        attrs = build_attributes(item, "PRODUCT", image_urls=urls)
        self.assertIn("other_product_image_locator_8", attrs)
        self.assertNotIn("other_product_image_locator_9", attrs)

    def test_no_image_locators_when_no_urls(self):
        from erpmin_integrations.amazon.attributes import build_attributes
        item = self._make_item()
        attrs = build_attributes(item, "PRODUCT", image_urls=[])
        self.assertNotIn("main_product_image_locator", attrs)

    def test_no_image_locators_when_image_urls_is_none(self):
        from erpmin_integrations.amazon.attributes import build_attributes
        item = self._make_item()
        attrs = build_attributes(item, "PRODUCT", image_urls=None)
        self.assertNotIn("main_product_image_locator", attrs)

    def test_parent_attributes_include_images(self):
        from erpmin_integrations.amazon.attributes import build_parent_attributes
        item = self._make_item()
        attrs = build_parent_attributes(
            item, "CLOTHING",
            image_urls=["https://erp.example.com/files/a.jpg"],
        )
        self.assertIn("main_product_image_locator", attrs)

    def test_child_attributes_include_images(self):
        from erpmin_integrations.amazon.attributes import build_child_attributes
        item = self._make_item()
        item.attributes = []
        attrs = build_child_attributes(
            item, "PRODUCT", parent_sku="PARENT-001",
            image_urls=["https://erp.example.com/files/a.jpg"],
        )
        self.assertIn("main_product_image_locator", attrs)
        self.assertEqual(attrs["parentage"][0]["value"], "child")
