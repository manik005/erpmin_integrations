import frappe


def get_or_create_customer(data: dict) -> str:
    """Find or create a Customer from order data.

    Args:
        data: dict with keys: name, email, phone, source,
              shipping_address, billing_address, gstin

    Returns:
        ERPNext Customer docname
    """
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()

    existing = None

    if email and not _is_masked_email(email):
        existing = _find_by_contact_email(email)

    if not existing and phone:
        existing = _find_by_contact_phone(phone)

    if not existing and (not email or _is_masked_email(email)):
        existing = frappe.db.get_value("Customer", {"customer_name": data.get("name", "")})

    if existing:
        _update_contact(existing, email if not _is_masked_email(email) else "", phone)
        if data.get("shipping_address") and _is_valid_address(data["shipping_address"]):
            _add_address_if_new(existing, data["shipping_address"], "Shipping")
        if data.get("billing_address") and _is_valid_address(data["billing_address"]):
            _add_address_if_new(existing, data["billing_address"], "Billing")
        return existing

    customer_name = _create_customer(data, email=email, phone=phone)
    _create_contact(customer_name, data.get("name", ""), email, phone)

    if data.get("shipping_address") and _is_valid_address(data["shipping_address"]):
        _create_address(customer_name, data["shipping_address"], "Shipping", is_primary=True)
    if data.get("billing_address") and _is_valid_address(data["billing_address"]):
        _create_address(customer_name, data["billing_address"], "Billing", is_primary=True)

    return customer_name


def _is_masked_email(email: str) -> bool:
    """Amazon masks buyer emails with @marketplace.amazon.in / .com."""
    if not email:
        return False
    return "@marketplace.amazon." in email.lower()


def _find_by_contact_email(email: str) -> str | None:
    """Return Customer name linked to this email via Contact, or None."""
    contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
    if not contact_name:
        return None
    return frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "parent": contact_name, "link_doctype": "Customer"},
        "link_name",
    )


def _find_by_contact_phone(phone: str) -> str | None:
    """Return Customer name linked to this phone via Contact, or None."""
    contact_name = frappe.db.get_value("Contact Phone", {"phone": phone}, "parent")
    if not contact_name:
        return None
    return frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "parent": contact_name, "link_doctype": "Customer"},
        "link_name",
    )


def _create_customer(data: dict, email: str = "", phone: str = "") -> str:
    """Create a new ERPNext Customer. Returns the docname."""
    customer = frappe.new_doc("Customer")
    customer.customer_name = data.get("name", "")
    customer.customer_type = "Company" if data.get("gstin") else "Individual"
    customer.customer_group = "Individual"
    customer.territory = "India"
    customer.custom_source_channel = data.get("source", "")

    if email and not _is_masked_email(email):
        customer.email_id = email
    if phone:
        customer.mobile_no = phone
    if data.get("gstin"):
        customer.gstin = data["gstin"]

    customer.insert(ignore_permissions=True)
    frappe.db.commit()
    return customer.name


def _create_contact(customer_name: str, full_name: str, email: str, phone: str) -> None:
    """Create a Contact linked to the Customer."""
    parts = full_name.strip().split(" ", 1)
    contact = frappe.new_doc("Contact")
    contact.first_name = parts[0]
    contact.last_name = parts[1] if len(parts) > 1 else ""

    if email and not _is_masked_email(email):
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
    if phone:
        contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})

    contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    contact.insert(ignore_permissions=True)
    frappe.db.commit()


def _update_contact(customer_name: str, email: str, phone: str) -> None:
    """Add missing email or phone to the customer's existing contact."""
    contact_name = frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer_name},
        "parent",
    )
    if not contact_name:
        return

    contact = frappe.get_doc("Contact", contact_name)
    updated = False

    if email and not _is_masked_email(email):
        if email not in [e.email_id for e in contact.email_ids]:
            contact.append("email_ids", {"email_id": email})
            updated = True

    if phone:
        if phone not in [p.phone for p in contact.phone_nos]:
            contact.append("phone_nos", {"phone": phone})
            updated = True

    if updated:
        contact.save(ignore_permissions=True)
        frappe.db.commit()


def _create_address(customer_name: str, addr: dict, address_type: str, is_primary: bool = False) -> str:
    """Create an Address linked to the Customer. Returns the docname."""
    address = frappe.new_doc("Address")
    address.address_title = customer_name
    address.address_type = address_type
    address.address_line1 = addr.get("line1", "")
    address.address_line2 = addr.get("line2", "")
    address.city = addr.get("city", "")
    address.state = addr.get("state", "")
    address.pincode = addr.get("pincode", "")
    address.country = addr.get("country", "India")

    if addr.get("phone"):
        address.phone = addr["phone"]
    if address_type == "Shipping":
        address.is_shipping_address = 1 if is_primary else 0
    elif address_type == "Billing":
        address.is_primary_address = 1 if is_primary else 0

    address.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    address.insert(ignore_permissions=True)
    frappe.db.commit()
    return address.name


def _add_address_if_new(customer_name: str, addr: dict, address_type: str) -> None:
    """Add address only if a matching one (same line1 + city) doesn't already exist."""
    if not _is_valid_address(addr):
        return

    existing = frappe.db.sql(
        """
        SELECT a.name FROM `tabAddress` a
        JOIN `tabDynamic Link` dl ON dl.parent = a.name
        WHERE dl.link_doctype = 'Customer'
          AND dl.link_name = %(customer)s
          AND a.address_line1 = %(line1)s
          AND a.city = %(city)s
        LIMIT 1
        """,
        {"customer": customer_name, "line1": addr.get("line1", ""), "city": addr.get("city", "")},
    )
    if existing:
        return

    _create_address(customer_name, addr, address_type)


def _is_valid_address(addr: dict) -> bool:
    """An address requires at least line1 and city."""
    if not addr:
        return False
    return bool((addr.get("line1") or "").strip() and (addr.get("city") or "").strip())
