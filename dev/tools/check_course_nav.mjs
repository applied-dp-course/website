import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.join(__dirname, "../../_site");
const port = 9876;
const base = `http://127.0.0.1:${port}`;

async function checkPage(page, url, label) {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("a.course-nav-main", { timeout: 5000 });
  const href = await page.locator("a.course-nav-main").getAttribute("href");
  if (!href || !href.includes("course.html")) {
    throw new Error(`${label}: course link href missing or wrong: ${href}`);
  }
  await page.locator("button.course-nav-caret, a.course-nav-caret").click();
  await page.waitForSelector("ul.dropdown-menu.show", { timeout: 3000 });
  const count = await page.locator("ul.dropdown-menu.show a.dropdown-item").count();
  if (count < 5) {
    throw new Error(`${label}: expected 5 dropdown items, got ${count}`);
  }
  console.log(`OK ${label}: href=${href}, dropdownItems=${count}`);
}

const server = spawn("python3", ["-m", "http.server", String(port)], {
  cwd: siteRoot,
  stdio: "ignore",
});
await new Promise((r) => setTimeout(r, 500));

try {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  try {
    await checkPage(page, `${base}/pages/index.html`, "index");
    await checkPage(page, `${base}/pages/course.html`, "course");
    await checkPage(
      page,
      `${base}/content/blog-posts/privacy-auditing/post.html`,
      "blog-post",
    );
    await page.locator("a.course-nav-main").click();
    await page.waitForURL(/course\.html$/);
    console.log("OK course link navigation:", page.url());
  } finally {
    await browser.close();
  }
} catch (err) {
  console.error("FAIL:", err.message);
  process.exitCode = 1;
} finally {
  server.kill("SIGTERM");
}
