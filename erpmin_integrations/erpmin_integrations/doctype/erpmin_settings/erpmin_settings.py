import frappe
from frappe.model.document import Document


class ERPminSettings(Document):
    pass


def get_settings():
    return frappe.get_single("ERPmin Settings")
