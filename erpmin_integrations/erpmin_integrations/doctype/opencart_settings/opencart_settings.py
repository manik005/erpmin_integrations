import frappe
from frappe.model.document import Document


class OpenCartSettings(Document):
    pass


def get_settings():
    return frappe.get_single("OpenCart Settings")
