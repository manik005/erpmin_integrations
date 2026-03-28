import frappe
from frappe import _


def validate(doc, method=None):
    _enforce_wholesale_min_qty(doc)


def _enforce_wholesale_min_qty(doc):
    """Raise ValidationError if a wholesale order item is below its min_order_qty.

    Applies when custom_channel == "Wholesale" OR the customer belongs to
    the "Wholesale" customer group. Items with min_order_qty = 0 are skipped.
    """
    is_wholesale = doc.custom_channel == "Wholesale" or (
        frappe.db.get_value("Customer", doc.customer, "customer_group") == "Wholesale"
    )
    if not is_wholesale:
        return

    errors = []
    for row in doc.items:
        min_qty = frappe.db.get_value("Item", row.item_code, "min_order_qty") or 0
        if min_qty > 0 and row.qty < min_qty:
            errors.append(
                f"Row {row.idx}: <b>{row.item_code}</b> requires minimum "
                f"<b>{min_qty}</b> units for wholesale orders (ordered: {row.qty})"
            )

    if errors:
        frappe.throw(
            _("Minimum order quantity not met:<br>") + "<br>".join(errors),
            title=_("Wholesale Minimum Qty"),
        )
