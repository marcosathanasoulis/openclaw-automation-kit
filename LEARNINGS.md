# OpenClaw Automation Learnings

This file captures hard-won knowledge from successful and failed runs.
Runners and the adaptive layer should reference this file.
Update this whenever a new pattern or fix is discovered.

---

## United Airlines

### What works
- **Login**: MileagePlus number ka388724, credentials from keychain `www.united.com`
- **Wait after login**: Must wait 8+ seconds after clicking Sign In
- **SMS 2FA**: Code comes from sender `26266` (NOT `94960`)
- **Deep-link URL with at=1**: `united.com/en/us/fsr/choose-flights?...&at=1` triggers award mode
- **Date strip**: After results load, shows prices for nearby dates

### What doesn't work
- **Deep link without login**: Shows cash prices, not miles. Login is REQUIRED.
- **Homepage "Book with miles" toggle**: Agent frequently fails to enable it or it doesn't persist through search
- **sc parameter**: URL param `sc=5` (business) filters results. Use `sc=7` (economy) to see all cabins

### Goal structure (navigate-first approach)
- **STEP 1**: Login on homepage (if needed)
- **STEP 2**: Navigate to `at=1` deep-link URL
- **STEP 3**: Handle login dialog on results (close if logged in, show cash if not)
- **STEP 3b**: If error page appears, navigate to cash URL (same params without `at=1`)
- **STEP 4-5**: Screenshot and report

### Known issues
- **Login uses ~14-20 steps**: SMS 2FA flow is step-heavy. Need max_steps >= 60
- **Rate limiting**: United login rate-limits after ~5 attempts. "Something went wrong" error on Continue. Wait 1+ hours (sometimes needs 24h+)
- **Session expiry**: If too many steps after login, session expires and login dialog reappears on results
- **Login dialog on results**: When `at=1` URL is used without login, shows "Sign in or Show flights with money" dialog. Close dialog to see cash prices.
- **Error page after "Show flights with money"**: Clicking "Show flights" on at=1 URL can lead to error page. Must navigate to cash URL (without at=1) as fallback.
- **Cash fallback**: Without login, navigate to URL without `at=1` param to get cash prices (still valid data)
- **Chrome page crashes**: CDP connection drops occasionally. Agent should create new tab and retry navigation.

---

## Delta Airlines

### What works
- **Homepage search with shopWithMiles=true**: Reliable deep-link approach
- **Direct results**: Agent finds fares consistently
- **7-12 steps typical**: Delta is the most efficient airline to search
- **No login needed**: Award search works without authentication

### Known issues
- **Double search**: If prompt says "report economy AND business", agent does TWO searches. Fix: "Do NOT run a second search"
- **Timeout with fares**: Agent may report "timed out" for secondary search while first search had valid fares

---

## Singapore Airlines

### What works
- **Hybrid approach**: BrowserAgent login + Playwright form fill + Playwright scraping
- **Login**: KrisFlyer 8814147288, keychain `www.singaporeair.com`, ~10 steps
- **Form fields** (confirmed Feb 2026):
  - `input[name='flightOrigin']` — origin (often pre-filled with SFO from login)
  - `input[name='redeemFlightDestination']` — destination
  - `input[name='departDate']` — date picker
  - `input[name='flightClass']` — cabin class (suggest-item click)
  - `input[name='flightPassengers']` — passenger count
  - `form.redeem-flight button[type='submit']` — search button
- **Calendar cells**: `.viewcell` with children `.date`, `.from`, `.milesvalue`, `.miles`
- **Calendar nav**: `.SevenDayCalendar button.flip.left/right`
- **JS extraction**: Use `page.evaluate()` for reliable scraping of async calendar content
- **Confirmed availability**: SFO→SIN business: 185,000-296,000 miles (Feb-Mar 2026)

### What doesn't work
- **form.submit()**: Triggers Akamai CAPTCHA. Must click the submit button
- **fetch() API calls**: Also trigger Akamai CAPTCHA
- **Rapid re-testing**: SIA blocks with reCAPTCHA image challenge on login after 3-4 rapid tests. Need 30+ min cooldown (sometimes longer)
- **Login page CAPTCHA**: After repeated logins, SIA shows motorcycle/bicycle image CAPTCHA that agent cannot solve. Only fix is waiting for cooldown.
- **Session cookies expire**: Chrome session cookies for SIA don't persist across long gaps. Must login each time.

### Navigation tips (critical)
- **ALWAYS do two-step navigation**: Even if URL already has "redeemflight", the Angular app may not be bootstrapped from a login redirect. Always: homepage first → then hash to redeemflight.
- **Homepage URL**: `https://www.singaporeair.com/en_UK/us/home` (bootstraps Angular)
- **Redeem URL**: `https://www.singaporeair.com/en_UK/us/home#/book/redeemflight`
- **Wait times**: 6s after homepage, 5s after redeem hash navigation

### Form fill tips
- **Skip origin if pre-filled**: Check `origin_input.input_value()` — if SFO already there, don't refill
- **Escape key**: Press Escape after each field to close autocomplete dropdowns
- **Triple-click to select**: Use `click(click_count=3)` before typing to select all existing text
- **Slow typing**: Use `delay=100-120` for autocomplete fields
- **Wait 3-4s**: After typing, wait for autocomplete dropdown before clicking suggest-item
- **Cookie popup**: Dismiss with `button:has-text('Accept')` or `.dwc--SiaCookie__PopupClose`
- **adaptive_run max_attempts=1**: Don't retry login — SIA counts it as bot activity

### Scraping tips
- **Loading cells**: First ~7 viewcells may show `.Donut` loading spinner
- **JS extraction**: Use `page.evaluate()` to extract all viewcell data at once
- **Wait for cells**: After search, wait 15s + check for `.viewcell:not(.loading)` before scraping

---

## AeroMexico

### What works
- **English site**: `aeromexico.com/en-us` for cash search (no login needed)
- **Cash prices**: Found $223 SFO→MEX economy (Feb 2026)
- **30 steps typical**: Including reCAPTCHA handling
- **Press char-by-char**: For reCAPTCHA, use `press` action for human-like input

### What doesn't work
- **Points/puntos toggle**: Very difficult to interact with programmatically
- **Airport confusion**: Agent sometimes fills wrong airports. Need explicit "FROM = SFO, TO = MEX" instructions

### Known issues
- **reCAPTCHA**: Always present, eats many steps. Budget 45+ steps
- **Spanish page**: Spanish version triggers different form behavior

---

## ANA (All Nippon Airways)

### What works
- **English path**: `ana.co.jp/en/us/` — homepage, less bot-sensitive
- **Cookie dialog dismiss**: Use JS: `document.querySelector('#onetrust-accept-btn-handler')?.click()` or scroll down to find button

### What doesn't work
- **Direct URLs**: `aswbe-i.ana.co.jp` → 404, `aswbe.ana.co.jp` → "Access Denied" without login
- **Award search without login**: Returns "Access Denied". Login is MANDATORY.
- **No keychain credentials**: As of Feb 2026, no ANA credentials in the automation keychain. Need to add them.

### Known issues
- **Cookie dialog blocks agent**: The cookie settings dialog has no visible accept button without scrolling down. Agent gets stuck.
- **Bot detection**: ANA has aggressive bot detection on the award search pages
- **CAPTCHA**: May appear, especially on repeated access
- **Not fully tested**: Needs live validation once credentials are added to keychain

---

## JetBlue

### What works
- **usePoints=true URL param**: Deep-link with `?usePoints=true` correctly enables points mode (checkbox shows checked)
- **No login needed for search**: Points checkbox works without authentication
- **Fast execution**: 12 steps, ~130s with no login
- **Fixed URL params**: `isMultiCity`, `sharedMarket`, `roundTrip` (NOT `is498Multi`, `shared498Market`, `roundTri498p`)

### What doesn't work
- **"Use TrueBlue points" checkbox toggle**: Agent can't enable it via clicks/JS. Use URL param instead.
- **NRT→SFO availability**: "No flights found" on tested dates (Feb-Mar 2026). JAL codeshare may have limited availability.

### Known issues
- **JAL partnership ending March 31, 2026**: NRT/HND→SFO bookable via TrueBlue points through JAL codeshare
- **Availability sparse**: Not all dates have flights. Try multiple dates (Tue/Wed/Thu preferred).
- **Login + 2FA overhead**: If login needed, email 2FA takes ~15 steps. Skip login unless required.
- **160K TrueBlue points available**: Account marcos@athanasoulis.net

---

## General Patterns

### Step budgets
| Airline | Login | Search | Total min |
|---------|-------|--------|-----------|
| United | ~14-20 (SMS 2FA) | ~10 | 60 |
| Delta | 0 (no login) | ~7-12 | 30 |
| Singapore | ~10 (hybrid) | N/A (Playwright) | 20 |
| AeroMexico | 0 (cash) | ~30 (reCAPTCHA) | 45 |
| ANA | ~10 (needs keychain setup) | ~20 | 50 |
| JetBlue | 0 (URL param) | ~12 | 30 |

### CDPLock
- Only ONE browser automation can use Chrome at a time
- Tests MUST run sequentially — never in parallel
- Clear `/tmp/cdp_lock` if stuck
- Close all Chrome tabs between tests via CDP endpoint

### Rate limiting
- **United**: Rate-limits after ~5 login attempts. Wait 1+ hours
- **Singapore**: "Access Blocked" CAPTCHA after 3-4 rapid searches. Wait 30+ min
- **AeroMexico**: reCAPTCHA appears on every visit
- **Best practice**: 10-30s cooldown between airline tests

### Prompt engineering
- "Do NOT run a second search for a different cabin" prevents double-search timeouts
- "Any nearby date is fine" for calendar pickers (agent struggles with exact dates)
- "Your VERY NEXT ACTION must be: [action]" forces specific step ordering
- "IMMEDIATELY do done" after screenshot prevents wandering
- "Do NOT use js_eval" prevents agents from over-engineering solutions

### Health check pipeline
- Full chain: Mac Mini script → SSH → Ubuntu Agent → search_award_flights tool → SSH → Mac Mini → OpenClaw CLI → Browser Agent → Chrome → Airline
- Timeout: 900s per airline (15 min)
- Agent timeout: 720s (12 min)
- Sequential execution required (CDPLock)
- PYTHONPATH=src required for CLI commands on Mac Mini
