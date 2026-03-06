import frappe
from frappe.model.document import Document


class ChannelCategoryMapping(Document):
    pass


def get_category_id(item_group):
    result = frappe.db.get_value(
        "Channel Category Mapping",
        {"item_group": item_group},
        "opencart_category_id",
    )
    return result or 0
