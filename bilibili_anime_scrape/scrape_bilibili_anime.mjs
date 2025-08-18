// scrape_bilibili_anime.js
import puppeteer from "puppeteer";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Prefer the best cover URL from <picture>, else <img>, normalize protocol
function extractCoverURL(card) {
  const pic = card.querySelector(".season-cover-img picture");
  // Prefer AVIF/WebP source; fall back to <img>
  const pickFromSource = (type) => {
    const s = pic?.querySelector(`source[type="${type}"]`);
    if (!s) return null;
    const srcset = s.getAttribute("srcset") || "";
    const first = srcset.split(",")[0]?.trim().split(" ")[0];
    return first || null;
  };

  let url =
    pickFromSource("image/avif") ||
    pickFromSource("image/webp") ||
    pic?.querySelector("img")?.getAttribute("src") ||
    card.querySelector(".season-cover-img img")?.getAttribute("src") ||
    null;

  if (!url) return null;
  if (url.startsWith("//")) url = "https:" + url;
  if (url.startsWith("/")) url = "https://www.bilibili.com" + url;
  return url;
}

(async () => {
  // const browser = await puppeteer.launch({
  //   headless: true, // or "new"
  //   args: [
  //     "--no-sandbox",
  //     "--disable-setuid-sandbox",
  //     "--disable-dev-shm-usage",
  //   ],
  //   defaultViewport: { width: 1280, height: 1200 },
  // });

  const browser = await puppeteer.launch({
    executablePath: "/usr/bin/chromium", // or /usr/bin/google-chrome-stable
    headless: true,
  });
  const page = await browser.newPage();
  // Mildly realistic UA; reduces anti-bot friction
  await page.setUserAgent(
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " +
      "Chrome/120.0.0.0 Safari/537.36",
  );

  // Basic request hygiene: block heavy assets we don’t need
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    const type = req.resourceType();
    if (["stylesheet", "font"].includes(type)) return req.abort();
    return req.continue();
  });

  await page.goto("https://www.bilibili.com/anime/", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });

  // Helper to detect network idleness between scroll chunks
  async function waitForNetworkQuiet(ms = 1000, timeout = 15_000) {
    let idleResolve;
    let inflight = 0;
    let idleTimer;

    function resetIdle() {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => idleResolve(), ms);
    }

    const rq = (req) => {
      inflight++;
      resetIdle();
    };
    const rs = (res) => {
      inflight = Math.max(0, inflight - 1);
      resetIdle();
    };
    const rf = (err) => {
      inflight = Math.max(0, inflight - 1);
      resetIdle();
    };

    const p = new Promise((resolve, reject) => {
      idleResolve = resolve;
      setTimeout(() => resolve(), timeout); // hard cap
    });

    page.on("request", rq);
    page.on("requestfinished", rs);
    page.on("requestfailed", rf);

    // start the idle window now
    resetIdle();
    await p;

    page.off("request", rq);
    page.off("requestfinished", rs);
    page.off("requestfailed", rf);
  }

  // Scroll until no new cards for a few iterations or we hit a sane cap
  let lastCount = 0;
  let stableRounds = 0;
  const MAX_ROUNDS = 20; // safety
  const STABLE_TARGET = 2; // stop when count stops growing twice in a row
  for (let round = 0; round < MAX_ROUNDS; round++) {
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 1.2));
    await sleep(400 + Math.random() * 300); // polite throttle
    await waitForNetworkQuiet(800, 8000);

    const count = await page.$$eval(
      ".hot-ranking-cell-wrapper",
      (els) => els.length,
    );
    if (count === lastCount) stableRounds++;
    else stableRounds = 0;

    lastCount = count;
    if (stableRounds >= STABLE_TARGET) break;
  }

  // Extract data from each card
  const data = await page.$$eval(".hot-ranking-cell-wrapper", (cards) => {
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim();

    function extractCoverURL(card) {
      const pic = card.querySelector(".season-cover-img picture");
      const pickFromSource = (type) => {
        const s = pic?.querySelector(`source[type="${type}"]`);
        if (!s) return null;
        const srcset = s.getAttribute("srcset") || "";
        const first = srcset.split(",")[0]?.trim().split(" ")[0];
        return first || null;
      };
      let url =
        pickFromSource("image/avif") ||
        pickFromSource("image/webp") ||
        pic?.querySelector("img")?.getAttribute("src") ||
        card.querySelector(".season-cover-img img")?.getAttribute("src") ||
        null;

      if (!url) return null;
      if (url.startsWith("//")) url = "https:" + url;
      if (url.startsWith("/")) url = "https://www.bilibili.com" + url;
      return url;
    }

    return cards
      .map((card, idx) => {
        const cover = extractCoverURL(card);
        const titleEl = card.querySelector(".home-cell-desc-title");
        const subtitleEl = card.querySelector(".home-cell-desc-subtitle");
        const scoreEl = card.querySelector(".season-cover-score");
        const linkEl =
          card.querySelector("a.season-cover[href]") ||
          card.querySelector(".ranking-cell-desc a[href]");

        return {
          rank: idx + 1,
          title: norm(titleEl?.textContent),
          subtitle: norm(subtitleEl?.textContent),
          rating: norm(scoreEl?.textContent) || null, // e.g., "9.7" or null
          cover,
          href: linkEl
            ? linkEl.getAttribute("href")?.startsWith("//")
              ? "https:" + linkEl.getAttribute("href")
              : linkEl.getAttribute("href")
            : null,
        };
      })
      .filter((x) => x.title || x.cover);
  });

  console.log(JSON.stringify(data, null, 2));
  await browser.close();
})();
