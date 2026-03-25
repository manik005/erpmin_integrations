from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase


def _make_template(item_code="TSHIRT", item_name="Cotton T-Shirt", group="Apparel"):
    t = MagicMock()
    t.name = item_code
    t.item_name = item_name
    t.item_group = group
    t.description = "A T-Shirt"
    t.disabled = 0
    t.has_variants = 1
    t.variant_of = None
    t.custom_sync_to_opencart = 1
    t.custom_opencart_id = None
    return t


def _make_variant(item_code="TSHIRT-RED-L", template_code="TSHIRT", color="Red", size="L"):
    v = MagicMock()
    v.name = item_code
    v.item_name = "Cotton T-Shirt"
    v.item_group = "Apparel"
    v.description = ""
    v.disabled = 0
    v.has_variants = 0
    v.variant_of = template_code
    v.custom_sync_to_opencart = 1
    v.custom_opencart_id = None

    attr_color = MagicMock()
    attr_color.attribute = "Color"
    attr_color.attribute_value = color

    attr_size = MagicMock()
    attr_size.attribute = "Size"
    attr_size.attribute_value = size

    v.attributes = [attr_color, attr_size]
    return v


class TestOpenCartVariantSync(FrappeTestCase):

    @patch("erpmin_integrations.opencart.product.get_client")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=499.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_variant_creates_parent_product_if_not_exists(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_client
    ):
        template = _make_template()
        variant = _make_variant()

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "TSHIRT-RED-L" else template
        )
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client.get_product_by_sku.return_value = None
        client.create_product.return_value = {"product_id": 100}
        client.get_or_create_option.side_effect = lambda name: {"Color": 1, "Size": 2}[name]
        client.get_or_create_option_value.side_effect = lambda oid, val: {"Red": 10, "L": 20}[val]
        mock_client.return_value = client

        from erpmin_integrations.opencart.product import sync_item
        sync_item("TSHIRT-RED-L")

        client.create_product.assert_called_once()
        created_data = client.create_product.call_args[0][0]
        self.assertEqual(created_data["sku"], "TSHIRT")

    @patch("erpmin_integrations.opencart.product.get_client")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=499.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_variant_adds_option_values_to_parent(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_client
    ):
        template = _make_template()
        variant = _make_variant()

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "TSHIRT-RED-L" else template
        )
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client.get_product_by_sku.return_value = {"product_id": 100}
        client.get_or_create_option.side_effect = lambda name: {"Color": 1, "Size": 2}[name]
        client.get_or_create_option_value.side_effect = lambda oid, val: {"Red": 10, "L": 20}[val]
        mock_client.return_value = client

        from erpmin_integrations.opencart.product import sync_item
        sync_item("TSHIRT-RED-L")

        self.assertEqual(client.set_product_option.call_count, 2)
        calls = client.set_product_option.call_args_list
        option_ids_used = {c[1]["option_id"] for c in calls}
        self.assertIn(1, option_ids_used)
        self.assertIn(2, option_ids_used)

        # Parent already existed — no duplicate creation
        client.create_product.assert_not_called()

    @patch("erpmin_integrations.opencart.product.get_client")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=0.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_template_item_is_skipped(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_client
    ):
        template = _make_template()
        mock_get_doc.return_value = template
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")
        client = MagicMock()
        mock_client.return_value = client

        from erpmin_integrations.opencart.product import sync_item
        sync_item("TSHIRT")

        client.create_product.assert_not_called()
        client.update_product.assert_not_called()


class TestAttributeRoleRouting(FrappeTestCase):

    @patch("erpmin_integrations.opencart.product._get_attribute_role")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=499.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_filter_attributes_skipped_as_options(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_role
    ):
        """Attributes with role=Filter must NOT be passed to set_product_option."""
        from erpmin_integrations.opencart.product import _sync_variant_item

        template = _make_template()
        template.custom_opencart_id = 100
        template.custom_opencart_variant_mode = "Group as options"

        variant = _make_variant()
        # Add a Material=Filter attribute
        attr_material = MagicMock()
        attr_material.attribute = "Material"
        attr_material.attribute_value = "Cotton"
        variant.attributes = list(variant.attributes) + [attr_material]

        # Color=Option, Size=Option, Material=Filter
        mock_role.side_effect = lambda name: {
            "Color": "Option", "Size": "Option", "Material": "Filter"
        }.get(name, "Option")
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client._activated_products = set()
        client._synced_filter_products = set()

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "TSHIRT-RED-L" else template
        )

        _sync_variant_item(variant, client)

        # set_product_option called only for Color and Size (2 times), not Material
        self.assertEqual(client.set_product_option.call_count, 2)
        # filter sync called for Material
        client.get_or_create_filter_group.assert_called_once_with("Material")

    @patch("erpmin_integrations.opencart.product._get_attribute_role")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=499.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_none_attributes_fully_skipped(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_role
    ):
        """Attributes with role=None must not appear as options OR filters."""
        from erpmin_integrations.opencart.product import _sync_variant_item

        template = _make_template()
        template.custom_opencart_id = 100
        template.custom_opencart_variant_mode = "Group as options"

        variant = _make_variant()
        mock_role.return_value = "None"  # all attrs → None
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client._activated_products = set()
        client._synced_filter_products = set()

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "TSHIRT-RED-L" else template
        )

        _sync_variant_item(variant, client)

        client.set_product_option.assert_not_called()
        client.get_or_create_filter_group.assert_not_called()

    @patch("frappe.cache")
    @patch("frappe.db.get_value")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=599.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=5)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_price_update_skips_non_option_attributes(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_get_value, mock_cache
    ):
        """_update_variant_price_if_changed must not call get_or_create_option for Filter attrs."""
        from erpmin_integrations.opencart.product import _sync_variant_item

        template = _make_template()
        template.custom_opencart_id = 100
        template.custom_opencart_variant_mode = "Group as options"

        variant = _make_variant()
        variant.custom_opencart_id = 100  # existing variant — triggers price-update path

        attr_material = MagicMock()
        attr_material.attribute = "Material"
        attr_material.attribute_value = "Cotton"
        variant.attributes = [
            next(a for a in _make_variant().attributes if a.attribute == "Color"),
            attr_material,
        ]

        def role_lookup(doctype, name, fieldname):
            return {"Color": "Option", "Material": "Filter"}.get(name, "Option")
        mock_get_value.side_effect = role_lookup

        # cache returns None so DB is hit
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_value.return_value = None
        mock_cache.return_value = mock_cache_instance

        client = MagicMock()
        client._activated_products = set()
        client._synced_filter_products = set()

        mock_get_doc.side_effect = lambda dt, name: (
            variant if name == "TSHIRT-RED-L" else template
        )
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        _sync_variant_item(variant, client)

        # get_or_create_option called only for Color (not Material)
        option_calls = [call[0][0] for call in client.get_or_create_option.call_args_list]
        self.assertIn("Color", option_calls)
        self.assertNotIn("Material", option_calls)


class TestIndividualProductsMode(FrappeTestCase):

    @patch("erpmin_integrations.opencart.product.get_client")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=250.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=60)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_individual_mode_syncs_variant_as_flat_product(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_client
    ):
        """In Individual products mode, variant syncs as its own standalone product."""
        template = _make_template(item_code="Perfume - Roll On", item_name="Roll On Perfume")
        template.custom_opencart_variant_mode = "Individual products"

        variant = MagicMock()
        variant.name = "PYAA0001"
        variant.item_name = "Roll On Perfume(8ml) - Paris"
        variant.item_group = "PY"
        variant.description = ""
        variant.disabled = 0
        variant.has_variants = 0
        variant.variant_of = "Perfume - Roll On"
        variant.custom_sync_to_opencart = 1
        variant.custom_opencart_id = None

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "PYAA0001" else template
        )
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client.get_product_by_sku.return_value = None
        client.create_product.return_value = {"product_id": 201}
        mock_client.return_value = client

        from erpmin_integrations.opencart.product import sync_item
        sync_item("PYAA0001")

        # Must create a product with the VARIANT's item_name, not the template's
        client.create_product.assert_called_once()
        created = client.create_product.call_args[0][0]
        self.assertEqual(created["sku"], "PYAA0001")
        self.assertEqual(created["name"]["1"], "Roll On Perfume(8ml) - Paris")

        # Must NOT create a parent product or set options
        client.set_product_option.assert_not_called()

        # Routing must have used the variant's SKU for the product lookup
        client.get_product_by_sku.assert_called_once_with("PYAA0001")

    @patch("erpmin_integrations.opencart.product.get_client")
    @patch("erpmin_integrations.opencart.product.get_settings")
    @patch("erpmin_integrations.opencart.product._get_item_price", return_value=250.0)
    @patch("erpmin_integrations.opencart.product.get_category_id", return_value=60)
    @patch("frappe.get_doc")
    @patch("frappe.db.set_value")
    def test_group_mode_still_uses_parent_product(
        self, mock_set_value, mock_get_doc, mock_cat, mock_price, mock_settings, mock_client
    ):
        """Default Group as options mode is unchanged."""
        template = _make_template()
        template.custom_opencart_variant_mode = "Group as options"
        template.custom_opencart_id = 100

        variant = _make_variant()

        mock_get_doc.side_effect = lambda doctype, name: (
            variant if name == "TSHIRT-RED-L" else template
        )
        mock_settings.return_value = MagicMock(default_price_list="Standard Selling")

        client = MagicMock()
        client._activated_products = set()
        client._synced_filter_products = set()
        mock_client.return_value = client

        with patch("frappe.db.get_value", return_value="Option"):
            from erpmin_integrations.opencart.product import sync_item
            sync_item("TSHIRT-RED-L")

        # Parent product must NOT be created again (already has custom_opencart_id=100)
        client.create_product.assert_not_called()
        # Options are set
        self.assertGreater(client.set_product_option.call_count, 0)
