import frappe

_AMAZON_MASKED_SUFFIXES = ("@marketplace.amazon.in", "@marketplace.amazon.com")


def get_or_create_customer(data: dict) -> str:
    """Get or create ERPNext Customer + Contact + Address from normalised channel data.
    Returns customer.name.
    """
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    name = (data.get("name") or "").strip()

    if _is_masked_email(email):
        email = ""

    # 1. Email on Contact
    if email:
        found = _find_by_contact_email(email)
        if found:
            _update_customer(found, data, email, phone)
            return found

    # 2. Email on Customer.email_id (legacy)
    if email:
        found = frappe.db.get_value("Customer", {"email_id": email})
        if found:
            _update_customer(found, data, email, phone)
            return found

    # 3. Phone on Contact
    if phone:
        found = _find_by_contact_phone(phone)
        if found:
            _update_customer(found, data, email, phone)
            return found

    # 4. Name (case-insensitive)
    if name:
        found = frappe.db.get_value("Customer", {"customer_name": name})
        if found:
            _update_customer(found, data, email, phone)
            return found

    # 5. Create new
    return _create_customer(data, email, phone)


def _update_customer(customer_name: str, data: dict, email: str, phone: str):
    """Add new addresses and missing contact info to an existing customer."""
    _update_contact(customer_name, email, phone)

    shipping = data.get("shipping_address")
    billing = data.get("billing_address")

    if shipping and _is_valid_address(shipping):
        _add_address_if_new(customer_name, shipping, "Shipping")

    if billing and _is_valid_address(billing):
        if not shipping or not _addresses_match(billing, shipping):
            _add_address_if_new(customer_name, billing, "Billing")


def _is_masked_email(email: str) -> bool:
    if not email:
        return False
    return any(email.lower().endswith(s) for s in _AMAZON_MASKED_SUFFIXES)


def _find_by_contact_email(email: str) -> str | None:
    """Find customer.name via Contact Email child table."""
    contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
    if not contact_name:
        return None
    return frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "parent": contact_name,
            "link_doctype": "Customer",
        },
        "link_name",
    )


def _find_by_contact_phone(phone: str) -> str | None:
    """Find customer.name via Contact Phone child table."""
    contact_name = frappe.db.get_value("Contact Phone", {"phone": phone}, "parent")
    if not contact_name:
        return None
    return frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "parent": contact_name,
            "link_doctype": "Customer",
        },
        "link_name",
    )


def _create_customer(data: dict, email: str, phone: str) -> str:
    """Create a new Customer record. Returns customer.name."""
    name = (data.get("name") or "").strip() or email or "Unknown Customer"
    gstin = (data.get("gstin") or "").strip()

    customer_group = "Individual"
    territory = "India"
    try:
        from erpmin_integrations.doctype.amazon_settings.amazon_settings import (
            get_settings,
        )
        settings = get_settings()
        customer_group = settings.default_customer_group or "Individual"
        territory = settings.default_territory or "India"
    except Exception:
        pass

    customer = frappe.new_doc("Customer")
    customer.customer_name = name
    customer.customer_type = "Company" if gstin else "Individual"
    customer.customer_group = customer_group
    customer.territory = territory
    customer.custom_source_channel = data.get("source", "")
    if email:
        customer.email_id = email
    if phone:
        customer.mobile_no = phone
    if gstin:
        customer.gstin = gstin

    try:
        customer.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value("Customer", {"customer_name": name})
        if existing:
            return existing
        raise

    shipping = data.get("shipping_address")
    billing = data.get("billing_address")

    _create_contact(customer.name, name, email, phone)

    if shipping and _is_valid_address(shipping):
        _create_address(customer.name, shipping, "Shipping", is_primary=True)

    if billing and _is_valid_address(billing):
        if not shipping or not _addresses_match(billing, shipping):
            _create_address(customer.name, billing, "Billing", is_primary=True)

    return customer.name


# --- stubs for Tasks 4 and 5 ---

def _create_contact(customer_name: str, full_name: str, email: str, phone: str):
    parts = (full_name or "").strip().rsplit(" ", 1)
    first_name = parts[0] or "Unknown"
    last_name = parts[1] if len(parts) > 1 else ""

    contact = frappe.new_doc("Contact")
    contact.first_name = first_name
    contact.last_name = last_name
    if email:
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
    if phone:
        contact.append("phone_nos", {"phone": phone, "is_primary_phone": 1})
    contact.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    contact.insert(ignore_permissions=True)


def _update_contact(customer_name: str, email: str, phone: str):
    """Add email/phone to existing Contact if not already present. Never overwrites."""
    contact_name = frappe.db.get_value(
        "Dynamic Link",
        {
            "parenttype": "Contact",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        "parent",
    )
    if not contact_name:
        return

    contact = frappe.get_doc("Contact", contact_name)
    changed = False

    if email and not any(e.email_id == email for e in contact.email_ids):
        contact.append("email_ids", {"email_id": email, "is_primary": 0})
        changed = True

    if phone and not any(p.phone == phone for p in contact.phone_nos):
        contact.append("phone_nos", {"phone": phone, "is_primary_phone": 0})
        changed = True

    if changed:
        contact.save(ignore_permissions=True)


def _create_address(customer_name: str, addr: dict, addr_type: str, is_primary: bool = False):
    address = frappe.new_doc("Address")
    address.address_title = customer_name
    address.address_type = addr_type
    address.address_line1 = addr.get("line1", "")
    address.address_line2 = addr.get("line2", "") or ""
    address.city = addr.get("city", "")
    address.state = addr.get("state", "") or ""
    address.pincode = addr.get("pincode", "") or ""
    address.country = addr.get("country") or "India"
    address.phone = addr.get("phone", "") or ""
    address.is_primary_address = 1 if is_primary else 0
    address.is_shipping_address = 1 if addr_type == "Shipping" else 0
    address.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    address.insert(ignore_permissions=True)


def _add_address_if_new(customer_name: str, addr: dict, addr_type: str):
    """Create address only if no matching address (line1+city+pincode) exists for this customer."""
    linked_names = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
        pluck="parent",
    )

    existing = (
        frappe.get_all(
            "Address",
            filters={"name": ["in", linked_names], "address_type": addr_type},
            fields=["address_line1", "city", "pincode"],
        )
        if linked_names
        else []
    )

    incoming_key = _address_key(addr)
    for a in existing:
        if _address_key({"line1": a.address_line1, "city": a.city, "pincode": a.pincode}) == incoming_key:
            return  # already exists

    is_primary = not existing
    _create_address(customer_name, addr, addr_type, is_primary=is_primary)


def _is_valid_address(addr: dict) -> bool:
    return bool((addr.get("line1") or "").strip() and (addr.get("city") or "").strip())


def _addresses_match(a: dict, b: dict) -> bool:
    return _address_key(a) == _address_key(b)


def _address_key(addr: dict) -> str:
    return (
        (addr.get("line1") or "").lower().strip()
        + (addr.get("city") or "").lower().strip()
        + (addr.get("pincode") or "").strip()
    )
