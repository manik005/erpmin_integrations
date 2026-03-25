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
        self._option_cache: dict[str, int] = {}  # option name → option_id
        self._activated_products: set[int] = set()  # product_ids activated this session
        self._filter_group_cache: dict[str, int] = {}       # group name → filter_group_id
        self._filter_cache: dict[tuple[int, str], int] = {}  # (group_id, value) → filter_id
        self._synced_filter_products: set[int] = set()       # parent product IDs synced this session

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

    def get_or_create_option(self, name: str) -> int:
        """Return option_id for a global option (e.g. Color, Size), creating if needed.
        Results are cached for the lifetime of this client instance."""
        if name in self._option_cache:
            return self._option_cache[name]
        result = self._get("/api/v1/options", {"name": name})
        options = result.get("options", [])
        if options:
            option_id = int(options[0]["option_id"])
        else:
            created = self._post("/api/v1/options", {"name": name, "type": "select"})
            option_id = int(created["option_id"])
        self._option_cache[name] = option_id
        return option_id

    def get_or_create_option_value(self, option_id: int, value: str) -> int:
        """Return option_value_id for the given value under an option, creating if needed.
        Idempotency is handled server-side by the PHP API."""
        created = self._post(f"/api/v1/options/{option_id}/values", {"name": value})
        return int(created["option_value_id"])

    def set_product_option(
        self,
        product_id: int,
        option_id: int,
        option_value_id: int,
        price: float = 0.0,
    ) -> None:
        """Upsert a single option value on a product."""
        self._put(
            f"/api/v1/products/{product_id}/options",
            {
                "option_id": option_id,
                "option_value_id": option_value_id,
                "price": price,
                "price_prefix": "+",
            },
        )

    def get_or_create_filter_group(self, name: str) -> int:
        """Return filter_group_id for the given attribute name, creating if needed."""
        if name in self._filter_group_cache:
            return self._filter_group_cache[name]
        result = self._get("/api/v1/filter-groups", {"name": name})
        groups = result.get("filter_groups", [])
        if groups:
            fg_id = int(groups[0]["filter_group_id"])
        else:
            created = self._post("/api/v1/filter-groups", {"name": name})
            fg_id = int(created["filter_group_id"])
        self._filter_group_cache[name] = fg_id
        return fg_id

    def get_or_create_filter(self, filter_group_id: int, value: str) -> int:
        """Return filter_id for the given value under a filter group, creating if needed."""
        key = (filter_group_id, value)
        if key in self._filter_cache:
            return self._filter_cache[key]
        result = self._get(f"/api/v1/filter-groups/{filter_group_id}/filters", {"name": value})
        filters = result.get("filters", [])
        if filters:
            filter_id = int(filters[0]["filter_id"])
        else:
            created = self._post(f"/api/v1/filter-groups/{filter_group_id}/filters", {"name": value})
            filter_id = int(created["filter_id"])
        self._filter_cache[key] = filter_id
        return filter_id

    def set_product_filter(self, product_id: int, filter_id: int) -> None:
        """Attach a filter value to a product (idempotent). Also links filter group to category."""
        self._put(f"/api/v1/products/{product_id}/filters", {"filter_id": filter_id})

    def get_categories(self, parent_id: int | None = None, name: str | None = None) -> list[dict]:
        params = {}
        if parent_id is not None:
            params["parent_id"] = parent_id
        if name is not None:
            params["name"] = name
        result = self._get("/api/v1/categories", params)
        return result.get("categories", [])

    def get_or_create_category(self, name: str, parent_id: int = 0, top: bool = False) -> int:
        """Return category_id for the given name+parent, creating if needed."""
        cats = self.get_categories(parent_id=parent_id, name=name)
        if cats:
            return int(cats[0]["category_id"])
        data = {"name": name, "parent_id": parent_id, "top": 1 if top else 0}
        created = self._post("/api/v1/categories", data)
        return int(created["category_id"])

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
    from erpmin_integrations.erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings

    settings = get_settings()
    if not settings.enabled:
        return None
    return OpenCartClient(
        api_url=settings.api_url,
        api_key=settings.get_password("api_key"),
    )
