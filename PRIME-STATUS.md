# PRIME — Field Ops SMS Bot
## Status as of 2026-06-15

---

## DEPLOYED & LIVE

**URL:** https://prime-fiber-production.up.railway.app
**Twilio number:** (806) 630-0278
**GitHub:** github.com/cmarrufo85/PRIME-ops
**Railway project:** prime-fiber (cmarrufo85's Projects)

---

## WHAT'S BUILT

### Core System
- [x] Flask webhook server on Railway (permanent URL, no tunnels)
- [x] Twilio signature validation (fixed for Railway's HTTPS proxy)
- [x] Async message processing (background thread — avoids Twilio's 15s timeout)
- [x] Health endpoint: /health

### Crew Registry (`crew.py`)
- [x] Chris Gonzales — 8065006215 — Lubbock — tech
- [x] Gabriel Huerta — 8065437951 — Lubbock — tech
- [x] Mathew Ruiz — 8063463980 — Lubbock — tech
- [x] Greg Delon — 8065593355 — Lubbock — tech
- [x] Armando — 9402177381 — Wichita Falls — tech
- [x] Phil Mata — 8062393887 — Lubbock — supervisor
- [x] Carlos — 5054807855 — supervisor (testing)

### Vision & Extraction (`vision.py`)
- [x] Claude Opus vision reads Oracle work order screenshots
- [x] Extracts: Work Order ID, Subscriber ID, Subscriber Name, Address, City, State, ZIP, Phone, Time Slot, Delivery Window, Activity Type, APT flag
- [x] EOD route screenshot detection (separate prompt)

### Pay Engine (`pay.py`)
- [x] Full Install experienced: $110
- [x] Full Install inexperienced: $95
- [x] Inside only: $50
- [x] Outside drop experienced: $60 / inexperienced: $45
- [x] Apartment add-on: $20 (auto-detected from screenshot)
- [x] Extender: $7/each (tech declares in notes)
- [x] Wallfish: $20 (requires 2 photos)
- [x] Buried drop: $50 (tech declares in notes)
- [x] Itemized pay breakdown in confirmation text

### SMS Flows (`app.py`)
- [x] Unknown number → "Contact your supervisor to get registered"
- [x] Work order screenshot → vision extraction → pay calc → confirmation text
- [x] Follow-up text → notes appended to active job
- [x] Wallfish declared → requests 2 photos automatically
- [x] Wallfish photos → counts received, confirms when 2 received
- [x] EOD route screenshot → reconciles against submitted jobs, flags discrepancies
- [x] 6pm reminder if EOD not received
- [x] Supervisor commands: REPORT, CONFIRM [WO#], DECLINE [WO#] [reason]

### Pay Confirmation Format
```
✓ Job logged — [Tech Name]
Customer: [Name]
Address: [Full Address]
Work Order: [ID]
Type: [Job Type]

PAY BREAKDOWN:
  [itemized]
─────────────────
  Estimated Total: $[amount]

STATUS: 🟡 Pending Metronet confirmation
Notes logged: [notes]

Send end of day route screenshot when complete.
```

### Traffic Light Status
- [x] 🟡 Yellow — logged, pending Metronet confirmation
- [x] 🟢 Green — confirmed paid (supervisor sets via CONFIRM command)
- [x] 🔴 Red — declined (supervisor sets via DECLINE command)

### Daily Automation (`daily.py`)
- [x] 6pm CST — EOD reminder to any tech with jobs but no route screenshot
- [x] 7pm CST — Supervisor report to Carlos (+15054807855): jobs per tech, pay per tech, 10% comp total, flags
- [x] Midnight — daily state reset

### Job Store (`jobs.py`)
- [x] JSON persistence (survives restarts)
- [x] Notes + photo URLs per job, timestamped
- [x] Retrievable by work order ID, tech phone, date

### Google Sheets (`sheets.py`)
- [x] Code written for 7-tab structure
- [ ] NOT CONNECTED — needs credentials.json (service account) and GOOGLE_SHEETS_ID env var

---

## PENDING / NOT YET TESTED

### Critical — Test Now
- [ ] End-to-end Oracle screenshot test from Carlos's number (5054807855)
- [ ] Confirm Claude Vision correctly extracts all fields from real Oracle screenshots
- [ ] Confirm pay confirmation SMS delivers successfully (Twilio upgraded ✓)
- [ ] Test from actual crew number (Chris, Gabriel, etc.)

### Google Sheets Integration
- [ ] Create Google Cloud project
- [ ] Enable Google Sheets API
- [ ] Create service account → download credentials.json
- [ ] Create spreadsheet, share with service account email
- [ ] Add GOOGLE_SHEETS_ID to Railway env vars
- [ ] Upload credentials.json to Railway (or use env var for JSON content)
- [ ] Run `sheets.init_spreadsheet()` once to create all 7 tabs

### Known Issues to Watch
- [ ] Oracle screenshots vary — Vision prompt may need tuning based on real screenshots
- [ ] Activity Type extraction needs validation (Full Install vs Inside Only vs Outside Drop)
- [ ] EOD reconciliation only works if Oracle EOD screen is a clear list view

### Future Phases
- [ ] Web dashboard for Carlos to view all jobs, flip status flags
- [ ] Auto-detect inexperienced techs (currently all set to experienced)
- [ ] Metronet payout import — auto-flip 🟡 → 🟢 when CSV received
- [ ] Photo storage (currently stores Twilio media URLs, which expire after ~few days)
- [ ] Crew onboarding flow (supervisor texts ADD [name] [number] to register new tech)

---

## ENV VARS ON RAILWAY
```
TWILIO_ACCOUNT_SID=AC8bbefc...
TWILIO_AUTH_TOKEN=8a6aa779...
TWILIO_NUMBER=+18066300278
ANTHROPIC_API_KEY=sk-ant-...
SUPERVISOR_NUMBER=+15054807855
WEBHOOK_BASE_URL=https://prime-fiber-production.up.railway.app
GOOGLE_SHEETS_ID=(not set)
GOOGLE_CREDENTIALS_FILE=credentials.json
```

---

## NEXT SESSION PRIORITY
1. Confirm end-to-end Oracle screenshot test works
2. Tune Vision prompt if extraction is missing fields
3. Set up Google Sheets
