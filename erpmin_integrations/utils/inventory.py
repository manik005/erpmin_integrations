import frappe


def get_available_qty(item_code, warehouse="Main Warehouse"):
    bin_data = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "reserved_qty"],
        as_dict=True,
    )
    if not bin_data:
        return 0
    return max(0, (bin_data.actual_qty or 0) - (bin_data.reserved_qty or 0))
