# scrape_bilibili_anime.py
import asyncio, json, re
from playwright.async_api import async_playwright

def normalize_url(u: str | None) -> str | None:
    if not u: return None
    if u.startswith("//"): return "https:" + u
    if u.startswith("/"):  return "https://www.bilibili.com" + u
    return u

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 1200},
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        )
        page = await ctx.new_page()
        # Reduce bandwidth: block fonts/css
        await ctx.route("**/*", lambda route: route.abort() if route.request.resource_type in ("font","stylesheet") else route.continue_())
        await page.goto("https://www.bilibili.com/anime/", wait_until="domcontentloaded", timeout=60000)

        async def network_quiet(ms=800, timeout=8000):
            # crude quiet wait
            await page.wait_for_timeout(ms)

        # scroll loop
        last = 0; stable = 0
        for _ in range(20):
            await page.mouse.wheel(0, 1000)
            await network_quiet()
            count = await page.locator(".hot-ranking-cell-wrapper").count()
            if count == last: stable += 1
            else: stable = 0
            last = count
            if stable >= 2: break

        cards = page.locator(".hot-ranking-cell-wrapper")
        n = await cards.count()
        out = []
        for i in range(n):
            card = cards.nth(i)
            # cover via picture > source (avif/webp) fallback to img
            url = await card.locator(".season-cover-img picture source[type='image/avif']").first.get_attribute("srcset")
            if not url:
                url = await card.locator(".season-cover-img picture source[type='image/webp']").first.get_attribute("srcset")
            if url:
                url = url.split(",")[0].strip().split(" ")[0]
            if not url:
                url = await card.locator(".season-cover-img img").first.get_attribute("src")
            url = normalize_url(url)

            title = (await card.locator(".home-cell-desc-title").inner_text()).strip() if await card.locator(".home-cell-desc-title").count() else None
            subtitle = (await card.locator(".home-cell-desc-subtitle").inner_text()).strip() if await card.locator(".home-cell-desc-subtitle").count() else None
            rating = (await card.locator(".season-cover-score").inner_text()).strip() if await card.locator(".season-cover-score").count() else None

            href = await card.locator("a.season-cover").first.get_attribute("href")
            href = normalize_url(href)

            out.append({
                "rank": i+1, "title": title, "subtitle": subtitle,
                "rating": rating, "cover": url, "href": href
            })

        print(json.dumps([x for x in out if x["title"] or x["cover"]], ensure_ascii=False, indent=2))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
