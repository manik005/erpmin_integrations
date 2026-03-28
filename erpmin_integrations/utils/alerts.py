import frappe
from frappe.utils import add_days, today

_DEFAULT_THRESHOLD = 10


def send_error_digest():
    """Send a daily digest of OpenCart/Amazon integration errors to configured alert emails."""
    if not frappe.db.get_single_value("ERPmin Settings", "enable_error_digest"):
        return

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


def send_low_stock_alert():
    """Send alert for items whose available qty has dropped to or below the configured threshold.

    Checks items synced to OpenCart or Amazon in their respective sync warehouses.
    Runs daily at 8 AM alongside the error digest.
    """
    if not frappe.db.get_single_value("ERPmin Settings", "enable_low_stock_alerts"):
        return

    threshold = int(
        frappe.db.get_single_value("ERPmin Settings", "low_stock_threshold") or _DEFAULT_THRESHOLD
    )
    recipients = _get_alert_recipients()
    if not recipients:
        return

    # Collect sync warehouses from both channel settings
    warehouses = set()
    for doctype in ("OpenCart Settings", "Amazon Settings"):
        wh = frappe.db.get_single_value(doctype, "default_warehouse")
        if wh:
            warehouses.add(wh)

    if not warehouses:
        return

    low_stock_items = frappe.db.sql(
        """
        SELECT
            b.item_code,
            b.warehouse,
            (b.actual_qty - b.reserved_qty) AS available_qty,
            i.item_name,
            i.custom_sync_to_opencart,
            i.custom_sync_to_amazon
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse IN %(warehouses)s
          AND (i.custom_sync_to_opencart = 1 OR i.custom_sync_to_amazon = 1)
          AND (b.actual_qty - b.reserved_qty) <= %(threshold)s
          AND (i.disabled = 0 OR i.disabled IS NULL)
          AND (i.custom_discontinued_date IS NULL OR i.custom_discontinued_date > CURDATE())
        ORDER BY (b.actual_qty - b.reserved_qty) ASC
        """,
        {"warehouses": list(warehouses), "threshold": threshold},
        as_dict=True,
    )

    if not low_stock_items:
        return

    rows = "".join(
        f"<tr>"
        f"<td>{r.item_code}</td>"
        f"<td>{frappe.utils.escape_html(r.item_name or '')}</td>"
        f"<td>{r.warehouse}</td>"
        f"<td style='text-align:center;color:{'red' if r.available_qty <= 0 else 'orange'}'>"
        f"<b>{int(r.available_qty)}</b></td>"
        f"<td>{'OpenCart' if r.custom_sync_to_opencart else ''}{'  Amazon' if r.custom_sync_to_amazon else ''}</td>"
        f"</tr>"
        for r in low_stock_items
    )

    body = f"""
    <h3>Low Stock Alert — {today()}</h3>
    <p>{len(low_stock_items)} item(s) at or below the threshold of <b>{threshold} units</b>.</p>
    <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;width:100%">
      <thead>
        <tr>
          <th>Item Code</th><th>Item Name</th><th>Warehouse</th>
          <th>Available Qty</th><th>Channels</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p><a href="/app/query-report/Stock Balance">View Stock Balance in ERPNext</a></p>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=f"[ERP] Low Stock Alert: {len(low_stock_items)} item(s) at or below {threshold} units",
        message=body,
        delayed=False,
    )

    frappe.logger().info(f"[Alerts] Low stock alert sent: {len(low_stock_items)} items to {recipients}")


def _get_alert_recipients() -> list[str]:
    """Read comma-separated alert emails from ERPmin Settings."""
    email_str = frappe.db.get_single_value("ERPmin Settings", "alert_email") or ""
    return [addr.strip() for addr in email_str.split(",") if addr.strip()]
