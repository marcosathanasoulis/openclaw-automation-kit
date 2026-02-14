# OpenClaw Automation Learnings

This file captures hard-won knowledge from successful and failed runs.
Runners and the adaptive layer should reference this file.
Update this whenever a new pattern or fix is discovered.

---

## United Airlines

### What works
- **Search form approach**: Use the homepage search form with "Book with miles" toggle
- **Login**: MileagePlus number ka388724, credentials from keychain `www.united.com`
- **Wait after login**: Must wait 8+ seconds after clicking Sign In before doing anything else
- **Miles toggle**: Enable "Book with miles" BEFORE filling the search form
- **Date strip**: After results load, the date strip shows prices for nearby dates

### What doesn't work
- **Deep link URLs**: `united.com/en/us/fsr/choose-flights?...` returns "unable to complete your request" error (as of Feb 2026)
- **sc parameter**: URL param `sc=5` (business) filters results to only show business cabin
- **Multiple Miles selections**: Selecting "Miles" from dropdown more than once causes infinite loop
- **No wait after login**: Navigating immediately after login loses the session

### Key parameters
- `sc=7` = economy (shows all cabins on results page)
- `sc=5` = business (filters to business only — avoid)
- `clm=7` = cabin class economy

---

## Delta Airlines

### What works
- **Flexible dates calendar**: Delta's calendar view shows miles prices across dates — very reliable
- **Login**: SkyMiles number 9396260433, credentials from keychain `www.delta.com`
- **Shop with Miles**: Must check the "Shop with Miles" checkbox on the search form
- **One-way search**: More reliable than round-trip
- **Screenshot the calendar**: The flexible dates view is stable and doesn't crash

### What doesn't work
- **Clicking CONTINUE on results**: Opens individual flight page that crashes Chrome
- **Scrolling on results pages**: Can cause issues
- **Cash price search**: If "Shop with Miles" is unchecked, returns cash prices and may crash Chrome

---

## Singapore Airlines

### What works
- **Hybrid approach**: Login via browser agent, then use Vue.js API for calendar manipulation
- **Login URL**: `https://www.singaporeair.com/en_UK/us/ppsclub-krisflyer/login/`
- **KrisFlyer number**: 8814147288, credentials from keychain `www.singaporeair.com`
- **Redemption form URL**: `https://www.singaporeair.com/en_UK/us/home#/book/redeemflight`
- **Direct SIA routes from SFO**: SFO→SIN (nonstop), SFO→NRT, SFO→ICN

### What doesn't work
- **SFO→BKK**: Not a direct SIA route; requires connection through SIN
- **form.submit() / fetch()**: Both trigger Akamai CAPTCHA; must use real browser clicks
- **Calendar clicks**: Vue.js calendar state must be set via `__vue__` API, not UI clicks

### Key notes
- SIA may show "no availability" for short-haul or non-direct routes
- The hybrid approach (browser login + API search) is fastest and most reliable

---

## AeroMexico

### What works
- **Cash price search**: Simpler and more reliable than award search
- **Character-by-character typing**: Required for reCAPTCHA fields (use `press` action, not `type`)
- **Spanish interface**: Site is in Spanish; "Puntos" = points, "Directo" = nonstop

### What doesn't work
- **Award (puntos) search**: Complex to navigate; the "Puntos" toggle often doesn't stick
- **Fast typing**: reCAPTCHA detects automated fast typing — must use char-by-char press
- **js_eval/fill**: Blocked by reCAPTCHA on login page

### Key notes
- Use cash price search instead of award to avoid complexity
- Login: account 00667826747, credentials from keychain `www.aeromexico.com`

---

## ANA (All Nippon Airways)

### What works
- **English path**: Use `/us/en` URL path — less bot-sensitive than Japanese default
- **ANA URL**: `https://aswbe-i.ana.co.jp/international_asw/pages/award/search/roundtrip/award_search_roundtrip_input.xhtml?CONNECTION_KIND=JPN&LANG=en`
- **Login**: ANA Mileage Club number 4135234365, credentials from keychain `aswbe-i.ana.co.jp`
- **Airport codes**: Must use NRT or HND (not TYO which is a city code)

### What doesn't work
- **TYO as airport code**: ANA search doesn't accept city codes
- **CAPTCHA**: ANA frequently shows image CAPTCHAs that block automation
- **Multiple CAPTCHA attempts**: After 2 failed attempts, the CAPTCHA gets harder

### CAPTCHA handling
- When CAPTCHA appears, take a screenshot and send it to the user via iMessage
- Wait for the user to respond with the solution
- This requires the iMessage bot integration on Mac Mini

---

## General Patterns

### Timeouts
- Browser agent: 480-720s per run is typical
- Agent-side SSH timeout: 720s (12 min)
- Health check per-airline timeout: 900s (15 min)
- International routes take longer than domestic

### Chrome/CDP
- Only ONE browser agent can use Chrome at a time (CDPLock)
- Kill stale processes before starting a new run
- Close Chrome tabs between test runs
- CDP port: 9222 on Mac Mini

### Common failure modes
1. **Deep link URLs breaking**: Airline websites change URL params regularly → use search forms instead
2. **Session lost on navigation**: Login, then navigate to deep link → session cookies may not persist
3. **CAPTCHA**: ANA and sometimes AeroMexico show CAPTCHAs → need human-in-the-loop
4. **Rate limiting**: Too many login attempts → wait and retry later
5. **Stale CDPLock**: Previous process died without releasing lock → kill and clean up
6. **browser_agent.py emptied**: Concurrent processes can corrupt files → always check file integrity

### Search strategy
- Always search ECONOMY class — results pages often show all cabins
- Use midpoint date (`max(7, days_ahead // 2)`) for date-range searches
- Tell the agent to report ALL visible fares, not just the searched cabin
- Tell the agent NOT to run a second search for a different cabin
- Report both min and max prices per cabin

### Airport codes
- Use actual airport codes (NRT, HND) not city codes (TYO)
- Verify routes exist on the airline (SIA doesn't fly SFO→BKK direct)
- Common valid routes: SFO→NRT, SFO→SIN, SFO→MEX, SFO→BOS, SFO→JFK
