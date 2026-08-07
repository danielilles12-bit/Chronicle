const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const { pathToFileURL } = require("url");

const root = path.resolve(__dirname, "..");
const source = path.resolve(__dirname, "launch-assets.html");
const assets = [
  ["story-01", "story/01-i-made-a-thing.png", 1080, 1920],
  ["story-02", "story/02-four-daily-games.png", 1080, 1920],
  ["story-03", "story/03-new-at-midnight.png", 1080, 1920],
  ["story-04", "story/04-why-i-made-it.png", 1080, 1920],
  ["story-05", "story/05-play-today.png", 1080, 1920],
  ["feed-01", "feed/01-yesternerd-is-live.png", 1080, 1440],
  ["feed-02", "feed/02-the-four-games.png", 1080, 1440],
  ["feed-03", "feed/03-new-every-midnight.png", 1080, 1440],
  ["feed-04", "feed/04-why-i-made-it.png", 1080, 1440],
  ["feed-05", "feed/05-play-today.png", 1080, 1440],
  ["reel-cover", "reel-cover.png", 1080, 1680],
];

(async () => {
  const systemChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const browser = await chromium.launch({
    headless: true,
    ...(fs.existsSync(systemChrome) ? { executablePath: systemChrome } : {}),
  });
  try {
    for (const [id, relativeOut, width, height] of assets) {
      const out = path.join(root, relativeOut);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
      const url = `${pathToFileURL(source).href}?asset=${encodeURIComponent(id)}`;
      await page.goto(url, { waitUntil: "load" });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(Array.from(document.images).map(img => img.complete ? null : new Promise(resolve => {
          img.addEventListener("load", resolve, { once: true });
          img.addEventListener("error", resolve, { once: true });
        })));
      });
      await page.screenshot({ path: out, type: "png" });
      await page.close();
      process.stdout.write(`${relativeOut}\n`);
    }
  } finally {
    await browser.close();
  }
})();
