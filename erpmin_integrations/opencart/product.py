import frappe
from erpmin_integrations.opencart.api import get_client
from erpmin_integrations.erpmin_integrations.doctype.opencart_settings.opencart_settings import get_settings
from erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping import (
    get_category_id,
)


def _get_attribute_role(attr_name: str) -> str:
    """Return the OpenCart role for an Item Attribute: Option, Filter, or None.
    Defaults to Option if unset. Uses frappe.cache to avoid repeated DB lookups."""
    cache_key = f"oc_attr_role:{attr_name}"
    cached = frappe.cache().get_value(cache_key)
    if cached:
        return cached
    role = frappe.db.get_value("Item Attribute", attr_name, "custom_opencart_role") or "Option"
    frappe.cache().set_value(cache_key, role, expires_in_sec=3600)
    return role


def _sync_template_filters(item, parent_product_id: int, client) -> None:
    """Sync Filter-role attributes from a variant to the parent OpenCart product.
    Called once per parent product per session (guarded by client._synced_filter_products)."""
    if parent_product_id in client._synced_filter_products:
        return
    for attr_row in item.attributes:
        if _get_attribute_role(attr_row.attribute) != "Filter":
            continue
        fg_id = client.get_or_create_filter_group(attr_row.attribute)
        filter_id = client.get_or_create_filter(fg_id, attr_row.attribute_value)
        client.set_product_filter(parent_product_id, filter_id)
    client._synced_filter_products.add(parent_product_id)


def on_item_save(doc, method=None):
    if frappe.flags.in_import or frappe.flags.in_migrate:
        return
    if not doc.custom_sync_to_opencart:
        return

    if doc.has_variants:
        # Propagate flag to all variants so they get picked up by sync
        frappe.db.set_value(
            "Item",
            {"variant_of": doc.name},
            "custom_sync_to_opencart",
            1,
        )
        return  # template itself is never synced as a product

    frappe.enqueue(
        "erpmin_integrations.opencart.product.sync_item",
        item_code=doc.name,
        queue="short",
        enqueue_after_commit=True,
    )


def sync_item(item_code, client=None):
    if client is None:
        client = get_client()
    if not client:
        return

    item = frappe.get_doc("Item", item_code)
    if not item.custom_sync_to_opencart:
        return

    # Template items (has_variants=1) are skipped — parent product created lazily when variants sync
    if item.has_variants:
        return

    if item.variant_of:
        template = frappe.get_doc("Item", item.variant_of)
        variant_mode = template.custom_opencart_variant_mode or "Group as options"
        if variant_mode == "Individual products":
            _sync_flat_item(item, client)
        else:
            _sync_variant_item(item, client, template=template)
    else:
        _sync_flat_item(item, client)


def _sync_flat_item(item, client):
    settings = get_settings()
    price = _get_item_price(item.name, settings.default_price_list)
    category_id = get_category_id(item.item_group)

    is_active = not item.disabled and price > 0
    product_data = {
        "sku": item.name,
        "model": item.name,
        "name": {"1": item.item_name},
        "description": {"1": item.description or ""},
        "price": price,
        "quantity": 0,
        "status": 1 if is_active else 0,
        "category_id": [category_id] if category_id else [],
    }

    existing = client.get_product_by_sku(item.name)
    if existing:
        product_id = existing.get("product_id")
        client.update_product(product_id, product_data)
        if item.custom_opencart_id != product_id:
            frappe.db.set_value("Item", item.name, "custom_opencart_id", product_id)
    else:
        result = client.create_product(product_data)
        product_id = result.get("product_id")
        if product_id:
            frappe.db.set_value("Item", item.name, "custom_opencart_id", product_id)

    frappe.logger().info(f"[OpenCart] Synced product: {item.name}")


def _sync_variant_item(item, client, template=None):
    """Sync a variant item. Creates parent product from template if needed, then
    upserts this variant's option values on the parent product."""
    settings = get_settings()
    if template is None:
        template = frappe.get_doc("Item", item.variant_of)
    category_id = get_category_id(template.item_group)

    # Ensure parent product exists in OpenCart (keyed by template item_code).
    # Use cached custom_opencart_id to avoid a GET on every variant sync.
    parent_sku = template.name
    if template.custom_opencart_id:
        parent_product_id = int(template.custom_opencart_id)
    else:
        existing_parent = client.get_product_by_sku(parent_sku)
        if existing_parent:
            parent_product_id = int(existing_parent["product_id"])
        else:
            parent_data = {
                "sku": parent_sku,
                "model": parent_sku,
                "name": {"1": template.item_name},
                "description": {"1": template.description or ""},
                "price": 0,
                "quantity": 0,
                "status": 0,
                "category_id": [category_id] if category_id else [],
            }
            result = client.create_product(parent_data)
            parent_product_id = result.get("product_id")
            if not parent_product_id:
                frappe.log_error(
                    f"[OpenCart] create_product returned no product_id for template {template.name}",
                    "[OpenCart] _sync_variant_item",
                )
                return
            parent_product_id = int(parent_product_id)
        frappe.db.set_value("Item", template.name, "custom_opencart_id", parent_product_id)

    variant_price = _get_item_price(item.name, settings.default_price_list)
    # A variant is "new" if it has never been fully synced (no opencart_id recorded).
    # custom_opencart_id is only written after options are successfully set, so any
    # variant left without it (e.g. from a partial previous sync) is re-synced fully.
    is_new_variant = not item.custom_opencart_id

    if is_new_variant:
        for attr_row in item.attributes:
            role = _get_attribute_role(attr_row.attribute)
            if role != "Option":
                continue  # Filter and None handled separately
            option_id = client.get_or_create_option(attr_row.attribute)
            option_value_id = client.get_or_create_option_value(option_id, attr_row.attribute_value)
            client.set_product_option(
                product_id=parent_product_id,
                option_id=option_id,
                option_value_id=option_value_id,
                price=variant_price,
            )
        # Mark as synced only after all options are set successfully
        frappe.db.set_value("Item", item.name, "custom_opencart_id", parent_product_id)
    else:
        # Existing variant: attributes never change in ERPNext, only update price if needed
        _update_variant_price_if_changed(client, item, parent_product_id, variant_price)

    # Sync Filter-role attributes once per parent product per session
    _sync_template_filters(item, parent_product_id, client)

    # Activate parent product if template is enabled (status may be 0 from initial creation).
    # Use session-level cache to avoid one PUT per variant on every sync run.
    if not template.disabled and parent_product_id not in client._activated_products:
        client.update_product(parent_product_id, {"status": 1})
        client._activated_products.add(parent_product_id)

    frappe.logger().info(f"[OpenCart] Synced variant: {item.name} (new={is_new_variant}) under parent {parent_product_id}")


def check_sync_status():
    """Print items that should sync to OpenCart but haven't been (no opencart_id).

    Useful for diagnosing partial sync failures after bulk imports.
    """
    # Flat items
    flat = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "disabled": 0, "has_variants": 0,
                 "variant_of": "", "custom_opencart_id": ""},
        fields=["name", "item_name", "item_group"],
        limit=0,
    )
    # Variants of synced templates
    templates = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "has_variants": 1, "disabled": 0},
        pluck="name",
        limit=0,
    )
    variants_missing = []
    if templates:
        variants_missing = frappe.get_all(
            "Item",
            filters={"variant_of": ["in", templates], "disabled": 0,
                     "custom_opencart_id": ""},
            fields=["name", "item_name", "variant_of"],
            limit=0,
        )

    print(f"\n=== Flat items not synced: {len(flat)} ===")
    for i in flat:
        print(f"  {i['name']:20s}  {i['item_name']}")

    print(f"\n=== Variants not synced: {len(variants_missing)} ===")
    for i in variants_missing:
        print(f"  {i['name']:20s}  {i['item_name']:40s}  template={i['variant_of']}")

    print(f"\n=== Recent Error Log entries (OpenCart) ===")
    errors = frappe.get_all(
        "Error Log",
        filters={"method": ["like", "%OpenCart%"]},
        fields=["creation", "method", "error"],
        order_by="creation desc",
        limit=10,
    )
    for e in errors:
        print(f"  {e['creation']}  {e['method']}")
        print(f"    {e['error']}")


def propagate_sync_flags():
    """Push custom_sync_to_opencart=1 from templates to all their variants.

    Normally on_item_save() does this propagation, but it is skipped during
    Data Import (frappe.flags.in_import). Run this once after bulk imports.
    """
    templates = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "has_variants": 1, "disabled": 0},
        pluck="name",
        limit=0,
    )
    if not templates:
        print("No sync-enabled templates found.")
        return

    updated = frappe.db.count(
        "Item", filters={"variant_of": ["in", templates], "custom_sync_to_opencart": 0}
    )
    frappe.db.set_value(
        "Item",
        {"variant_of": ["in", templates]},
        "custom_sync_to_opencart",
        1,
        update_modified=False,
    )
    frappe.db.commit()
    print(f"✓ Propagated sync flag to {updated} variants across {len(templates)} templates")


def full_product_sync():
    client = get_client()
    if not client:
        return

    # Flat items and variants with sync directly enabled
    items = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "disabled": 0, "has_variants": 0},
        pluck="name",
        limit=0,
    )

    # Also include ALL variants of templates that have sync enabled
    template_codes = frappe.get_all(
        "Item",
        filters={"custom_sync_to_opencart": 1, "has_variants": 1, "disabled": 0},
        pluck="name",
        limit=0,
    )
    if template_codes:
        variant_codes = frappe.get_all(
            "Item",
            filters={"variant_of": ["in", template_codes], "disabled": 0},
            pluck="name",
            limit=0,
        )
        items = list(set(items) | set(variant_codes))

    for item_code in items:
        try:
            sync_item(item_code, client=client)  # share client so _option_cache persists
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"[OpenCart] full_product_sync failed: {item_code}"
            )


def _update_variant_price_if_changed(client, item, parent_product_id, new_price):
    """Update option prices on OpenCart only when the ERPNext price has changed."""
    cached_price = frappe.cache().get_value(f"oc_variant_price:{item.name}")
    if cached_price is not None and float(cached_price) == new_price:
        return
    for attr_row in item.attributes:
        if _get_attribute_role(attr_row.attribute) != "Option":
            continue
        option_id = client.get_or_create_option(attr_row.attribute)
        option_value_id = client.get_or_create_option_value(option_id, attr_row.attribute_value)
        client.set_product_option(
            product_id=parent_product_id,
            option_id=option_id,
            option_value_id=option_value_id,
            price=new_price,
        )
    frappe.cache().set_value(f"oc_variant_price:{item.name}", new_price, expires_in_sec=3600)


def _get_item_price(item_code, price_list):
    price = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list},
        "price_list_rate",
    )
    return float(price or 0)
