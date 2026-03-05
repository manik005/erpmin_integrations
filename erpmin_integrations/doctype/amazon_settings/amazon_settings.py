import frappe
from frappe.model.document import Document


class AmazonSettings(Document):
    pass


def get_settings():
    return frappe.get_single("Amazon Settings")
