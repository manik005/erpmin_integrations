app_name = "erpmin_integrations"
app_title = "Erpmin Integrations"
app_publisher = "erpmin"
app_description = "Native Frappe integration layer for OpenCart and Amazon India"
app_email = "admin@erpmin.local"
app_license = "MIT"

after_install = "erpmin_integrations.install.after_install"

doc_events = {
    "Item": {
        "after_save": [
            "erpmin_integrations.opencart.product.on_item_save",
            "erpmin_integrations.amazon.product.on_item_save",
        ]
    },
    "Delivery Note": {
        "on_submit": "erpmin_integrations.amazon.fulfillment.on_delivery_note_submit",
    },
    "Channel Category Mapping": {
        "after_save": "erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping.on_mapping_save",
    },
}

scheduler_events = {
    "cron": {
        "*/30 * * * *": [
            "erpmin_integrations.opencart.inventory.sync_all_inventory",
            "erpmin_integrations.amazon.inventory.sync_all_inventory",
        ],
        "*/15 * * * *": [
            "erpmin_integrations.amazon.order.import_orders",
        ],
        "*/5 * * * *": [
            "erpmin_integrations.amazon.feeds.check_pending_feeds",
        ],
        "0 2 * * *": [
            "erpmin_integrations.opencart.product.full_product_sync",
            "erpmin_integrations.amazon.product.full_product_sync",
        ],
    }
}
