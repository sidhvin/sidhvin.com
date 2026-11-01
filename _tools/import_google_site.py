"""
Import the Google Site at sites.google.com/view/sidhvin into this static site.

Run from the repository root:  python _tools/import_google_site.py
It fetches every page live (Google's image URLs are signed and expire, so pages
and images must be fetched together), downloads all assets into ./assets, and
writes clean static HTML pages that GitHub Pages can serve.
Requires: pip install beautifulsoup4
"""
import hashlib, html, json, os, re, time, urllib.parse, urllib.request
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS_BASE = "https://sites.google.com/view/sidhvin/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
SITE_NAME = "Sidhvin"
DOMAIN = "https://sidhvin.com"

# (google sites path, output path ('' = home), label)
PAGES = [
    ("home", "", "Home"),
    ("work-experience", "work-experience", "Work experience"),
    ("projects", "projects", "Projects"),
    ("projects/yaskawa-hc10", "projects/yaskawa-hc10", "Yaskawa HC10"),
    ("projects/kth-hk-project", "projects/kth-hk-project", "KTH HK Project"),
    ("projects/aircrafts", "projects/aircrafts", "Aircrafts"),
    ("projects/aircrafts/fixed-wings", "projects/aircrafts/fixed-wings", "Fixed Wings"),
    ("projects/aircrafts/quadcopters", "projects/aircrafts/quadcopters", "Quadcopters"),
    ("projects/automobiles", "projects/automobiles", "Automobiles"),
    ("projects/cnc-machine", "projects/cnc-machine", "CNC Machine"),
    ("projects/balance-bike", "projects/balance-bike", "Balance Bike"),
    ("projects/lit-bike", "projects/lit-bike", "lit Bike"),
]

# Navigation tree, same order as the Google Site menu.
NAV = [
    ("Home", "/", []),
    ("Work experience", "/work-experience/", []),
    ("Projects", "/projects/", [
        ("Yaskawa HC10", "/projects/yaskawa-hc10/", []),
        ("KTH HK Project", "/projects/kth-hk-project/", []),
        ("Aircrafts", "/projects/aircrafts/", [
            ("Fixed Wings", "/projects/aircrafts/fixed-wings/", []),
            ("Quadcopters", "/projects/aircrafts/quadcopters/", []),
        ]),
        ("Automobiles", "/projects/automobiles/", []),
        ("CNC Machine", "/projects/cnc-machine/", []),
        ("Balance Bike", "/projects/balance-bike/", []),
        ("lit Bike", "/projects/lit-bike/", []),
    ]),
]

# Google Sites grid classes -> number of columns out of 12
COL_SPAN = {"R6PoUb": 1, "ibL1re": 2, "c5RTEf": 3, "II5mzb": 4, "wNfPc": 5, "qWD73c": 6,
            "OwsYgb": 7, "OiUrBf": 8, "Clt0zb": 9, "EehZO": 10, "zQtlcf": 11, "uQSCkd": 12}

EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/gif": ".gif",
       "image/webp": ".webp", "image/svg+xml": ".svg", "image/x-icon": ".ico",
       "image/vnd.microsoft.icon": ".ico", "application/pdf": ".pdf", "video/mp4": ".mp4"}

asset_by_hash = {}      # sha1 -> site path, so identical files are stored once
asset_log = []          # manifest rows
warnings = []


def fetch(url, tries=3):
    err = None
    for _ in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
            return r.headers.get("content-type", "").split(";")[0].strip(), r.read()
        except Exception as e:
            err = e
            time.sleep(1.5)
    raise RuntimeError(f"{url[:90]}: {err}")


def slugify(s, maxlen=48):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen].strip("-")


MAX_WEB_WIDTH = 2000   # published images are resized to at most this width


def sniff_ext(data, ctype, url):
    """Pick a file extension from the bytes first, then the content type."""
    magic = [(b"%PDF", ".pdf"), (b"\x89PNG", ".png"), (b"\xff\xd8\xff", ".jpg"), (b"GIF8", ".gif")]
    for sig, ext in magic:
        if data.startswith(sig):
            return ext
    if data[4:8] == b"ftyp":
        return ".mp4"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return EXT.get(ctype, os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".bin")


def unique_path(rel, data):
    """Return a repo-relative path that is free or already holds identical bytes."""
    base, ext = os.path.splitext(rel)
    n = 2
    while True:
        path = os.path.join(ROOT, *rel.split("/"))
        if not os.path.exists(path) or open(path, "rb").read() == data:
            return rel, path
        rel = f"{base}-{n}{ext}"
        n += 1


def web_copy(data, ext):
    """Return (bytes, ext) of a web-sized version of an image, or the input if already small."""
    if ext not in (".jpg", ".png", ".webp"):
        return data, ext
    try:
        from PIL import Image, ImageOps
        import io
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        resized = im.width > MAX_WEB_WIDTH
        if resized:
            im = im.resize((MAX_WEB_WIDTH, round(im.height * MAX_WEB_WIDTH / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        if ext == ".png":
            im.save(buf, "PNG", optimize=True)
        else:
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(buf, "JPEG", quality=85, optimize=True, progressive=True)
            ext = ".jpg"
        out = buf.getvalue()
        if resized or len(out) < len(data) * 0.9:
            return out, ext
    except Exception as e:
        warnings.append(f"could not optimise image: {e}")
    return data, ext


def save_asset(url, folder, name, kind="image", original_url=None):
    """Download url and store it under assets/<folder>/; return the site path ('/assets/...').

    Images: the untouched original goes to _google-sites-backup/original-images/<folder>/
    and a web-sized copy is published in assets/<folder>/.
    """
    if url.startswith("https://sites.google.com/sitesv-images") or "googleusercontent.com" in url:
        url = re.sub(r"=[a-z]\d*[^/=]*$", "", url) + "=s0"   # ask for the original size
    try:
        ctype, data = fetch(url)
    except Exception as e:
        warnings.append(f"download failed for {name}: {e}")
        return None
    if ctype.startswith("text/html"):
        warnings.append(f"not public / not found: {folder}/{name} ({(original_url or url)[:80]})")
        return None
    h = hashlib.sha1(data).hexdigest()
    if h in asset_by_hash:
        return asset_by_hash[h]
    ext = sniff_ext(data, ctype, url)
    publish = data
    if kind == "image":
        sub = folder[len("images/"):] if folder.startswith("images/") else folder
        orel, opath = unique_path(f"_google-sites-backup/original-images/{sub}/{name}{ext}", data)
        os.makedirs(os.path.dirname(opath), exist_ok=True)
        with open(opath, "wb") as f:
            f.write(data)
        publish, ext = web_copy(data, ext)
    rel, path = unique_path(f"assets/{folder}/{name}{ext}", publish)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(publish)
    site_path = "/" + rel
    asset_by_hash[h] = site_path
    asset_log.append({"file": rel, "bytes": len(publish), "original_bytes": len(data),
                      "type": ctype, "kind": kind, "source": (original_url or url)[:300]})
    return site_path


def local_drive_copy(folder, slug):
    """A private Drive file the owner downloaded manually into assets/<folder>/<slug>.*"""
    d = os.path.join(ROOT, "assets", folder)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if os.path.splitext(f)[0] == slug:
                return f"/assets/{folder}/{f}"
    return None


def rewrite_href(href):
    if not href:
        return href or ""
    href = html.unescape(href)
    if re.match(r"https?://(www\.)?google\.com/url\?", href):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("q")
        if q:
            href = q[0]
    m = re.match(r"(?:https://sites\.google\.com)?/view/sidhvin/?([^?#]*)(#.*)?$", href)
    if m:
        path, frag = m.group(1).strip("/"), m.group(2) or ""
        return ("/" if path in ("", "home") else f"/{path}/") + frag
    return href


# ---------------------------------------------------------------- text tiles

KEEP_ATTRS = {"a": {"href", "target"}}
TEXT_CLASS = {"TMjjoe": "caption"}


def clean_text_tile(tile):
    """Return clean HTML for a Google Sites text box."""
    box = BeautifulSoup(str(tile), "html.parser").find(class_="tyJCtd")
    for a in box.select(".aP9Z7e"):
        nxt = a.find_next_sibling()
        if nxt is not None and a.get("id"):
            nxt["data-anchor"] = a["id"]
        a.decompose()
    for junk in box.select(".PPhIP, script, style, svg"):
        junk.decompose()
    for el in box.find_all("div"):
        el.unwrap()
    for el in box.find_all(True):
        cls = el.get("class") or []
        newcls = [TEXT_CLASS[c] for c in cls if c in TEXT_CLASS]
        anchor = el.get("data-anchor")
        style = (el.get("style") or "").strip().rstrip(";").strip()
        keep = KEEP_ATTRS.get(el.name, set())
        el.attrs = {k: v for k, v in el.attrs.items() if k in keep}
        if el.name == "a":
            el["href"] = rewrite_href(el.get("href"))
            if el["href"].startswith("http"):
                el["target"] = "_blank"
                el["rel"] = "noopener"
            elif "target" in el.attrs:
                del el["target"]
        if style and style != "display: block":
            el["style"] = style
        if newcls:
            el["class"] = newcls
        if anchor:
            el["id"] = anchor
        if el.name == "span" and not el.attrs:
            el.unwrap()
    return box.decode_contents().strip()


def youtube_id(src):
    m = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]{6,})", src or "")
    return m.group(1) if m else None


class PageBuilder:
    def __init__(self, gs_path, out_path, label):
        self.gs_path, self.out_path, self.label = gs_path, out_path, label
        self.img_folder = "images/" + (out_path or "home")
        self.counter = 0
        self.text_chunks = []

    def next_name(self, hint):
        self.counter += 1
        return f"{self.counter:02d}-{slugify(hint) or 'image'}"

    # -- individual tile types -------------------------------------------------
    def tile_html(self, tile):
        box = tile.find(class_="tyJCtd")
        if box is None:
            return ""
        for widget in box.select(".PPhIP"):     # hidden "Copy heading link" buttons
            widget.decompose()
        car = box.find(class_="mr3rhf")
        if car:
            return self.carousel(car)
        frame = box.find("iframe")
        if frame is not None:
            return self.embed(box, frame)
        btn = box.find("a", class_="FKF6mc")
        if btn is not None:
            label = btn.get_text(" ", strip=True) or btn.get("aria-label", "")
            href = rewrite_href(btn.get("href"))
            ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
            wrap = box.find(class_="hEyo2d")
            align = "center" if wrap and "center" in (wrap.get("style") or "") else "left"
            self.text_chunks.append(label)
            return (f'<div class="btn-wrap" style="text-align:{align}"><a class="btn" '
                    f'href="{html.escape(href)}"{ext}>{html.escape(label)}</a></div>')
        if box.find(class_="iwQgFb"):
            return '<hr class="divider">'
        img = box.find("img")
        if img is not None and box.find(class_="t3iYD"):
            link = box.find("a", class_="fqo2vd")
            href = rewrite_href(link.get("href")) if link else None
            if href and href.startswith("http"):
                host = urllib.parse.urlparse(href).netloc.lower()
                host = re.sub(r"^(www\d?|m)\.", "", host)
                hint = host.rsplit(".", 1)[0] if host.count(".") >= 1 else host
            elif href:
                hint = "home" if href == "/" else href.strip("/").split("/")[-1].split("#")[0]
            else:
                heading = tile.find_previous(["h1", "h2", "h3"])
                hint = heading.get_text(" ", strip=True) if heading else ""
                if not hint or hint == SITE_NAME:
                    hint = self.label
            src = save_asset(html.unescape(img["src"]), self.img_folder,
                             self.next_name(("thumb-" if href else "") + hint))
            if not src:
                return ""
            alt = html.escape(img.get("alt") or img.get("aria-label") or hint.replace("-", " "))
            tag = f'<img src="{src}" alt="{alt}" loading="lazy">'
            if href:
                ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
                tag = f'<a href="{html.escape(href)}"{ext}>{tag}</a>'
            return f'<figure class="image">{tag}</figure>'
        text = clean_text_tile(tile)
        plain = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        if not plain:
            return ""
        self.text_chunks.append(plain)
        return f'<div class="text">{text}</div>'

    def carousel(self, car):
        slides = car.select(".nQBJnb")
        caps = [c.get_text(" ", strip=True) for c in car.select(".dVFkob")]
        m = re.search(r"aspect-ratio:\s*([\d.]+)\s*/\s*([\d.]+)", car.get("style") or "")
        ratio = f"{float(m.group(1)):.4f} / {float(m.group(2)):g}" if m else "16 / 9"
        items = []
        for i, s in enumerate(slides):
            u = re.search(r"url\(([^)]+)\)", s.get("style") or "")
            if not u:
                continue
            cap = caps[i] if i < len(caps) else ""
            src = save_asset(html.unescape(u.group(1).strip("'\"")), self.img_folder,
                             self.next_name("carousel-" + (cap or "slide")))
            if src:
                items.append((src, cap))
                if cap:
                    self.text_chunks.append(cap)
        slides_html = "".join(
            f'<div class="slide{" active" if i == 0 else ""}" role="img" '
            f'aria-label="{html.escape(c or "Carousel image")}" '
            f'style="background-image:url(\'{src}\')" data-caption="{html.escape(c)}"></div>'
            for i, (src, c) in enumerate(items))
        return (f'<div class="carousel" style="--ratio:{ratio}" '
                f'data-autostart="{car.get("data-autostart", "false")}" '
                f'data-interval="{car.get("data-transitionspeed", "3000")}" '
                f'data-dots="{car.get("data-showdots", "true")}" '
                f'data-captions="{car.get("data-showcaptions", "true")}" tabindex="0" aria-label="Image carousel">'
                f'<div class="slides">{slides_html}'
                f'<button class="nav prev" aria-label="Previous"><svg viewBox="0 0 48 48" width="36" height="36"><path d="M30.83 32.67l-9.17-9.17 9.17-9.17L28 11.5l-12 12 12 12z" fill="currentColor"/></svg></button>'
                f'<button class="nav next" aria-label="Next"><svg viewBox="0 0 48 48" width="36" height="36"><path d="M17.17 32.92l9.17-9.17-9.17-9.17L20 11.75l12 12-12 12z" fill="currentColor"/></svg></button>'
                f'</div><div class="caption"></div><div class="dots"></div></div>')

    def embed(self, box, frame):
        pad_div = box.find(attrs={"jsname": "WXxXjd"})
        pad = None
        if pad_div is not None:
            m = re.search(r"padding-top:\s*([\d.]+)%", pad_div.get("style") or "")
            pad = float(m.group(1)) if m else None
        label = frame.get("aria-label") or frame.get("title") or "Embedded content"
        yid = youtube_id(frame.get("src"))
        if yid:
            self.text_chunks.append(label.replace("YouTube Video, ", ""))
            return (f'<div class="embed" style="padding-top:{pad or 56.25:.4f}%"><iframe '
                    f'src="https://www.youtube.com/embed/{yid}" title="{html.escape(label)}" '
                    f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                    f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe></div>')
        doc = box.find(attrs={"data-embed-doc-id": True})
        if doc is not None:
            did = doc["data-embed-doc-id"]
            fname = label.replace("Drive, ", "")
            is_pdf = fname.lower().endswith(".pdf")
            folder, slug = ("documents" if is_pdf else "videos"), slugify(os.path.splitext(fname)[0])
            local = local_drive_copy(folder, slug) or save_asset(
                f"https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t",
                folder, slug, kind="drive-file", original_url=f"https://drive.google.com/file/d/{did}/view")
            self.text_chunks.append(fname)
            if local and local.endswith(".pdf"):
                return (f'<div class="embed doc" style="padding-top:{pad or 129.4:.4f}%"><iframe src="{local}" '
                        f'title="{html.escape(fname)}" loading="lazy"></iframe></div>'
                        f'<p class="embed-link"><a href="{local}" target="_blank" rel="noopener">'
                        f'Open {html.escape(fname)}</a></p>')
            if local and local.endswith(".mp4"):
                return f'<video class="video" src="{local}" controls preload="metadata"></video>'
            # Not public: keep the Google Drive preview, exactly like the Google Site does today.
            return (f'<div class="embed" style="padding-top:{pad or 56.25:.4f}%"><iframe '
                    f'src="https://drive.google.com/file/d/{did}/preview" title="{html.escape(fname)}" '
                    f'allow="autoplay" allowfullscreen loading="lazy"></iframe></div>')
        code_div = box.find(attrs={"data-code": True})
        if code_div is not None:
            code = code_div["data-code"]
            src = re.search(r'src="([^"]+)"', code)
            w = re.search(r"width:\s*(\d+)px", code)
            h = re.search(r"height:\s*(\d+)px", code)
            ratio = (int(h.group(1)) / int(w.group(1)) * 100) if (w and h) else 62.5
            if src:
                self.text_chunks.append("Interactive robot simulation")
                return (f'<div class="embed" style="padding-top:{ratio:.4f}%"><iframe src="{html.escape(src.group(1))}" '
                        f'title="Interactive simulation" allowfullscreen loading="lazy"></iframe></div>')
            return f'<div class="custom-embed">{code}</div>'
        src = frame.get("src") or frame.get("data-src") or ""
        warnings.append(f"unknown iframe kept as-is on {self.out_path or 'home'}: {src}")
        return (f'<div class="embed" style="padding-top:{pad or 56.25:.4f}%"><iframe '
                f'src="{html.escape(src)}" loading="lazy"></iframe></div>')

    # -- page structure ---------------------------------------------------------
    def section_html(self, sec):
        cls = sec.get("class") or []
        kind = "divider" if "WxWicb" in cls else "title" if "LB7kq" in cls else "band"
        tone = "grey" if "lQAHbd" in cls else "light" if "qeLZfd" in cls else "white"
        if kind == "title":
            tone = "white"
        rows = []
        for row in sec.select("div.LS81yb"):
            cols = []
            for col in row.find_all("div", recursive=False):
                span = next((COL_SPAN[c.split("-")[-1]] for c in (col.get("class") or [])
                             if c.startswith("hJDwNd-AhqUyc-") and c.split("-")[-1] in COL_SPAN), None)
                if span is None:
                    continue
                tiles_html = []
                for tile in col.select("div.oKdM2c"):
                    inner = tile.find(class_="jXK9ad")
                    flags = (inner.get("class") or []) if inner else []
                    content = self.tile_html(tile)
                    if not content:
                        continue
                    pad = " ".join(x for x, f in (("pt", "OjCsFc"), ("pb", "wHaque")) if f in flags)
                    tiles_html.append(f'<div class="tile {pad}">{content}</div>'.replace('tile ">', 'tile">'))
                body = "".join(tiles_html)
                cols.append(f'<div class="col{" empty" if not body else ""}" style="--span:{span}">{body}</div>')
            rows.append(f'<div class="row">{"".join(cols)}</div>')
        return f'<section class="sec {kind} {tone}">{"".join(rows)}</section>'

    def build(self):
        _, raw = fetch(GS_BASE + self.gs_path)
        text = raw.decode("utf-8")
        backup = os.path.join(ROOT, "_google-sites-backup", "html",
                              (self.out_path or "home").replace("/", "__") + ".html")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        open(backup, "w", encoding="utf-8").write(text)
        soup = BeautifulSoup(text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else SITE_NAME
        sections = soup.select("div.UtePc section.yaqOZd") or soup.select("section.yaqOZd")
        body = "\n".join(self.section_html(s) for s in sections)
        return title, body, soup


# ---------------------------------------------------------------- page template

CHEVRON = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">'
           '<path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" fill="currentColor"/></svg>')


def nav_html(items, current):
    out = []
    for label, href, kids in items:
        here = current == href
        inside = here or (href != "/" and current.startswith(href))
        a_cls = ' class="current"' if here else ""
        li_cls = " active" if inside else ""
        if kids:
            out.append(f'<li class="has-sub{li_cls}"><div class="item"><a href="{href}"{a_cls}>{label}</a>'
                       f'<button class="toggle" aria-label="Show {label} pages" aria-expanded="false">{CHEVRON}</button></div>'
                       f'<ul class="sub">{nav_html(kids, current)}</ul></li>')
        else:
            out.append(f'<li class="{li_cls.strip()}"><div class="item"><a href="{href}"{a_cls}>{label}</a></div></li>'
                       .replace(' class=""', ""))
    return "".join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
{og_image}<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Playfair+Display:wght@400;700;900&display=swap">
<link rel="stylesheet" href="/assets/css/style.css">
</head>
<body>
<header class="topbar">
  <button class="menu-btn" aria-label="Open navigation" aria-expanded="false"><svg viewBox="0 0 24 24" width="24" height="24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" fill="currentColor"/></svg></button>
  <a class="brand" href="/"><img src="{logo}" alt=""><span>{site}</span></a>
  <nav class="main-nav" aria-label="Main"><ul>{nav}</ul></nav>
  <button class="search-btn" aria-label="Search this site"><svg viewBox="0 0 24 24" width="24" height="24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor"/></svg></button>
</header>
<div class="drawer-backdrop"></div>
<nav class="drawer" aria-label="Mobile">
  <a class="drawer-brand" href="/">{site}</a>
  <ul>{nav}</ul>
</nav>
<div class="search-panel" role="dialog" aria-label="Search" hidden>
  <div class="search-bar"><input type="search" placeholder="Search this site" aria-label="Search this site"><button class="search-close" aria-label="Close search">&times;</button></div>
  <ol class="search-results"></ol>
</div>
<main>
{body}
</main>
<script src="/assets/js/main.js"></script>
</body>
</html>
"""


def write_page(out_path, title, body, description, logo, favicon, og_image=""):
    current = "/" if not out_path else f"/{out_path}/"
    page = TEMPLATE.format(
        title=html.escape(title), description=html.escape(description[:200]),
        canonical=DOMAIN + current, nav=nav_html(NAV, current), body=body, site=SITE_NAME,
        logo=logo, favicon=favicon,
        og_image=f'<meta property="og:image" content="{DOMAIN}{og_image}">\n' if og_image else "")
    path = os.path.join(ROOT, *(out_path.split("/") if out_path else []), "index.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)


def write_file(rel, text):
    path = os.path.join(ROOT, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_hosting_files(logo, favicon):
    """CNAME, 404 page, /home redirect, sitemap and robots.txt for GitHub Pages."""
    write_file("CNAME", DOMAIN.split("//", 1)[1] + "\n")
    body404 = ('<section class="sec title white notfound"><div class="row"><div class="col" style="--span:8">'
               '<div class="tile pt pb"><div class="text"><h1>Page not found</h1></div></div></div></div></section>'
               '<section class="sec band grey notfound"><div class="row"><div class="col" style="--span:8">'
               '<div class="tile pt pb"><div class="text"><p>The page you are looking for does not exist or has moved.</p>'
               '</div></div><div class="tile pb"><div class="btn-wrap" style="text-align:center">'
               '<a class="btn" href="/">Go to the home page</a></div></div></div></div></section>')
    page = TEMPLATE.format(title=f"{SITE_NAME} - Page not found", description="Page not found",
                           canonical=DOMAIN + "/404.html", nav=nav_html(NAV, "/404/"), body=body404,
                           site=SITE_NAME, logo=logo, favicon=favicon, og_image="")
    write_file("404.html", page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex">'))
    # Old Google Sites address sidhvin.com/home -> /
    write_file("home/index.html", '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
               '<title>Sidhvin</title><link rel="canonical" href="https://sidhvin.com/">'
               '<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url=/">'
               '<script>location.replace("/" + location.hash)</script></head>'
               '<body><a href="/">Continue to sidhvin.com</a></body></html>\n')
    today = time.strftime("%Y-%m-%d")
    urls = "".join(f"  <url><loc>{DOMAIN}{'/' if not o else '/' + o + '/'}</loc><lastmod>{today}</lastmod></url>\n"
                   for _, o, _ in PAGES)
    write_file("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    write_file("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")


def main():
    search_index = []
    logo = favicon = None
    for gs_path, out_path, label in PAGES:
        print("page:", gs_path, flush=True)
        pb = PageBuilder(gs_path, out_path, label)
        title, body, soup = pb.build()
        if logo is None:
            limg = soup.select_one("img.r9CsCb") or soup.select_one("header img")
            logo = save_asset(html.unescape(limg["src"]), "images/site", "logo") if limg else ""
            ico = soup.find("link", rel=lambda r: r and "icon" in r)
            favicon = save_asset(html.unescape(ico["href"]), "images/site", "favicon") \
                if ico and ico.get("href") else None
            favicon = favicon or logo
        text = re.sub(r"\s+", " ", " ".join(pb.text_chunks)).strip()
        first_img = re.search(r'(?:src="|url\(\')(/assets/images/[^"\']+)', body)
        write_page(out_path, title, body, text or title, logo, favicon,
                   first_img.group(1) if first_img else logo)
        search_index.append({"title": label, "url": "/" if not out_path else f"/{out_path}/",
                             "text": text[:6000]})
    write_hosting_files(logo, favicon)
    os.makedirs(os.path.join(ROOT, "assets", "data"), exist_ok=True)
    with open(os.path.join(ROOT, "assets", "data", "search-index.json"), "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "_google-sites-backup", "asset-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(asset_log, f, indent=1)
    print(f"\n{len(asset_log)} files downloaded, {sum(a['bytes'] for a in asset_log) / 1e6:.1f} MB")
    for w in warnings:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
