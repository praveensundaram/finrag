# Style census: group every text block in the filing by its visual style,
# to check which styles are headings and whether they're consistent across Items.
import re
from collections import defaultdict
from bs4 import BeautifulSoup

PATH = "data/raw/aapl-2025-10k.htm"
ITEM_RE = re.compile(r"^Item\s+(\d+[A-C]?)\.", re.IGNORECASE)


def parse_style(tag):
    """Turn a tag's style="a:b;c:d" attribute into a dict."""
    out = {}
    for part in (tag.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


with open(PATH, encoding="utf-8", errors="ignore") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

groups = defaultdict(lambda: {"count": 0, "samples": [], "items": set(), "total_len": 0})
current_item = "front"

for div in soup.find_all("div"):
    #only need innermost divs, otherwise will duplicate counts
    if div.find("div") or div.find_parent("table") or not div.get_text(" ", strip=True): continue
    text = div.get_text(" ", strip=True)
    spans = [s for s in div.find_all("span") if s.get_text(strip=True)]
    if not spans:  continue
    span_styles = [parse_style(s) for s in spans]
    first = span_styles[0]
    weight = first.get("font-weight", "400")
    italic = first.get("font-style", "normal") == "italic"
    # MIXED = the block contains more than one style (e.g. a bold lead-in, then normal text)
    mixed = len({(s.get("font-weight", "400"), s.get("font-style", "normal")) for s in span_styles}) > 1
    dstyle = parse_style(div)
    key = (weight, italic, dstyle.get("margin-top", "-"),
           "indent" if "text-indent" in dstyle else "",
           "MIXED" if mixed else "")

    # Track which Item we're in, using bold "Item N." headings
    m = ITEM_RE.match(text)
    if m and weight in ("700", "bold"):
        current_item = m.group(1)

    g = groups[key]
    g["count"] += 1
    g["total_len"] += len(text)
    g["items"].add(current_item)
    if len(g["samples"]) < 1000:
        g["samples"].append(f"{len(text):4}  {text[:70]}")

for key, g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
    weight, italic, margin, indent, mixed = key
    print(f"weight={weight} italic={italic} margin-top={margin} {indent} {mixed}")
    print(f"  count={g['count']}  avg_len={g['total_len'] // g['count']}  items={sorted(g['items'])}")
    for s in g["samples"]:
        print(f"    - {s}")
    print()