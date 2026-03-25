from unittest.mock import MagicMock, patch
from frappe.tests.utils import FrappeTestCase
from erpmin_integrations.opencart.api import OpenCartClient


def _make_client():
    return OpenCartClient(api_url="http://opencart/", api_key="test-key")


class TestOpenCartClientOptions(FrappeTestCase):

    def test_get_or_create_option_creates_when_not_found(self):
        client = _make_client()
        with patch.object(client, '_get', return_value={'options': []}) as mock_get, \
             patch.object(client, '_post', return_value={'option_id': 42}) as mock_post:
            result = client.get_or_create_option("Color")
            mock_post.assert_called_once_with("/api/v1/options", {"name": "Color", "type": "select"})
            self.assertEqual(result, 42)

    def test_get_or_create_option_returns_existing(self):
        client = _make_client()
        with patch.object(client, '_get', return_value={'options': [{'option_id': 7, 'name': 'Color'}]}) as mock_get, \
             patch.object(client, '_post') as mock_post:
            result = client.get_or_create_option("Color")
            mock_post.assert_not_called()
            self.assertEqual(result, 7)

    def test_get_or_create_option_value_creates(self):
        client = _make_client()
        with patch.object(client, '_post', return_value={'option_value_id': 55}) as mock_post:
            result = client.get_or_create_option_value(option_id=7, value="Red")
            mock_post.assert_called_once_with("/api/v1/options/7/values", {"name": "Red"})
            self.assertEqual(result, 55)

    def test_set_product_option_calls_put(self):
        client = _make_client()
        with patch.object(client, '_put', return_value={'success': True}) as mock_put:
            client.set_product_option(
                product_id=5,
                option_id=1,
                option_value_id=2,
                price=0.0,
            )
            mock_put.assert_called_once_with(
                "/api/v1/products/5/options",
                {
                    "option_id": 1,
                    "option_value_id": 2,
                    "price": 0.0,
                    "price_prefix": "+",
                },
            )


class TestFilterMethods(FrappeTestCase):

    def _make_client(self):
        from erpmin_integrations.opencart.api import OpenCartClient
        client = OpenCartClient.__new__(OpenCartClient)
        client._filter_group_cache = {}
        client._filter_cache = {}
        client._synced_filter_products = set()
        return client

    @patch.object(OpenCartClient, '_get')
    @patch.object(OpenCartClient, '_post')
    def test_get_or_create_filter_group_creates_when_missing(self, mock_post, mock_get):
        mock_get.return_value = {'filter_groups': []}
        mock_post.return_value = {'filter_group_id': 7}
        client = self._make_client()

        result = client.get_or_create_filter_group('Material')

        mock_post.assert_called_once_with('/api/v1/filter-groups', {'name': 'Material'})
        self.assertEqual(result, 7)
        self.assertEqual(client._filter_group_cache['Material'], 7)

    @patch.object(OpenCartClient, '_get')
    def test_get_or_create_filter_group_returns_existing(self, mock_get):
        mock_get.return_value = {'filter_groups': [{'filter_group_id': 3, 'name': 'Material'}]}
        client = self._make_client()

        result = client.get_or_create_filter_group('Material')

        self.assertEqual(result, 3)
        mock_get.assert_called_once()

    @patch.object(OpenCartClient, '_get')
    def test_get_or_create_filter_group_uses_cache(self, mock_get):
        client = self._make_client()
        client._filter_group_cache['Material'] = 5

        result = client.get_or_create_filter_group('Material')

        mock_get.assert_not_called()
        self.assertEqual(result, 5)

    @patch.object(OpenCartClient, '_get')
    @patch.object(OpenCartClient, '_post')
    def test_get_or_create_filter_creates_when_missing(self, mock_post, mock_get):
        mock_get.return_value = {'filters': []}
        mock_post.return_value = {'filter_id': 12}
        client = self._make_client()

        result = client.get_or_create_filter(7, 'Cotton')

        mock_post.assert_called_once_with('/api/v1/filter-groups/7/filters', {'name': 'Cotton'})
        self.assertEqual(result, 12)
        self.assertEqual(client._filter_cache[(7, 'Cotton')], 12)

    @patch.object(OpenCartClient, '_get')
    def test_get_or_create_filter_returns_existing(self, mock_get):
        mock_get.return_value = {'filters': [{'filter_id': 9, 'name': 'Cotton'}]}
        client = self._make_client()

        result = client.get_or_create_filter(7, 'Cotton')

        self.assertEqual(result, 9)

    @patch.object(OpenCartClient, '_get')
    def test_get_or_create_filter_uses_cache(self, mock_get):
        client = self._make_client()
        client._filter_cache[(7, 'Cotton')] = 4

        result = client.get_or_create_filter(7, 'Cotton')

        mock_get.assert_not_called()
        self.assertEqual(result, 4)

    @patch.object(OpenCartClient, '_put')
    def test_set_product_filter_calls_put(self, mock_put):
        client = self._make_client()
        client.set_product_filter(59, 12)
        mock_put.assert_called_once_with('/api/v1/products/59/filters', {'filter_id': 12})
