from unittest.mock import MagicMock
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.amazon.attributes import build_attributes, _parse_bullet_points


def _make_item(**kwargs):
    item = MagicMock()
    item.item_name = kwargs.get("item_name", "Test Item")
    item.description = kwargs.get("description", "A test item")
    item.barcodes = kwargs.get("barcodes", [])
    item.custom_amazon_brand = kwargs.get("brand", "TestBrand")
    item.custom_amazon_color = kwargs.get("color", "")
    item.custom_amazon_size = kwargs.get("size", "")
    item.custom_amazon_bullet_points = kwargs.get("bullets", "")
    item.custom_amazon_description = kwargs.get("amz_desc", "")
    return item


class TestBuildAttributes(FrappeTestCase):
    def test_generic_product_has_item_name(self):
        item = _make_item()
        attrs = build_attributes(item, "PRODUCT")
        self.assertIn("item_name", attrs)
        self.assertEqual(attrs["item_name"][0]["value"], "Test Item")

    def test_brand_included_when_set(self):
        item = _make_item(brand="Nike")
        attrs = build_attributes(item, "PRODUCT")
        self.assertIn("brand", attrs)
        self.assertEqual(attrs["brand"][0]["value"], "Nike")

    def test_brand_omitted_when_empty(self):
        item = _make_item(brand="")
        attrs = build_attributes(item, "PRODUCT")
        self.assertNotIn("brand", attrs)

    def test_clothing_includes_color_and_size(self):
        item = _make_item(color="Red", size="L")
        attrs = build_attributes(item, "CLOTHING")
        self.assertEqual(attrs["color"][0]["value"], "Red")
        self.assertEqual(attrs["size"][0]["value"], "L")

    def test_bullet_points_parsed(self):
        bullets = _parse_bullet_points("Point one\nPoint two\nPoint three")
        self.assertEqual(len(bullets), 3)
        self.assertEqual(bullets[0]["value"], "Point one")

    def test_bullet_points_max_5(self):
        text = "\n".join(f"Point {i}" for i in range(10))
        bullets = _parse_bullet_points(text)
        self.assertEqual(len(bullets), 5)

    def test_barcode_included_when_present(self):
        barcode = MagicMock()
        barcode.barcode = "1234567890123"
        barcode.barcode_type = "EAN"
        item = _make_item(barcodes=[barcode])
        attrs = build_attributes(item, "PRODUCT")
        self.assertIn("externally_assigned_product_identifier", attrs)

    def test_unknown_product_type_falls_back_to_product(self):
        item = _make_item()
        # Should not raise
        attrs = build_attributes(item, "UNKNOWN_TYPE_XYZ")
        self.assertIn("item_name", attrs)

    def test_clothing_omits_color_and_size_when_empty(self):
        item = _make_item(color="", size="")
        attrs = build_attributes(item, "CLOTHING")
        self.assertNotIn("color", attrs)
        self.assertNotIn("size", attrs)

    def test_non_ean_barcode_not_submitted(self):
        barcode = MagicMock()
        barcode.barcode = "NONEAN123"
        barcode.barcode_type = "Other"
        item = _make_item(barcodes=[barcode])
        attrs = build_attributes(item, "PRODUCT")
        self.assertNotIn("externally_assigned_product_identifier", attrs)

    def test_brand_has_language_tag(self):
        item = _make_item(brand="Nike")
        attrs = build_attributes(item, "PRODUCT")
        self.assertEqual(attrs["brand"][0]["language_tag"], "en_IN")

    def test_bullet_points_have_language_tag(self):
        bullets = _parse_bullet_points("Feature one\nFeature two")
        for bullet in bullets:
            self.assertIn("language_tag", bullet)
            self.assertEqual(bullet["language_tag"], "en_IN")
