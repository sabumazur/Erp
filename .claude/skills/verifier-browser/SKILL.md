---
name: verifier-browser
description: Use when verifying a frontend/UI change in this Django project by driving Chrome — confirms a feature works in the real running app, captures screenshots as evidence. Use before reporting any UI fix as complete.
---

# verifier-browser

Runtime browser verification for sabsys via Playwright + Chromium.

## Setup (one-time per session)

**1. Start server** (if not running):
```bash
python manage.py runserver 8000 > /tmp/django.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/   # expect 302
```

**2. Reset test password** (if needed):
```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
u = U.objects.get(email='sabumazur@gmail.com')
u.set_password('testpass123')
u.save()
print('ok')
" 2>/dev/null | grep -v "imported"
```

**3. Write and run scripts from the project root** (playwright is a local dep):
```bash
node my_test.js   # NOT: cd /tmp && node ...
```

## Login recipe

```js
await page.goto('http://localhost:8000/auth/login/');
await page.fill('[name="login"]', 'sabumazur@gmail.com');
await page.fill('[name="password"]', 'testpass123');
await page.click('[type="submit"]');
await page.waitForURL('**/', { timeout: 8000 });
```

- Login URL: `/auth/login/` (NOT `/accounts/login/`)
- Email field name: `login` (allauth)
- Org slug: `sabumazur`

## Key URLs

| Surface | URL |
|---------|-----|
| Dashboard | `/` |
| Invoice list | `/sales/` |
| Invoice create | `/sales/create/` form id: `#invoice-form` |
| Quotation create | `/quotations/create/` form id: `#quotation-form` |
| Sale order create | `/sale-orders/create/` form id: `#sale-order-form` |
| Purchase order create | `/purchases/purchase-orders/create/` form id: `#doc-form` |
| Supplier invoice create | `/purchases/supplier-invoices/create/` form id: `#si-form` |
| Sidebar nav | `#sidebar a[href]` |

## Script template

```js
const { chromium } = require('playwright');  // local dep — run from project root

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Login
  await page.goto('http://localhost:8000/auth/login/');
  await page.fill('[name="login"]', 'sabumazur@gmail.com');
  await page.fill('[name="password"]', 'testpass123');
  await page.click('[type="submit"]');
  await page.waitForURL('**/', { timeout: 8000 });

  // Navigate to target
  await page.goto('http://localhost:8000/TARGET_URL/');
  await page.waitForLoadState('load');
  await page.waitForTimeout(500); // let window.load + TomSelect/Alpine settle

  // --- your test steps here ---

  // Screenshot (save to project root, then Read tool can view it)
  await page.screenshot({ path: 'verify_output.png' });

  await browser.close();
})().catch(err => { console.error(err.message); process.exit(1); });
```

## Timing notes

- Always `waitForLoadState('load')` then `waitForTimeout(300-500)` before interacting — Alpine.js is `defer`, TomSelect binds at DOMContentLoaded, window.load listeners fire last
- TomSelect selects: interact via `sel.tomselect.setValue(val)` in `page.evaluate()` to reliably trigger change events
- `window._docFormMarkDirty` is exposed by the unsaved-guard — call it in evaluate() to force-dirty a form without UI interaction

## Screenshots

```js
await page.screenshot({ path: 'verify_output.png' });
// Then in Claude: Read tool on c:\Users\sabum\sabsys\verify_output.png
```

Clean up after:
```bash
rm -f my_test.js verify_output.png
```

## Common mistakes

| Mistake | Fix |
|---------|-----|
| `Cannot find module 'playwright'` | Run script from project root, not `/tmp` |
| Login times out | URL is `/auth/login/`, not `/accounts/login/` |
| Form not found after login | Add `waitForLoadState('load')` + `waitForTimeout(500)` |
| TomSelect change not detected | Use `sel.tomselect.setValue()` via `page.evaluate()` |
| Screenshot not viewable | Save to project root, use Read tool path `c:\Users\sabum\sabsys\file.png` |
