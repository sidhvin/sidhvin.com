# sidhvin.com

Personal website of Sidhvin Dulevale Matadha. This repository is a static copy of the Google Site that used to live at `sites.google.com/view/sidhvin`. It keeps the same look, page addresses and navigation, and is hosted for free on GitHub Pages at <https://sidhvin.com>.

## Folder layout

| Path | What it holds |
| --- | --- |
| `index.html` | Home page |
| `work-experience/`, `projects/...` | One folder per page, each with an `index.html`. The URLs are the same as on the Google Site. |
| `assets/css/style.css` | All styling, a recreation of the Google Sites "Impression" theme |
| `assets/js/main.js` | Menus, mobile drawer, image carousels and site search |
| `assets/data/search-index.json` | Text of every page, used by the search box |
| `assets/images/site/` | Logo and favicon |
| `assets/images/<page>/` | Images for each page, numbered in the order they appear and sized for the web, at most 2000px wide |
| `assets/documents/` | PDFs shown on the site |
| `404.html` | "Page not found" page |
| `home/` | Redirects the old `sidhvin.com/home` address to `/` |
| `CNAME` | Tells GitHub Pages to serve the site at `sidhvin.com` |
| `sitemap.xml`, `robots.txt` | For search engines |
| `_google-sites-backup/` | The original Google Sites HTML, the full-resolution original images, and `asset-manifest.json` listing where every file came from. Not published. |
| `_tools/import_google_site.py` | The script that built this site from the Google Site. Not published. |

GitHub Pages runs Jekyll, which skips folders that start with `_`. The backup and tools are therefore stored in git but never appear on the public website.

## Preview locally

```
cd C:\Users\sidhv\sidhvin.com
python -m http.server 8000
```

Then open <http://localhost:8000>. Opening the HTML files directly by double-clicking will not work, because links start at the site root.

## Editing the site

- **Text:** edit the page's `index.html` and look for the paragraph inside `<main>`.
- **Images:** put the file in `assets/images/<page>/` and reference it as `/assets/images/<page>/<file>`.
- **Menu:** the menu is repeated in every page's `<header>` and drawer. If you add a page, copy an existing page folder and add the new link to every page's menu. Also add the page to `sitemap.xml` and `assets/data/search-index.json`.
- **Publish:** commit and push. GitHub Pages republishes automatically within a minute or two.

```
git add -A
git commit -m "Describe the change"
git push
```

### Re-importing from Google Sites (optional)

While the Google Site still exists, `python _tools/import_google_site.py` re-downloads everything and regenerates all pages. It needs `pip install beautifulsoup4 pillow`. It overwrites any manual edits to the generated pages, so stop using it once you start editing here.

## Known content issues carried over from the Google Site

- **The "View CV" button** points to a Google Drive file that no longer exists and returns a 404. Upload a new CV to `assets/documents/cv.pdf` and change the button link in `index.html` to `/assets/documents/cv.pdf`.
- **Three Drive files are private,** so visitors see a Google sign-in or cookie screen instead of them:
  - "Technical Drawing.pdf" on the Balance Bike page.
  - "Gear profile.mp4" and "Letter cutting S.mp4" on the CNC Machine page.

  To fix this, download them from your Drive into `assets/documents/technical-drawing.pdf`, `assets/videos/gear-profile.mp4` and `assets/videos/letter-cutting-s.mp4`. Then re-run the import script, which uses the local copies automatically, or replace the iframes by hand.
- **The "Call me" button** links to `http://sidhvin.me`. Change it to `tel:+46793338062` if it should start a phone call.

## Publishing on GitHub Pages with the sidhvin.com domain

### 1. Create the repository

1. Sign in at <https://github.com> and click **New repository**.
2. Name it `sidhvin.com`, set it to **Public**, and do **not** add a README, .gitignore or licence. Public repositories get GitHub Pages for free.
3. Push this folder. Replace `<username>` with your GitHub username:

```
cd C:\Users\sidhv\sidhvin.com
git remote add origin https://github.com/<username>/sidhvin.com.git
git push -u origin main
```

The first push opens a browser window to sign in to GitHub.

### 2. Turn on GitHub Pages

1. In the repository, open **Settings**, then **Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**. Set the branch to **main** and the folder to **/ (root)**, then click **Save**.
3. Under **Custom domain**, enter `sidhvin.com` and click **Save**. It is usually pre-filled from the `CNAME` file. GitHub will show a DNS warning until step 3 below is done.
4. Wait a minute, then check that the site works at `https://<username>.github.io/sidhvin.com/`. Once the custom domain is set, that address redirects to sidhvin.com.

### 3. Point the domain at GitHub (GoDaddy)

The domain is managed at GoDaddy, whose nameservers are `ns09/ns10.domaincontrol.com`. Today the bare domain uses GoDaddy forwarding to Google Sites, and `www` points at `ghs.googlehosted.com`.

1. **Optional but recommended, before changing DNS:** verify the domain on GitHub. Go to your profile **Settings**, then **Pages**, then **Add a domain**, and enter `sidhvin.com`. GitHub shows a TXT record named `_github-pages-challenge-<username>`. Add it in GoDaddy and click **Verify**. This stops anyone else from claiming your domain on GitHub.
2. In GoDaddy, open **My Products**, then **sidhvin.com**, then **DNS**.
3. **Forwarding tab:** delete the domain forwarding to `sites.google.com/view/sidhvin/home`.
4. **DNS Records tab:**
   - Delete the existing `A` record(s) for `@`, which are the GoDaddy forwarding IPs 15.197.225.128 and 3.33.251.168.
   - Add four `A` records with name `@` and these values: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - Optionally add four `AAAA` records with name `@` for IPv6: `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`.
   - Edit the `CNAME` record named `www` and change its value from `ghs.googlehosted.com` to `<username>.github.io`.
   - Keep the existing `google-site-verification` TXT record. It is harmless and keeps Google Search Console working.
5. Wait for DNS to update. It usually takes a few minutes, at most 24 to 48 hours. Check with:

```
nslookup sidhvin.com
nslookup www.sidhvin.com
```

`sidhvin.com` should return the four `185.199.x.153` addresses, and `www` should be an alias of `<username>.github.io`.

### 4. Turn on HTTPS

Back in the repository, go to **Settings**, then **Pages**. When the DNS check turns green, GitHub issues a free certificate, which can take up to an hour. Then tick **Enforce HTTPS**. Visitors to `www.sidhvin.com` are redirected to `sidhvin.com` automatically.

### 5. Retire the Google Site

1. In Google Sites, open the site, then **Settings**, then **Custom domains**, and remove `www.sidhvin.com`.
2. Keep the Google Site, or at least its Drive files, until you have confirmed the new site works and moved any private Drive files.

Nothing in these steps affects email, because the domain has no MX records.
