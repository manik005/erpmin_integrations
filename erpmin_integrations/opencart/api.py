import frappe
import requests


class OpenCartAPIError(Exception):
    pass


class OpenCartClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _get(self, endpoint, params=None):
        response = self.session.get(
            f"{self.api_url}{endpoint}", params=params, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, data=None):
        response = self.session.post(
            f"{self.api_url}{endpoint}", json=data, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint, data=None):
        response = self.session.put(
            f"{self.api_url}{endpoint}", json=data, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_product_by_sku(self, sku):
        result = self._get("/api/v1/products", {"sku": sku})
        products = result.get("products", [])
        return products[0] if products else None

    def create_product(self, product_data):
        return self._post("/api/v1/products", product_data)

    def update_product(self, product_id, product_data):
        return self._put(f"/api/v1/products/{product_id}", product_data)

    def update_stock(self, product_id, quantity):
        return self._put(f"/api/v1/products/{product_id}", {"quantity": quantity})

    def get_new_orders(self, status_id=1):
        return self._get("/api/v1/orders", {"order_status_id": status_id})

    def get_order(self, order_id):
        return self._get(f"/api/v1/orders/{order_id}")

    def update_order_status(self, order_id, status_id, comment=""):
        return self._put(
            f"/api/v1/orders/{order_id}",
            {"order_status_id": status_id, "comment": comment, "notify": 0},
        )


def get_client():
    from erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings

    settings = get_settings()
    if not settings.enabled:
        return None
    return OpenCartClient(
        api_url=settings.api_url,
        api_key=settings.get_password("api_key"),
    )
