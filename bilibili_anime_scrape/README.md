# Puppeteer (Node.js)

**Run**

```bash
pnpm add puppeteer
node scrape_bilibili_anime.mjs > anime.json
```

---

# Playwright (Python)

**Run**

```bash
pip install playwright
playwright install chromium
python scrape_bilibili_anime.py > anime.json
```

---

## Notes on **rate-limits & dynamic loading**

* **Scrolling policy:** The scripts scroll in small increments and require **two stable cycles** (no new cards detected) before stopping. This reduces hammering their APIs.
* **Network quiet time:** After each scroll we wait \~0.8–1.1s; tweak up (e.g., 1500ms) if your IP is slow or if cards load late.
* **Blocking heavy assets:** Fonts/stylesheets are blocked to save bandwidth while keeping JS and images (covers) flowing.
* **User-Agent & viewport:** Set explicitly to a common desktop profile to avoid serving mobile markup.
* **Cap rounds:** Safety caps (20 rounds) prevent infinite scroll loops.
* **Backoff:** If you start seeing empty `srcset` or `null` titles, increase the wait, add random jitter, or introduce exponential backoff between scrolls.

---

## Selector cheatsheet (robust)

* Card: `.hot-ranking-cell-wrapper`
* Cover (container): `.season-cover-img picture`
* Title: `.home-cell-desc-title`
* Subtitle: `.home-cell-desc-subtitle`
* Rating: `.season-cover-score`
* Link: `a.season-cover[href]` (falls back to desc anchor if needed)

---

## Optional: run in browser console (quick & dirty)

Paste after you manually scroll the page to load enough items:

```js
(() => {
  const norm = s => (s || "").replace(/\s+/g, " ").trim();
  const pickSrc = pic => {
    const p = pic?.querySelector("source[type='image/avif']")?.getAttribute("srcset")
      || pic?.querySelector("source[type='image/webp']")?.getAttribute("srcset")
      || pic?.querySelector("img")?.getAttribute("src");
    let u = (p || "").split(",")[0].trim().split(" ")[0];
    if (!u) return null;
    if (u.startsWith("//")) u = "https:" + u;
    if (u.startsWith("/"))  u = location.origin + u;
    return u;
  };

  const cards = [...document.querySelectorAll(".hot-ranking-cell-wrapper")];
  return cards.map((c, i) => ({
    rank: i + 1,
    title: norm(c.querySelector(".home-cell-desc-title")?.textContent),
    subtitle: norm(c.querySelector(".home-cell-desc-subtitle")?.textContent),
    rating: norm(c.querySelector(".season-cover-score")?.textContent),
    cover: pickSrc(c.querySelector(".season-cover-img picture")),
    href: (() => {
      let h = c.querySelector("a.season-cover")?.getAttribute("href");
      if (!h) return null;
      if (h.startsWith("//")) h = "https:" + h;
      return h;
    })(),
  })).filter(r => r.title || r.cover);
})();
```
