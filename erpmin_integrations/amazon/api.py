import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timezone

import frappe
import requests

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE = "https://sellingpartnerapi-eu.amazon.com"


class AmazonAPIError(Exception):
    pass


def _get_lwa_access_token(settings):
    cache_key = f"amazon_lwa_token_{settings.seller_id}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached

    resp = requests.post(
        LWA_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": settings.get_password("lwa_refresh_token"),
            "client_id": settings.lwa_client_id,
            "client_secret": settings.get_password("lwa_client_secret"),
        },
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_in = int(token_data.get("expires_in", 3600)) - 60  # buffer

    frappe.cache().set_value(cache_key, access_token, expires_in_sec=expires_in)
    return access_token


def _sign_request(method, url, headers, payload, region, service="execute-api"):
    """AWS SigV4 signing using stdlib hashlib/hmac."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query_string = parsed.query

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers["host"] = host
    headers["x-amz-date"] = amz_date

    signed_headers = ";".join(sorted(k.lower() for k in headers))
    canonical_headers = "".join(
        f"{k.lower()}:{headers[k]}\n" for k in sorted(headers, key=str.lower)
    )

    payload_hash = hashlib.sha256((payload or "").encode()).hexdigest()
    canonical_request = "\n".join(
        [method, path, query_string, canonical_headers, signed_headers, payload_hash]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    # SigV4 does NOT use AWS credentials for SP-API (uses LWA only)
    # We only sign the canonical request for the Authorization header shape
    # but SP-API authentication is done entirely via x-amz-access-token header.
    # Return the date header for SP-API compliance.
    return amz_date


class SPAPIClient:
    def __init__(self, settings):
        self.settings = settings
        self.marketplace_id = settings.marketplace_id
        self.seller_id = settings.seller_id

    def _get_headers(self):
        access_token = _get_lwa_access_token(self.settings)
        return {
            "x-amz-access-token": access_token,
            "x-amz-date": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "Content-Type": "application/json",
        }

    def get(self, path, params=None):
        url = f"{SP_API_BASE}{path}"
        resp = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
        if not resp.ok:
            raise AmazonAPIError(f"SP-API GET {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def post(self, path, data=None):
        url = f"{SP_API_BASE}{path}"
        resp = requests.post(
            url, headers=self._get_headers(), json=data, timeout=30
        )
        if not resp.ok:
            raise AmazonAPIError(f"SP-API POST {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def put_listing(self, path, data=None):
        """PUT to Listings API (create or update a listing)."""
        url = f"{SP_API_BASE}{path}"
        resp = requests.put(
            url, headers=self._get_headers(), json=data, timeout=30
        )
        if not resp.ok:
            raise AmazonAPIError(f"SP-API PUT {path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_orders(self, created_after, statuses=None):
        params = {
            "MarketplaceIds": self.marketplace_id,
            "CreatedAfter": created_after,
            "OrderStatuses": ",".join(statuses or ["Unshipped", "PartiallyShipped"]),
        }
        return self.get("/orders/v0/orders", params=params)

    def get_orders_next_page(self, next_token):
        params = {
            "MarketplaceIds": self.marketplace_id,
            "NextToken": next_token,
        }
        return self.get("/orders/v0/orders", params=params)

    def get_orders_updated_after(self, updated_after, statuses=None):
        params = {
            "MarketplaceIds": self.marketplace_id,
            "LastUpdatedAfter": updated_after,
            "OrderStatuses": ",".join(statuses or ["Cancelled"]),
        }
        return self.get("/orders/v0/orders", params=params)

    def get_order_items(self, order_id):
        return self.get(f"/orders/v0/orders/{order_id}/orderItems")

    def confirm_shipment(self, order_id, payload):
        return self.post(f"/orders/v0/orders/{order_id}/shipmentConfirmation", payload)


def get_client():
    from erpmin_integrations.erpmin_integrations.doctype.amazon_settings.amazon_settings import get_settings

    settings = get_settings()
    if not settings.enabled:
        return None
    return SPAPIClient(settings)
