const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  await page.goto('file:///C:/Users/sabum/sabsys/tmp/po_focus.html', { waitUntil: 'networkidle' });
  await page.locator('#id_notes').click();
  await page.waitForTimeout(350);
  const styles = await page.locator('#id_notes').evaluate((el) => {
    const s = getComputedStyle(el);
    return { borderColor: s.borderColor, boxShadow: s.boxShadow };
  });
  console.log(JSON.stringify(styles));
  await browser.close();
})();
