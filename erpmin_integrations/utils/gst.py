"""
Monthly GSTR-1 auto-generation utility.

Runs on the 1st of each month at 8 AM (see hooks.py scheduler_events).
Queries submitted Sales Invoices for the prior month, builds an HSN-wise
summary, and emails it to configured alert recipients.
"""
import frappe
from frappe.utils import add_days, get_first_day, getdate, today, formatdate


def generate_gstr1_report():
    """Generate GSTR-1 summary for the previous month and email to alert recipients.

    Computes HSN-wise tax summary from submitted Sales Invoices.
    Attempts to use India Compliance's GSTR-1 report if available; falls back
    to a direct DB query otherwise.

    Filing deadline reminder: GSTR-1 is due by the 11th of the current month.
    """
    if not frappe.db.get_single_value("ERPmin Settings", "enable_gstr1_auto_report"):
        frappe.logger().info("[GST] GSTR-1 auto report is disabled in ERPmin Settings — skipping")
        return

    from erpmin_integrations.utils.alerts import _get_alert_recipients

    recipients = _get_alert_recipients()
    if not recipients:
        frappe.logger().info("[GST] No alert recipients configured — skipping GSTR-1 email")
        return

    period_start, period_end, period_label = _get_previous_month_range()
    company = _get_default_company()
    if not company:
        frappe.logger().warning("[GST] No company found — skipping GSTR-1 generation")
        return

    gstin = frappe.db.get_value("Company", company, "gstin") or ""

    # Try India Compliance first; fall back to raw query
    hsn_rows = _get_hsn_summary_india_compliance(company, period_start, period_end)
    if hsn_rows is None:
        hsn_rows = _get_hsn_summary_raw(company, period_start, period_end)

    invoice_count, total_taxable, total_gst = _get_invoice_totals(company, period_start, period_end)

    _send_gstr1_email(
        recipients=recipients,
        period_label=period_label,
        company=company,
        gstin=gstin,
        invoice_count=invoice_count,
        total_taxable=total_taxable,
        total_gst=total_gst,
        hsn_rows=hsn_rows,
    )

    frappe.logger().info(
        f"[GST] GSTR-1 summary emailed for {period_label}: "
        f"{invoice_count} invoices, ₹{total_taxable:.2f} taxable, ₹{total_gst:.2f} GST"
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _get_previous_month_range():
    """Return (start_date, end_date, label) for the previous calendar month."""
    first_of_today = get_first_day(today())
    last_of_prev = add_days(first_of_today, -1)
    first_of_prev = get_first_day(last_of_prev)
    label = formatdate(first_of_prev, "MMMM YYYY")
    return str(first_of_prev), str(last_of_prev), label


def _get_default_company() -> str | None:
    company = frappe.defaults.get_global_default("company")
    if not company:
        rows = frappe.get_all("Company", filters={"country": "India"}, limit=1, pluck="name")
        company = rows[0] if rows else None
    if not company:
        rows = frappe.get_all("Company", limit=1, pluck="name")
        company = rows[0] if rows else None
    return company


def _get_hsn_summary_india_compliance(company: str, period_start: str, period_end: str) -> list | None:
    """Try to get HSN-wise summary using India Compliance's GSTR-1 report.

    Returns a list of dicts with keys: hsn_code, description, taxable_value, tax_rate,
    cgst, sgst, igst  — or None if India Compliance is not available.
    """
    try:
        import importlib
        ic = importlib.import_module("india_compliance.gst_india.report.gstr_1.gstr_1")
        filters = frappe._dict(
            company=company,
            from_date=period_start,
            to_date=period_end,
            type_of_business="B2C Small",
        )
        data = ic.get_data(filters)
        if data:
            return data
        return []
    except Exception:
        return None


def _get_hsn_summary_raw(company: str, period_start: str, period_end: str) -> list:
    """Fallback: compute HSN-wise taxable summary directly from DB.

    Groups by HSN code + GST rate, summing taxable values and tax amounts.
    Only considers submitted (docstatus=1) Sales Invoices.
    """
    rows = frappe.db.sql(
        """
        SELECT
            sii.gst_hsn_code                            AS hsn_code,
            sii.item_name                               AS description,
            ROUND(SUM(sii.taxable_value), 2)            AS taxable_value,
            ROUND(
                SUM(
                    CASE WHEN stc.account_head LIKE '%CGST%' THEN stc.tax_amount ELSE 0 END
                ) * 2, 2
            )                                           AS total_gst,
            ROUND(
                SUM(CASE WHEN stc.account_head LIKE '%CGST%' THEN stc.tax_amount ELSE 0 END), 2
            )                                           AS cgst,
            ROUND(
                SUM(CASE WHEN stc.account_head LIKE '%SGST%' THEN stc.tax_amount ELSE 0 END), 2
            )                                           AS sgst,
            ROUND(
                SUM(CASE WHEN stc.account_head LIKE '%IGST%' THEN stc.tax_amount ELSE 0 END), 2
            )                                           AS igst
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si
            ON si.name = sii.parent
        LEFT JOIN `tabSales Taxes and Charges` stc
            ON stc.parent = si.name
        WHERE si.docstatus = 1
          AND si.company = %(company)s
          AND si.posting_date BETWEEN %(start)s AND %(end)s
          AND (si.is_return = 0 OR si.is_return IS NULL)
        GROUP BY sii.gst_hsn_code, sii.item_name
        ORDER BY taxable_value DESC
        """,
        {"company": company, "start": period_start, "end": period_end},
        as_dict=True,
    )
    return rows


def _get_invoice_totals(company: str, period_start: str, period_end: str) -> tuple:
    """Return (invoice_count, total_taxable_value, total_gst) for the period."""
    result = frappe.db.sql(
        """
        SELECT
            COUNT(DISTINCT si.name)         AS invoice_count,
            ROUND(SUM(si.total), 2)         AS total_taxable,
            ROUND(SUM(si.total_taxes_and_charges), 2) AS total_gst
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.company = %(company)s
          AND si.posting_date BETWEEN %(start)s AND %(end)s
          AND (si.is_return = 0 OR si.is_return IS NULL)
        """,
        {"company": company, "start": period_start, "end": period_end},
        as_dict=True,
    )
    row = result[0] if result else {}
    return (
        int(row.get("invoice_count") or 0),
        float(row.get("total_taxable") or 0),
        float(row.get("total_gst") or 0),
    )


def _send_gstr1_email(
    recipients: list,
    period_label: str,
    company: str,
    gstin: str,
    invoice_count: int,
    total_taxable: float,
    total_gst: float,
    hsn_rows: list,
):
    filing_deadline = _get_filing_deadline()

    if hsn_rows:
        hsn_table_rows = "".join(
            f"<tr>"
            f"<td>{frappe.utils.escape_html(str(r.get('hsn_code') or ''))}</td>"
            f"<td>{frappe.utils.escape_html(str(r.get('description') or ''))}</td>"
            f"<td style='text-align:right'>₹{float(r.get('taxable_value') or 0):,.2f}</td>"
            f"<td style='text-align:right'>₹{float(r.get('cgst') or 0):,.2f}</td>"
            f"<td style='text-align:right'>₹{float(r.get('sgst') or 0):,.2f}</td>"
            f"<td style='text-align:right'>₹{float(r.get('igst') or 0):,.2f}</td>"
            f"</tr>"
            for r in hsn_rows
        )
        hsn_section = f"""
        <h4>HSN-wise Summary</h4>
        <table border="1" cellpadding="4" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead>
            <tr style="background:#f0f0f0">
              <th>HSN Code</th><th>Description</th>
              <th>Taxable Value</th><th>CGST</th><th>SGST</th><th>IGST</th>
            </tr>
          </thead>
          <tbody>{hsn_table_rows}</tbody>
        </table>
        """
    else:
        hsn_section = "<p><em>No invoice data found for this period.</em></p>"

    body = f"""
    <h3>GSTR-1 Summary — {period_label}</h3>
    <table cellpadding="6" style="font-size:14px">
      <tr><td><b>Company</b></td><td>{frappe.utils.escape_html(company)}</td></tr>
      <tr><td><b>GSTIN</b></td><td>{frappe.utils.escape_html(gstin)}</td></tr>
      <tr><td><b>Period</b></td><td>{period_label}</td></tr>
      <tr><td><b>Total Invoices</b></td><td>{invoice_count}</td></tr>
      <tr><td><b>Total Taxable Value</b></td><td>₹{total_taxable:,.2f}</td></tr>
      <tr><td><b>Total GST Collected</b></td><td>₹{total_gst:,.2f}</td></tr>
      <tr><td><b>Filing Deadline</b></td>
          <td style="color:{'red' if _is_deadline_close(filing_deadline) else 'inherit'}">
              <b>{filing_deadline}</b> (GSTR-1 due by 11th)
          </td>
      </tr>
    </table>
    <br>
    {hsn_section}
    <br>
    <p>
      <a href="/app/query-report/GSTR 1">Open GSTR-1 report in ERPNext</a>
    </p>
    <p style="font-size:12px;color:#888">
      This summary was auto-generated on {today()}. File GSTR-1 via the India Compliance module
      or the GST portal before the deadline.
    </p>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=f"[ERP] GSTR-1 Summary — {period_label} (due {filing_deadline})",
        message=body,
        delayed=False,
    )


def _get_filing_deadline() -> str:
    """Return the GSTR-1 filing deadline for the current month (11th)."""
    from frappe.utils import get_first_day
    first = getdate(get_first_day(today()))
    deadline = first.replace(day=11)
    return formatdate(str(deadline), "dd MMM YYYY")


def _is_deadline_close(deadline_str: str) -> bool:
    """Return True if the deadline is within 3 days from today."""
    try:
        deadline = getdate(frappe.utils.parse_date(deadline_str))
        delta = (deadline - getdate(today())).days
        return 0 <= delta <= 3
    except Exception:
        return False
