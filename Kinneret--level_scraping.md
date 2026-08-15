Great news — there's **no official API**, but the site uses simple **GET requests with URL query parameters**, making it very easy to scrape without any JavaScript rendering or AJAX magic. Here's everything you need:

---

## How the Site Works

All data is **server-side rendered** by a custom WordPress plugin (`lingo-kinneret`). You just make a plain HTTP GET request and parse the HTML response.

---

## Endpoint 1: Single Date Lookup

```
GET https://kineret.org.il/miflasim/?singledate=YYYY-MM-DD
```

**Example:**
```
https://kineret.org.il/miflasim/?singledate=2026-05-27
```

**How to parse the result** — the level value is always in:
```html
<span class="hp_miflas_height">-212.565</span>
```
And the full result block (with change info, distance to red lines, etc.) is in:
```html
<div class="kinneret-miflas">...</div>
```

---

## Endpoint 2: Date Range (with optional filters)

```
GET https://kineret.org.il/miflasim/?fromdate=YYYY-MM-DD&todate=YYYY-MM-DD&maxmiflas=VALUE&minmiflas=VALUE&Frequency=daily
```

Parameters:
- `fromdate` / `todate` — date range
- `maxmiflas` / `minmiflas` — optional filter (e.g. only show days where level was below a threshold). Don't forget the minus sign!
- `Frequency` — hardcoded as `daily`

---

## Python Scraper Example

```python
import requests
from bs4 import BeautifulSoup

def get_kinneret_level(date: str) -> dict:
    """date format: YYYY-MM-DD"""
    url = f"https://kineret.org.il/miflasim/?singledate={date}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    
    level = soup.select_one(".hp_miflas_height")
    full_block = soup.select_one(".kinneret-miflas")
    
    return {
        "date": date,
        "level": float(level.text.strip()) if level else None,
        "details": full_block.get_text("\n", strip=True) if full_block else None
    }

# Example
print(get_kinneret_level("2026-05-27"))
# → {'date': '2026-05-27', 'level': -212.565, 'details': 'מפלס הכינרת 27/05/26\n-212.565\nירידה של...'}
```

---

## Historical Bulk Data

The site also offers a **direct Excel file download** for data up to 2002:
```
https://kineret.org.il/wp-content/uploads/...  (linked as XLS, 1.7MB)
```
You'd need to click through to get the exact URL, but it's linked on the page under "הורדת קבצי הנתונים".

---

## Key Notes

- **Data goes back to September 1966** and is available daily up to today.
- No authentication, no CSRF tokens, no rate-limit headers observed.
- The site uses Cloudflare, so add a reasonable delay if looping over many dates.
- Be a considerate scraper — add `time.sleep(0.5)` between requests if fetching bulk historical data.