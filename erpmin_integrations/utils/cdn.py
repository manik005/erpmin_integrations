def get_public_urls_for_item(item, base_url: str) -> list[str]:
    """Return a list of public URLs for an item's images (and videos).

    Reads from the custom_product_images child table sorted by sort_order,
    falls back to item.image if the table is empty. Skips non-/files/ paths.
    """
    if not base_url:
        return []

    base_url = base_url.rstrip("/")
    rows = sorted(
        getattr(item, "custom_product_images", []) or [],
        key=lambda r: (getattr(r, "sort_order", 0) or 0),
    )

    urls = []
    for row in rows:
        file_path = getattr(row, "file", "") or ""
        if not file_path or not file_path.startswith("/files/"):
            continue
        urls.append(base_url + file_path)

    if not urls:
        primary = getattr(item, "image", "") or ""
        if primary.startswith("/files/"):
            urls = [base_url + primary]

    return urls
