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
    item.attributes = []
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

    def test_variant_item_reads_color_from_attributes(self):
        """Variant items have color in item.attributes, not custom_amazon_color."""
        from unittest.mock import MagicMock as MM
        item = _make_item(color="")  # custom field empty
        attr = MM()
        attr.attribute = "Color"
        attr.attribute_value = "Blue"
        item.attributes = [attr]
        attrs = build_attributes(item, "CLOTHING")
        self.assertEqual(attrs["color"][0]["value"], "Blue")

    def test_variant_item_reads_size_from_attributes(self):
        item = _make_item(size="")
        from unittest.mock import MagicMock as MM
        attr = MM()
        attr.attribute = "Size"
        attr.attribute_value = "XL"
        item.attributes = [attr]
        attrs = build_attributes(item, "CLOTHING")
        self.assertEqual(attrs["size"][0]["value"], "XL")

    def test_custom_field_color_wins_when_no_attributes(self):
        """Flat item: custom_amazon_color used when item.attributes is empty."""
        item = _make_item(color="Green")
        item.attributes = []
        attrs = build_attributes(item, "CLOTHING")
        self.assertEqual(attrs["color"][0]["value"], "Green")

    def test_build_parent_attributes_has_item_name(self):
        from erpmin_integrations.amazon.attributes import build_parent_attributes
        template = _make_item(item_name="Cotton T-Shirt")
        attrs = build_parent_attributes(template, "CLOTHING")
        self.assertEqual(attrs["item_name"][0]["value"], "Cotton T-Shirt")

    def test_build_parent_attributes_has_parentage(self):
        from erpmin_integrations.amazon.attributes import build_parent_attributes
        template = _make_item()
        attrs = build_parent_attributes(template, "CLOTHING")
        self.assertIn("parentage", attrs)
        self.assertEqual(attrs["parentage"][0]["value"], "parent")

    def test_build_parent_attributes_clothing_has_variation_theme_color_size(self):
        from erpmin_integrations.amazon.attributes import build_parent_attributes
        template = _make_item()
        attrs = build_parent_attributes(template, "CLOTHING")
        self.assertIn("variation_theme", attrs)
        self.assertEqual(attrs["variation_theme"][0]["name"], "COLOR_SIZE")

    def test_build_parent_attributes_unknown_type_omits_variation_theme(self):
        from erpmin_integrations.amazon.attributes import build_parent_attributes
        template = _make_item()
        attrs = build_parent_attributes(template, "PRODUCT")
        self.assertNotIn("variation_theme", attrs)

    def test_build_child_attributes_has_parentage_and_parent_sku(self):
        from erpmin_integrations.amazon.attributes import build_child_attributes
        from unittest.mock import MagicMock as MM
        item = _make_item()
        attr = MM()
        attr.attribute = "Color"
        attr.attribute_value = "Red"
        item.attributes = [attr]
        attrs = build_child_attributes(item, "CLOTHING", parent_sku="TSHIRT")
        self.assertEqual(attrs["parentage"][0]["value"], "child")
        rel = attrs["child_parent_sku_relationship"]
        self.assertEqual(rel[0]["parent_sku"], "TSHIRT")
        self.assertEqual(rel[0]["child_relationship_type"], "variation")

    def test_get_attribute_value_case_insensitive(self):
        """Attribute names like 'colour' should match 'Color'."""
        from erpmin_integrations.amazon.attributes import _get_attribute_value
        from unittest.mock import MagicMock as MM
        item = _make_item(color="")
        attr = MM()
        attr.attribute = "colour"
        attr.attribute_value = "Navy"
        item.attributes = [attr]
        result = _get_attribute_value(item, "Color")
        self.assertEqual(result, "Navy")
