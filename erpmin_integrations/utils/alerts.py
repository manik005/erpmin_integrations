import frappe
from frappe.utils import add_days, today, now_datetime


def send_error_digest():
    """Send a daily digest of OpenCart/Amazon integration errors to configured alert emails."""
    since = add_days(today(), -1)

    errors = frappe.get_all(
        "Error Log",
        filters=[["creation", ">=", since]],
        or_filters=[
            ["method", "like", "%[OpenCart]%"],
            ["method", "like", "%[Amazon]%"],
        ],
        fields=["name", "method", "error", "creation"],
        order_by="creation desc",
        limit=100,
    )

    recipients = _get_alert_recipients()
    if not recipients or not errors:
        return

    rows = "".join(
        f"<tr><td>{e.creation}</td><td>{frappe.utils.escape_html(e.method)}</td>"
        f"<td><pre style='font-size:11px'>{frappe.utils.escape_html((e.error or '')[:500])}</pre></td></tr>"
        for e in errors
    )

    body = f"""
    <h3>Integration Error Digest — {today()}</h3>
    <p>{len(errors)} error(s) in the last 24 hours.</p>
    <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;width:100%">
      <thead>
        <tr>
          <th>Time</th><th>Error Title</th><th>Details (first 500 chars)</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p><a href="/app/error-log">View all errors in ERPNext</a></p>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=f"[ERP] Integration Errors: {len(errors)} issue(s) on {today()}",
        message=body,
        delayed=False,
    )

    frappe.logger().info(f"[Alerts] Error digest sent: {len(errors)} errors to {recipients}")


def _get_alert_recipients() -> list[str]:
    """Collect unique alert emails from OpenCart Settings and Amazon Settings."""
    emails = set()

    for doctype in ("OpenCart Settings", "Amazon Settings"):
        try:
            email = frappe.db.get_single_value(doctype, "alert_email")
            if email:
                for addr in email.split(","):
                    addr = addr.strip()
                    if addr:
                        emails.add(addr)
        except Exception:
            pass

    return list(emails)
