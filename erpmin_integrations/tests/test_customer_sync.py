from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase


class TestMaskedEmail(FrappeTestCase):
    def test_amazon_in_masked_email_detected(self):
        from erpmin_integrations.customer import _is_masked_email
        self.assertTrue(_is_masked_email("abc123@marketplace.amazon.in"))

    def test_amazon_com_masked_email_detected(self):
        from erpmin_integrations.customer import _is_masked_email
        self.assertTrue(_is_masked_email("xyz@marketplace.amazon.com"))

    def test_real_email_not_masked(self):
        from erpmin_integrations.customer import _is_masked_email
        self.assertFalse(_is_masked_email("john@gmail.com"))

    def test_empty_email_not_masked(self):
        from erpmin_integrations.customer import _is_masked_email
        self.assertFalse(_is_masked_email(""))


class TestDedup(FrappeTestCase):
    @patch("frappe.db.get_value")
    def test_find_by_contact_email_returns_customer(self, mock_get_value):
        mock_get_value.side_effect = ["CONTACT-001", "CUST-001"]
        from erpmin_integrations.customer import _find_by_contact_email
        result = _find_by_contact_email("john@example.com")
        self.assertEqual(result, "CUST-001")

    @patch("frappe.db.get_value", return_value=None)
    def test_find_by_contact_email_returns_none_when_not_found(self, mock_get_value):
        from erpmin_integrations.customer import _find_by_contact_email
        result = _find_by_contact_email("nobody@example.com")
        self.assertIsNone(result)

    @patch("frappe.db.get_value")
    def test_find_by_contact_phone_returns_customer(self, mock_get_value):
        mock_get_value.side_effect = ["CONTACT-001", "CUST-001"]
        from erpmin_integrations.customer import _find_by_contact_phone
        result = _find_by_contact_phone("9876543210")
        self.assertEqual(result, "CUST-001")

    @patch("frappe.db.get_value", return_value=None)
    def test_find_by_contact_phone_returns_none_when_not_found(self, mock_get_value):
        from erpmin_integrations.customer import _find_by_contact_phone
        result = _find_by_contact_phone("0000000000")
        self.assertIsNone(result)


import frappe


class TestCreateCustomer(FrappeTestCase):
    def tearDown(self):
        for name in frappe.get_all("Customer", filters={"customer_name": ["like", "Test CS%"]}, pluck="name"):
            frappe.delete_doc("Customer", name, ignore_permissions=True, force=True)
        frappe.db.commit()

    @patch("erpmin_integrations.customer._create_contact")
    @patch("erpmin_integrations.customer._create_address")
    def test_creates_customer_with_email_and_phone(self, mock_addr, mock_contact):
        from erpmin_integrations.customer import _create_customer
        name = _create_customer(
            {"name": "Test CS John", "source": "Amazon", "gstin": ""},
            email="testcs@example.com",
            phone="9876543210",
        )
        customer = frappe.get_doc("Customer", name)
        self.assertEqual(customer.customer_name, "Test CS John")
        self.assertEqual(customer.email_id, "testcs@example.com")
        self.assertEqual(customer.mobile_no, "9876543210")
        self.assertEqual(customer.custom_source_channel, "Amazon")
        self.assertEqual(customer.customer_type, "Individual")

    @patch("erpmin_integrations.customer._create_contact")
    @patch("erpmin_integrations.customer._create_address")
    @patch("india_compliance.gst_india.overrides.party.validate_gstin", return_value="29ABCDE1234F1Z5")
    def test_sets_company_type_when_gstin_present(self, mock_gstin, mock_addr, mock_contact):
        from erpmin_integrations.customer import _create_customer
        name = _create_customer(
            {"name": "Test CS Corp", "source": "Amazon", "gstin": "29ABCDE1234F1Z5"},
            email="corp@example.com",
            phone="",
        )
        customer = frappe.get_doc("Customer", name)
        self.assertEqual(customer.customer_type, "Company")
        self.assertEqual(customer.gstin, "29ABCDE1234F1Z5")


class TestCreateContact(FrappeTestCase):
    def setUp(self):
        self._customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": "Test CS Contact Customer",
            "customer_group": "Individual",
            "territory": "India",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    def tearDown(self):
        for c in frappe.get_all("Contact", filters={"first_name": ["like", "Test CS%"]}, pluck="name"):
            frappe.delete_doc("Contact", c, ignore_permissions=True, force=True)
        frappe.delete_doc("Customer", self._customer.name, ignore_permissions=True, force=True)
        frappe.db.commit()

    def test_contact_created_with_email_and_phone(self):
        from erpmin_integrations.customer import _create_contact
        _create_contact(self._customer.name, "Test CS John Smith", "testcs2@example.com", "9876540000")
        contact_links = frappe.get_all(
            "Dynamic Link",
            filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": self._customer.name},
            pluck="parent",
        )
        self.assertEqual(len(contact_links), 1)
        c = frappe.get_doc("Contact", contact_links[0])
        self.assertEqual(c.first_name, "Test CS John")
        self.assertEqual(c.last_name, "Smith")
        emails = [e.email_id for e in c.email_ids]
        phones = [p.phone for p in c.phone_nos]
        self.assertIn("testcs2@example.com", emails)
        self.assertIn("9876540000", phones)

    def test_update_contact_adds_missing_phone(self):
        from erpmin_integrations.customer import _create_contact, _update_contact
        _create_contact(self._customer.name, "Test CS Jane", "testcs3@example.com", "")
        _update_contact(self._customer.name, "", "9876541111")
        contact_name = frappe.db.get_value(
            "Dynamic Link",
            {"parenttype": "Contact", "link_doctype": "Customer", "link_name": self._customer.name},
            "parent",
        )
        c = frappe.get_doc("Contact", contact_name)
        phones = [p.phone for p in c.phone_nos]
        self.assertIn("9876541111", phones)

    def test_update_contact_does_not_duplicate_email(self):
        from erpmin_integrations.customer import _create_contact, _update_contact
        _create_contact(self._customer.name, "Test CS Dupe", "testcs4@example.com", "")
        _update_contact(self._customer.name, "testcs4@example.com", "")
        contact_name = frappe.db.get_value(
            "Dynamic Link",
            {"parenttype": "Contact", "link_doctype": "Customer", "link_name": self._customer.name},
            "parent",
        )
        c = frappe.get_doc("Contact", contact_name)
        emails = [e.email_id for e in c.email_ids]
        self.assertEqual(emails.count("testcs4@example.com"), 1)


class TestCreateAddress(FrappeTestCase):
    def setUp(self):
        self._customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": "Test CS Address Customer",
            "customer_group": "Individual",
            "territory": "India",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    def tearDown(self):
        for a in frappe.get_all("Address", filters={"address_title": self._customer.name}, pluck="name"):
            frappe.delete_doc("Address", a, ignore_permissions=True, force=True)
        frappe.delete_doc("Customer", self._customer.name, ignore_permissions=True, force=True)
        frappe.db.commit()

    def _addr(self, line1="12 MG Road", city="Bengaluru", pincode="560001"):
        return {"line1": line1, "line2": "", "city": city, "state": "Karnataka",
                "pincode": pincode, "country": "India", "phone": ""}

    def test_creates_shipping_address(self):
        from erpmin_integrations.customer import _create_address
        _create_address(self._customer.name, self._addr(), "Shipping", is_primary=True)
        addresses = frappe.get_all(
            "Address",
            filters={"address_title": self._customer.name, "address_type": "Shipping"},
            fields=["address_line1", "city", "is_shipping_address"],
        )
        self.assertEqual(len(addresses), 1)
        self.assertEqual(addresses[0].address_line1, "12 MG Road")
        self.assertEqual(addresses[0].is_shipping_address, 1)

    def test_skips_duplicate_address(self):
        from erpmin_integrations.customer import _add_address_if_new
        _add_address_if_new(self._customer.name, self._addr(), "Shipping")
        _add_address_if_new(self._customer.name, self._addr(), "Shipping")
        count = len(frappe.get_all("Address", filters={"address_title": self._customer.name}))
        self.assertEqual(count, 1)

    def test_adds_new_address_when_different(self):
        from erpmin_integrations.customer import _add_address_if_new
        _add_address_if_new(self._customer.name, self._addr(), "Shipping")
        _add_address_if_new(
            self._customer.name,
            {"line1": "99 Park Street", "line2": "", "city": "Mysuru",
             "state": "Karnataka", "pincode": "570001", "country": "India", "phone": ""},
            "Shipping",
        )
        count = len(frappe.get_all("Address", filters={"address_title": self._customer.name}))
        self.assertEqual(count, 2)

    def test_skips_incomplete_address(self):
        from erpmin_integrations.customer import _is_valid_address
        self.assertFalse(_is_valid_address({"line1": "", "city": "Bengaluru"}))
        self.assertFalse(_is_valid_address({"line1": "12 MG Road", "city": ""}))
        self.assertTrue(_is_valid_address({"line1": "12 MG Road", "city": "Bengaluru"}))


class TestGetOrCreateCustomer(FrappeTestCase):
    def _data(self, name="Test CS Full John", email="testcsfull@example.com",
               phone="", source="Amazon", shipping=None, billing=None, gstin=""):
        return {"name": name, "email": email, "phone": phone, "source": source,
                "shipping_address": shipping, "billing_address": billing, "gstin": gstin}

    def tearDown(self):
        for c in frappe.get_all("Customer", filters={"customer_name": ["like", "Test CS Full%"]}, pluck="name"):
            for addr in frappe.get_all("Address", filters={"address_title": c}, pluck="name"):
                frappe.delete_doc("Address", addr, ignore_permissions=True, force=True)
            for contact_link in frappe.get_all(
                "Dynamic Link",
                filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": c},
                pluck="parent",
            ):
                frappe.delete_doc("Contact", contact_link, ignore_permissions=True, force=True)
            frappe.delete_doc("Customer", c, ignore_permissions=True, force=True)
        frappe.db.commit()

    def test_creates_new_customer(self):
        from erpmin_integrations.customer import get_or_create_customer
        name = get_or_create_customer(self._data())
        self.assertTrue(frappe.db.exists("Customer", name))

    def test_deduplicates_by_email(self):
        from erpmin_integrations.customer import get_or_create_customer
        name1 = get_or_create_customer(self._data())
        name2 = get_or_create_customer(self._data(name="Test CS Full Jane"))
        self.assertEqual(name1, name2)

    def test_masked_email_falls_through_to_name(self):
        from erpmin_integrations.customer import get_or_create_customer
        name1 = get_or_create_customer(self._data(
            name="Test CS Full Masked", email="abc@marketplace.amazon.in"
        ))
        name2 = get_or_create_customer(self._data(
            name="Test CS Full Masked", email="abc@marketplace.amazon.in"
        ))
        self.assertEqual(name1, name2)

    def test_adds_new_shipping_address_on_second_order(self):
        from erpmin_integrations.customer import get_or_create_customer
        addr1 = {"line1": "12 MG Road", "city": "Bengaluru", "pincode": "560001",
                 "state": "Karnataka", "country": "India", "phone": ""}
        addr2 = {"line1": "99 Park St", "city": "Mysuru", "pincode": "570001",
                 "state": "Karnataka", "country": "India", "phone": ""}
        cust = get_or_create_customer(self._data(
            email="testcsfull2@example.com", name="Test CS Full Multi", shipping=addr1
        ))
        get_or_create_customer(self._data(
            email="testcsfull2@example.com", name="Test CS Full Multi", shipping=addr2
        ))
        linked = frappe.get_all(
            "Dynamic Link",
            filters={"parenttype": "Address", "link_doctype": "Customer", "link_name": cust},
            pluck="parent",
        )
        self.assertEqual(len(linked), 2)
