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


def build_attributes(item, product_type: str) -> dict:
    """Return SP-API attributes dict for the given item and product type."""
    if product_type not in _SUPPORTED_TYPES:
        frappe.logger().warning(
            f"[Amazon] Unknown product type '{product_type}' for item {getattr(item, 'name', '?')}. "
            "Falling back to PRODUCT."
        )
        product_type = "PRODUCT"

    attrs = _build_common(item)

    if product_type == "CLOTHING":
        attrs.update(_build_clothing(item))
    elif product_type in ("CONSUMER_ELECTRONICS",):
        pass  # common attrs are sufficient; extend as needed
    # HOME_FURNISHING, BEAUTY, SPORTS also use common attrs

    return attrs


def _build_common(item) -> dict:
    attrs = {
        "item_name": [{"value": item.item_name, "language_tag": _LANG}],
    }

    # brand
    brand = getattr(item, "custom_amazon_brand", "") or ""
    if brand.strip():
        attrs["brand"] = [{"value": brand.strip(), "language_tag": _LANG}]

    # description — prefer amazon-specific, fall back to ERPNext description
    description = getattr(item, "custom_amazon_description", "") or item.description or ""
    if description.strip():
        attrs["product_description"] = [{"value": description.strip(), "language_tag": _LANG}]

    # bullet points
    bullets_text = getattr(item, "custom_amazon_bullet_points", "") or ""
    bullets = _parse_bullet_points(bullets_text)
    if bullets:
        attrs["bullet_point"] = bullets

    # barcode / GTIN
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
            # No EAN/UPC barcode found — skip GTIN to avoid SP-API schema rejection
            frappe.logger().warning(
                f"[Amazon] Item has barcodes but none are EAN/UPC. GTIN not submitted to SP-API."
            )

    return attrs


def _build_clothing(item) -> dict:
    extra = {}
    color = getattr(item, "custom_amazon_color", "") or ""
    size = getattr(item, "custom_amazon_size", "") or ""
    if color.strip():
        extra["color"] = [{"value": color.strip(), "language_tag": _LANG}]
    if size.strip():
        extra["size"] = [{"value": size.strip(), "language_tag": _LANG}]
    return extra


def _parse_bullet_points(text: str) -> list:
    """Split newline-separated bullet points, max 5, skip empty lines."""
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [{"value": line, "language_tag": _LANG} for line in lines[:5]]
