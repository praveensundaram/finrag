"""Step 1: HTML filing -> labeled sections, using sec2md.

sec2md handles Item detection (Items 1-16), page footer removal, and tables.
"""
import sec2md


def load_sections(path):
    """Parse a 10-K and return one section per Item: [{"item": "3", "text": ...}, ...]."""
    with open(path, "rb") as f:
        html = f.read()
    pages = sec2md.parse_filing(html)
    items = sec2md.extract_sections(pages, filing_type="10-K")

    sections = []
    for s in items:
        if s.item is None:      # parts sec2md couldn't assign to an Item
            continue
        sections.append({
            "item": s.item.replace("ITEM", "").strip(),   # "ITEM 1A" -> "1A"
            "text": s.markdown(),
        })
    return sections