# sidhvin.com migration: Google Sites to GitHub Pages

Record of the migration carried out on 1 November 2026. It covers what was found, what was built, what was changed on GitHub and at GoDaddy, how it was tested, and what is still open.

## Summary

| | Before | After |
| --- | --- | --- |
| Hosting | Google Sites, `sites.google.com/view/sidhvin` | GitHub Pages, repository [sidhvin/sidhvin.com](https://github.com/sidhvin/sidhvin.com), public |
| Bare domain `sidhvin.com` | GoDaddy domain forwarding (301 redirect) to Google Sites | A/AAAA records pointing at GitHub Pages |
| `www.sidhvin.com` | CNAME to `ghs.googlehosted.com` | CNAME to `sidhvin.github.io`, redirected by GitHub to `sidhvin.com` |
| Assets | Stored by Google, behind signed URLs that expire | Stored in the repository under `assets/` |
| Cost | Free | Free, because the repository is public |

Status when this was written (21:38 WEST, 1 Nov 2026):

- **DNS records:** correct at GoDaddy and on most public resolvers.
- **GitHub's DNS check:** failing, because some resolver caches still hold the old forwarding addresses. They should expire by about 22:33.
- **Website:** GitHub already serves it for `sidhvin.com`, and `www` redirects correctly.
- **HTTPS:** not available until GitHub issues the certificate, which follows a successful DNS check.

---

## 1. Investigation of the original site

### Pages

The Google Site had 12 pages. The new site keeps every address.

| Google Sites path | New URL |
| --- | --- |
| `/home` | `/`, with `/home/` redirecting to it |
| `/work-experience` | `/work-experience/` |
| `/projects` | `/projects/` |
| `/projects/yaskawa-hc10` | `/projects/yaskawa-hc10/` |
| `/projects/kth-hk-project` | `/projects/kth-hk-project/` |
| `/projects/aircrafts` | `/projects/aircrafts/` |
| `/projects/aircrafts/fixed-wings` | `/projects/aircrafts/fixed-wings/` |
| `/projects/aircrafts/quadcopters` | `/projects/aircrafts/quadcopters/` |
| `/projects/automobiles` | `/projects/automobiles/` |
| `/projects/cnc-machine` | `/projects/cnc-machine/` |
| `/projects/balance-bike` | `/projects/balance-bike/` |
| `/projects/lit-bike` | `/projects/lit-bike/` |

GitHub Pages redirects addresses without a trailing slash, such as `/projects/cnc-machine`, to the version with one, so old links keep working.

### Theme and layout

The site used Google's "Impression" theme. Values were taken from the page's theme CSS and Google's base stylesheet:

- **Fonts:** Playfair Display for headings and the site name. Open Sans for body text at 12pt with line height 1.75.
- **Headings:**
  - Page title header: 40pt bold, on a white section with a minimum height of 200px.
  - Heading 1: 29pt. Heading 2: 20pt. Heading 3: Open Sans 13pt semi-bold.
  - Small captions: Playfair 9pt.
- **Section styles:** white, grey `#929292`, light grey `#f4f4f4`, and thin divider sections.
- **Grid:** 12 columns. Rows are at most 1280px wide with 48px side padding. Column gutters are 1.25% of the row width. Tiles have optional 1.5rem top and bottom padding.
- **Top bar:** transparent, with the logo, "Sidhvin", Home, Work experience, a Projects dropdown with Aircrafts nested inside it, and a search button. The dropdown and mobile drawer are dark `#1b1b1b`.
- **Content types:**
  - Text boxes, images (some linked), outlined buttons and dividers.
  - Image carousels with autoplay, dots and captions.
  - YouTube embeds and Google Drive embeds.
  - A custom embed of a Unity robot simulation on the Yaskawa page, from `i.simmer.io`.

### Findings that shaped the approach

- **Google image URLs expire.** Images use signed URLs that change on every page load and return 403 later. The importer therefore fetches each page and its images in the same run. Adding `=s0` to an image URL returns the original full-resolution file.
- **Drive files:**

  | File | Page | State |
  | --- | --- | --- |
  | Lit Bike Project.pdf | lit Bike | Public. Downloaded. |
  | CV, linked from the "View CV" button | Home | **Returns 404 on the live site.** The file no longer exists. |
  | Technical Drawing.pdf | Balance Bike | **Private.** Visitors see a Google sign-in page. |
  | Gear profile.mp4 | CNC Machine | **Private.** |
  | Letter cutting S.mp4 | CNC Machine | **Private.** |

- **"Call me" button.** "Call me : +46-79-333-80-62" links to `http://sidhvin.me`, not to a phone number. It was kept as it was.
- **DNS before the migration.** Nameservers were `ns09/ns10.domaincontrol.com`, which is GoDaddy.

  | Record | Value |
  | --- | --- |
  | `sidhvin.com` A | 15.197.225.128, 3.33.251.168, the GoDaddy forwarding service. TTL 1 hour. |
  | `www` CNAME | `ghs.googlehosted.com` |
  | TXT | `google-site-verification=dtTbhykK0SIbMWVRfWOwEpkXIlIoK0uwij1cS2SJvu4` |
  | MX | none. Email was not affected. |

---

## 2. What was built

Project folder: `C:\Users\sidhv\sidhvin.com`, kept outside OneDrive so git and OneDrive sync can't conflict.

### 2.1 Importer: `_tools/import_google_site.py`

A Python script that rebuilds the whole site from the live Google Site. It needs `beautifulsoup4` and `pillow`, which were installed with `pip install --user`.

**Steps for each page:**

1. Downloads the page and saves the raw HTML to `_google-sites-backup/html/`.
2. Walks Google's layout: sections, then rows, then columns, then tiles. It maps Google's column classes to grid widths, for example `uQSCkd` to 12, `ibL1re` to 2 and `OiUrBf` to 8.
3. Converts each tile to clean HTML:
   - **Text:** keeps inline formatting such as colour, bold and alignment, plus links and heading anchors. Removes Google's scripts and classes.
   - **Images:** downloads them, keeps any link, and writes alt text.
   - **Carousels:** downloads every slide with its caption and keeps the autoplay speed, dots and caption settings.
   - **Buttons and dividers:** converted to plain equivalents.
   - **YouTube:** clean `youtube.com/embed/<id>` iframes at the original aspect ratio.
   - **Drive files:** downloaded and embedded locally when public. Otherwise kept as a Drive preview, which is how they behaved on Google Sites.
   - **The custom robot embed:** a responsive iframe to `i.simmer.io/@sidhvin/yaskawajog`.
4. Rewrites links: Google's `google.com/url?q=` redirect wrappers are removed, and `/view/sidhvin/...` becomes `/...`.

**Assets:**

- Identical files are stored once, using a SHA-1 hash.
- File types are detected from the file's bytes. This is needed because Drive sends PDFs as `application/octet-stream`.
- Full-resolution originals go to `_google-sites-backup/original-images/<page>/`.
- Published copies go to `assets/images/<page>/`, resized to at most 2000px wide. Photos are saved as JPEG at quality 85 and graphics as optimised PNG.
- Names follow page order and content, such as `09-carousel-fully-built-machine.jpg`, `04-thumb-scania.png` and `thumb-<project>` for project tiles.
- If a private Drive file is placed by hand in `assets/documents/` or `assets/videos/` under the expected name, the importer embeds that local copy instead.

**Generated files:**

- Every `index.html` page.
- `assets/data/search-index.json`, the text of each page for site search.
- `404.html`, the `/home/` redirect, `sitemap.xml`, `robots.txt` and `CNAME`.
- `_google-sites-backup/asset-manifest.json`, listing each file's source URL and its original and published sizes.

**Result of the final run:** 57 asset files.

| Measure | Value |
| --- | --- |
| Published assets | 12.8 MB |
| Full-resolution originals | 43 MB |
| Drive files that could not be downloaded | 3, all private |

**Bug found and fixed during development:** Google puts a hidden "Copy heading link" button inside every heading. At first these were converted into visible buttons. The importer now strips them before classifying a tile.

### 2.2 Theme: `assets/css/style.css`

A hand-written recreation of the Impression theme using the values in section 1:

- Grid, section colours, fonts, buttons, dividers, embeds and carousels.
- The top bar is transparent at the top of the page and turns white with a shadow on scroll.
- The first section gets extra top padding under the bar, as Google Sites does.
- Dark dropdown menus and a dark slide-in drawer on mobile.
- Below 768px, columns stack, empty spacer columns hide, and headings shrink using Google's mobile sizes.
- Animations are turned off when the visitor's system asks for reduced motion.

### 2.3 Behaviour: `assets/js/main.js`

Plain JavaScript with no libraries:

- **Top bar:** changes style on scroll.
- **Menus:** dropdowns and nested submenus. Escape or a click elsewhere closes them.
- **Mobile drawer:** a hamburger menu that opens the current page's branch automatically.
- **Carousels:** autoplay at each carousel's own interval and pause on hover. They have previous and next buttons, clickable dots, captions, left and right arrow keys, and swipe on touch screens.
- **Search:** opens an overlay, loads the search index on first use, and ranks pages with title matches first. Results show highlighted snippets, and Enter opens the first result.

### 2.4 Page template

Every page shares the same header, mobile drawer, search panel and footer script. Each page also gets:

- A title.
- A meta description taken from its text.
- A canonical URL on `https://sidhvin.com`.
- Open Graph tags, using the page's first image for link previews.
- The favicon.

### 2.5 Hosting files

| File | Purpose |
| --- | --- |
| `CNAME` | `sidhvin.com`. Tells GitHub Pages which custom domain to serve. |
| `404.html` | "Page not found" page in the site theme. Marked noindex. |
| `home/index.html` | Redirects the old `/home` address to `/`, keeping any `#anchor`. |
| `sitemap.xml`, `robots.txt` | For search engines. |
| `_config.yml` | Stops Jekyll from publishing `README.md` and `.gitignore`. |
| `.gitignore` | Python caches and OS clutter. |
| `README.md` | Folder layout, local preview, editing, known issues, and the full GitHub and GoDaddy steps. |

GitHub Pages runs Jekyll, which never publishes folders that start with `_`. The `_tools/`, `_google-sites-backup/` and `_docs/` folders are therefore kept privately in the repository but are not part of the website.

### 2.6 Final folder layout

```
sidhvin.com/
├── index.html, 404.html, CNAME, robots.txt, sitemap.xml
├── README.md, _config.yml, .gitignore
├── home/                      redirect for old /home links
├── work-experience/
├── projects/                  one folder per project, incl. aircrafts/fixed-wings and aircrafts/quadcopters
├── assets/
│   ├── css/style.css
│   ├── js/main.js
│   ├── data/search-index.json
│   ├── documents/lit-bike-project.pdf
│   └── images/
│       ├── site/              logo.png, favicon.png
│       ├── home/
│       ├── work-experience/
│       └── projects/<project>/
├── _google-sites-backup/      original HTML, original-images/, asset-manifest.json
├── _tools/import_google_site.py
└── _docs/MIGRATION.md         this file
```

---

## 3. Testing

- **Local preview.** The site was served with `python -m http.server` and screenshotted with headless Microsoft Edge at 1400px wide. Screenshots of Home, Projects, CNC Machine and Work experience were compared with screenshots of the live Google Site. The layout, colours, fonts, image grid, carousels and buttons matched closely.
- **Mobile.** Screenshots were taken at 600px wide. Columns stack and the hamburger menu replaces the top navigation. A 390px screenshot looked cut off, but that was a headless-browser minimum window width, not a page problem.
- **Link check.** A script checked all 14 HTML pages. All 474 internal links and asset references resolve, and no Google-hosted image URLs remain.
- **Behaviour test.** A temporary test page, deleted afterwards, was run in Edge:
  - The carousel built 7 dots for 7 slides, and "next" moved to slide 2 with the caption "Front View".
  - The Projects dropdown opened.
  - The mobile drawer opened.
  - A search for "quadcopter" returned 2 results, with "Quadcopters" first.
- **Fix from testing.** The browser's own clear button in the search box sat next to the site's close button. It is now hidden.

---

## 4. Git and GitHub

1. **Local repository.** Created with `git init -b main`. The first commit is "Migrate sidhvin.com from Google Sites to a static GitHub Pages site" (`ded63e6`).
2. **GitHub repository.** You created `github.com/sidhvin/sidhvin.com` as a **public** repository. A private repository needs a paid GitHub plan to use Pages, so public was chosen to keep hosting free.
3. **First push rejected.** GitHub had created the repository with its own `README.md` ("# sidhvin.com / My website", commit `571b578`), so the push failed with "fetch first". The fix:
   - Fetched the remote branch.
   - Merged it with `--allow-unrelated-histories`.
   - Resolved the README conflict by keeping the full local README. The merge commit is `c75b8b8`.
   - Pushed again, which succeeded. Nothing on GitHub was overwritten.
4. **GitHub Pages.** You turned on Pages from branch `main`, folder `/ (root)`, with the custom domain `sidhvin.com`. GitHub now serves the site for `sidhvin.com`. This was confirmed with requests sent straight to GitHub's server: the home page and project pages return 200, and `www.sidhvin.com` returns a 301 to `sidhvin.com`.

---

## 5. DNS changes at GoDaddy

1. **Zone file.** A zone file with the GitHub Pages records was written for GoDaddy's "Import Zone File". The first version, `sidhvin.com.zone`, was rejected with "Invalid media type; Must be text file or compressed text file" because of its extension. It was replaced by `C:\Users\sidhv\Downloads\sidhvin.com.txt`, with the same records and no comments:

   ```
   $ORIGIN sidhvin.com.
   $TTL 600
   @    600 IN A     185.199.108.153
   @    600 IN A     185.199.109.153
   @    600 IN A     185.199.110.153
   @    600 IN A     185.199.111.153
   @    600 IN AAAA  2606:50c0:8000::153
   @    600 IN AAAA  2606:50c0:8001::153
   @    600 IN AAAA  2606:50c0:8002::153
   @    600 IN AAAA  2606:50c0:8003::153
   www  600 IN CNAME sidhvin.github.io.
   ```

2. **Records in place.** The records were imported, and domain forwarding was removed. The two old forwarding A records were no longer visible in GoDaddy. Checks against GoDaddy's own nameservers confirmed they are gone.
3. **Verified state at 21:38 WEST:**
   - `ns09` and `ns10.domaincontrol.com`, Cloudflare `1.1.1.1`, Quad9 `9.9.9.9` and Google `8.8.8.8` all return only the four GitHub A records for `sidhvin.com`.
   - The AAAA records and the `www` CNAME to `sidhvin.github.io` are correct.
   - No CAA record restricts certificate issuers, so GitHub's Let's Encrypt certificate is allowed.
4. **Why GitHub's "DNS check unsuccessful" appeared.** Some Google DNS caches still returned the old forwarding addresses 15.197.225.128 and 3.33.251.168, with about 53 minutes left on their one-hour TTL. GitHub's checker probably received one of those cached answers. This computer also had the old address cached, so opening sidhvin.com locally still showed a 404 from the old forwarding server.
5. **Removed today, not re-added.** The `google-site-verification` TXT record was no longer present when the zone was checked. Re-add it only if Google Search Console is still used.

---

## 6. Next steps

1. **After about 22:35 on 1 Nov 2026,** open the repository's Settings, then Pages, and click "Check again".
   - If the check still fails, remove `sidhvin.com` from Custom domain, save, then add it back and save. This deletes and re-creates the `CNAME` file on GitHub.
   - Afterwards, run `git pull` locally.
2. **Turn on HTTPS.** Once the check passes and GitHub has issued the certificate, which can take up to an hour, tick **Enforce HTTPS**.
3. **Clear the local DNS cache** to see the new site on this computer, then restart the browser:
   ```
   ipconfig /flushdns
   ```
4. **Check that the site is live:**
   - `https://sidhvin.com` loads the new site.
   - `https://www.sidhvin.com` redirects to `https://sidhvin.com`.
   - `nslookup sidhvin.com` returns the four `185.199.x.153` addresses.
5. **Retire the Google Site.** In Google Sites, open Settings, then Custom domains, and remove the old `www.sidhvin.com` mapping. Keep the Google Site and its Drive files until everything above is confirmed.
6. **Optional:** verify the domain on GitHub to stop anyone else using it with GitHub Pages:
   - On GitHub, go to your profile Settings, then Pages, then Add a domain.
   - Add the `_github-pages-challenge-sidhvin` TXT record it shows in GoDaddy.

## 7. Content issues carried over from the Google Site

| Issue | Fix |
| --- | --- |
| "View CV" points to a deleted Drive file and returns 404 | Save a CV as `assets/documents/cv.pdf` and change the button link in `index.html` to `/assets/documents/cv.pdf` |
| Technical Drawing.pdf, Gear profile.mp4 and Letter cutting S.mp4 are private | Download them from Drive to `assets/documents/technical-drawing.pdf`, `assets/videos/gear-profile.mp4` and `assets/videos/letter-cutting-s.mp4`. Then re-run the importer or edit the iframes by hand. |
| "Call me" links to `http://sidhvin.me` | Change the link to `tel:+46793338062` if it should start a call |

## 8. Maintaining the site

- **Preview:** run `python -m http.server 8000` in the project folder and open `http://localhost:8000`.
- **Edit:** change the HTML in each page's `index.html`. Put new images in `assets/images/<page>/`.
- **Publish:** run `git add -A`, `git commit -m "..."` and `git push`. GitHub Pages republishes within a minute or two.
- **Re-import:** `python _tools/import_google_site.py` rebuilds everything from the Google Site while it still exists. It overwrites any manual edits to the pages, so stop using it once you start editing the HTML directly.
