const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  await page.goto('file:///C:/Users/sabum/sabsys/tmp/po_compare_fields.html', { waitUntil: 'networkidle' });

  async function inspect(label, selector) {
    await page.locator(selector).click();
    await page.waitForTimeout(250);
    return await page.locator(selector).evaluate((el, label) => {
      const s = getComputedStyle(el);
      return {
        label,
        tag: el.tagName,
        className: el.className,
        borderColor: s.borderColor,
        borderWidth: s.borderWidth,
        borderRadius: s.borderRadius,
        boxShadow: s.boxShadow,
        outline: s.outline,
        height: s.height,
        padding: s.padding,
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        backgroundColor: s.backgroundColor,
        appearance: s.appearance,
      };
    }, label);
  }

  const notes = await inspect('Notas', '#id_notes');
  const qtySelector = 'input[name$="-quantity"]';
  const qty = await inspect('Cantidad', qtySelector);
  console.log(JSON.stringify({ notes, qty }, null, 2));
  await browser.close();
})();
