"""
Amazon SP-API attribute builder.

Each product type has a builder that maps ERPNext Item fields to the
SP-API attributes dict. Unknown types fall back to the generic PRODUCT builder.

SP-API attribute shape:
    { "attribute_name": [{"value": ..., "language_tag": "en_IN"}] }
"""
import frappe

_LANG = "en_IN"
_SUPPORTED_TYPES = {"PRODUCT", "CLOTHING", "CONSUMER_ELECTRONICS", "HOME_FURNISHING", "BEAUTY", "SPORTS"}

# Map product_type → Amazon variation_theme value.
# CLOTHING (Color + Size) is implemented now.
# TODO: Add themes for other product types as inventory expands:
#   "SHOES": "SIZE_COLOR",
#   "CONSUMER_ELECTRONICS": "CONFIGURATION_NAME",
#   "HOME_FURNISHING": "COLOR",
#   "BEAUTY": "SCENT_NAME_SIZE_NAME",
#   "SPORTS": "SIZE_COLOR",
_VARIATION_THEME_MAP: dict[str, str] = {
    "CLOTHING": "COLOR_SIZE",
}

# Map ERPNext attribute name (lowercase) → (SP-API field name, custom field fallback).
# Case-insensitive: attribute names are lowercased before lookup.
# TODO: Extend this map for new attribute types as inventory expands:
#   "storage capacity": ("configuration_name", "custom_amazon_storage"),
#   "ram": ("configuration_name", "custom_amazon_ram"),
#   "scent": ("scent_name", "custom_amazon_scent"),
_ATTRIBUTE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "color":  ("color",  "custom_amazon_color"),
    "colour": ("color",  "custom_amazon_color"),
    "size":   ("size",   "custom_amazon_size"),
}


def build_attributes(item, product_type: str, image_urls: list[str] | None = None) -> dict:
    """Return SP-API attributes dict for the given item and product type."""
    if product_type not in _SUPPORTED_TYPES:
        frappe.logger().warning(
            f"[Amazon] Unknown product type '{product_type}' for item {getattr(item, 'name', '?')}. "
            "Falling back to PRODUCT."
        )
        product_type = "PRODUCT"

    attrs = _build_common(item, image_urls=image_urls)

    if product_type == "CLOTHING":
        attrs.update(_build_clothing(item))
    elif product_type in ("CONSUMER_ELECTRONICS",):
        pass
    # HOME_FURNISHING, BEAUTY, SPORTS also use common attrs

    return attrs


def build_parent_attributes(template_item, product_type: str, image_urls: list[str] | None = None) -> dict:
    """Build SP-API attributes for a parent (template) ASIN listing.

    Includes parentage=parent and variation_theme for known product types.
    For unknown types, variation_theme is omitted — Amazon may reject the listing.
    TODO: Add variation_theme entries to _VARIATION_THEME_MAP for new product types.
    """
    # Use _build_common directly (not build_attributes) so variant-specific attrs like
    # color/size are NOT added to the parent ASIN — those belong only on child ASINs.
    attrs = _build_common(template_item, image_urls=image_urls)
    attrs["parentage"] = [{"value": "parent", "language_tag": _LANG}]

    theme = _VARIATION_THEME_MAP.get(product_type)
    if theme:
        attrs["variation_theme"] = [{"name": theme}]
    else:
        frappe.logger().warning(
            f"[Amazon] No variation_theme defined for product type '{product_type}'. "
            "Parent ASIN may be rejected. Add it to _VARIATION_THEME_MAP in attributes.py."
        )

    return attrs


def build_child_attributes(item, product_type: str, parent_sku: str, image_urls: list[str] | None = None) -> dict:
    """Build SP-API attributes for a child variant ASIN listing."""
    attrs = build_attributes(item, product_type, image_urls=image_urls)
    attrs["parentage"] = [{"value": "child", "language_tag": _LANG}]
    attrs["child_parent_sku_relationship"] = [
        {
            "child_relationship_type": "variation",
            "parent_sku": parent_sku,
        }
    ]
    return attrs


def _get_attribute_value(item, attribute_name: str) -> str:
    """Read attribute value from item.attributes (native variants) or custom field (flat items).

    Matching is case-insensitive so 'Color', 'color', 'Colour' all resolve correctly.
    Aliases (e.g. 'colour' → same SP-API field as 'color') are resolved via _ATTRIBUTE_FIELD_MAP.
    """
    key = attribute_name.lower()
    # Determine the canonical SP-API field name for the requested attribute
    target_spapi_field, custom_field = _ATTRIBUTE_FIELD_MAP.get(key, (key, ""))

    # Check ERPNext variant attributes first — only if it's a real list (not a MagicMock in tests)
    attrs = getattr(item, "attributes", None)
    if isinstance(attrs, list):
        for row in attrs:
            row_attr = (getattr(row, "attribute", "") or "").lower()
            # Match if exact key OR if the row attribute maps to the same SP-API field
            row_spapi_field, _ = _ATTRIBUTE_FIELD_MAP.get(row_attr, (row_attr, ""))
            if row_attr == key or row_spapi_field == target_spapi_field:
                return (getattr(row, "attribute_value", "") or "").strip()

    # Fall back to custom field (flat items)
    if custom_field:
        return (getattr(item, custom_field, "") or "").strip()
    return ""


def _build_common(item, image_urls: list[str] | None = None) -> dict:
    attrs = {
        "item_name": [{"value": getattr(item, "custom_amazon_title", "") or item.item_name, "language_tag": _LANG}],
    }

    brand = getattr(item, "custom_amazon_brand", "") or ""
    if brand.strip():
        attrs["brand"] = [{"value": brand.strip(), "language_tag": _LANG}]

    description = getattr(item, "custom_amazon_description", "") or item.description or ""
    if description.strip():
        attrs["product_description"] = [{"value": description.strip(), "language_tag": _LANG}]

    bullets_text = getattr(item, "custom_amazon_bullet_points", "") or ""
    bullets = _parse_bullet_points(bullets_text)
    if bullets:
        attrs["bullet_point"] = bullets

    barcodes = getattr(item, "barcodes", []) or []
    for b in barcodes:
        btype = (b.barcode_type or "").upper()
        if btype in ("EAN", "EAN-13", "UPC"):
            attrs["externally_assigned_product_identifier"] = [
                {"type": "ean", "value": b.barcode}
            ]
            break
    else:
        if barcodes:
            frappe.logger().warning(
                f"[Amazon] Item has barcodes but none are EAN/UPC. GTIN not submitted to SP-API."
            )

    if image_urls:
        attrs["main_product_image_locator"] = [{"media_location": image_urls[0]}]
        for idx, url in enumerate(image_urls[1:9], start=1):
            attrs[f"other_product_image_locator_{idx}"] = [{"media_location": url}]

    return attrs


def _build_clothing(item) -> dict:
    extra = {}
    color = _get_attribute_value(item, "Color")
    size  = _get_attribute_value(item, "Size")
    if color:
        extra["color"] = [{"value": color, "language_tag": _LANG}]
    if size:
        extra["size"] = [{"value": size, "language_tag": _LANG}]
    return extra


def _parse_bullet_points(text: str) -> list:
    """Split newline-separated bullet points, max 5, skip empty lines."""
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [{"value": line, "language_tag": _LANG} for line in lines[:5]]
