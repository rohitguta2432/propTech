# Design

Visual identity, screens, components. Built to feel like a security tool (Truecaller, 1Password, Cred safety) — not a real estate brochure.

---

## Brand identity

### Colors

```
PRIMARY
─────────────────────────────────────────
Trust Blue    #2563EB    (primary actions, links, brand)
Deep Blue     #1E40AF    (hover states, headings)

SCORE COLORS (functional, never decorative)
─────────────────────────────────────────
Safe Green    #10B981    (score 70+)
Amber         #F59E0B    (score 40–69)
Risky Red     #EF4444    (score <40)

NEUTRALS
─────────────────────────────────────────
Slate 900     #0F172A    (body text)
Slate 600     #475569    (secondary text)
Slate 200     #E2E8F0    (borders)
Slate 50      #F8FAFC    (page background)
White         #FFFFFF    (cards, modals)
```

### Typography

- **Headings + body**: Inter (or DM Sans as fallback)
- **Numbers + scores**: JetBrains Mono (monospace makes scores feel like data, not marketing)
- **Sizes**:
  - H1: 48px / 56px line-height (landing hero only)
  - H2: 32px / 40px
  - H3: 24px / 32px
  - Body: 16px / 24px
  - Small: 14px / 20px
  - Score (huge): 96px / 96px JetBrains Mono

### Spacing

- 8px grid: 8, 16, 24, 32, 48, 64
- Section padding: 64px desktop, 32px mobile
- Card padding: 24px
- Border radius: 12px on cards, 8px on buttons, 9999px on pills

### Shadows

- Card: `0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04)`
- Modal: `0 20px 25px rgba(15,23,42,0.10)`
- Score badge: subtle inner glow, no outer shadow

### Voice in UI

- No exclamation marks
- No emoji decoration (warning icons OK when functional)
- Plain, direct sentences
- Show evidence with every claim ("Source: Karnataka RERA")

---

## The hero element — Trust Score Badge

The single most important visual in the product. Appears on every surface.

### Anatomy

```
       ┌─────────────────────┐
       │                     │
       │       42 / 100      │   ← JetBrains Mono, 96px
       │                     │
       │       RISKY         │   ← Inter Bold, 18px, color = score color
       │                     │
       │   ⚠ 4 red flags    │   ← Inter Regular, 14px, slate-600
       │                     │
       └─────────────────────┘
              ↑
        Background:
        - Score 70+: linear-gradient(135deg, #ECFDF5, #D1FAE5)
        - Score 40-69: linear-gradient(135deg, #FFFBEB, #FEF3C7)
        - Score <40: linear-gradient(135deg, #FEF2F2, #FEE2E2)
        Border: 2px of corresponding bold color
        Border radius: 16px
        Padding: 32px
```

### Sizes

- Web report page: 240×240px (centerpiece)
- Web report list view: 80×80px
- Chrome extension card overlay: 64×64px (just score number, label below)
- Chrome extension full sidebar: 160×160px
- WhatsApp: text only — `Trust Score: 42/100 — RISKY`

---

## Key screens

### 1. Landing page

```
┌──────────────────────────────────────────────────────────────┐
│  PropCheck (logo)                       Sign in   [Add to Chrome]│
├──────────────────────────────────────────────────────────────┤
│                                                              │
│         Don't get scammed on your next property.             │
│                                                              │
│   Verify any Magicbricks, 99acres, Housing or NoBroker       │
│   listing in 30 seconds. Free. Neutral.                      │
│                                                              │
│   ┌────────────────────────────────────────────┬────────┐    │
│   │  Paste a property listing link…            │ Check  │    │
│   └────────────────────────────────────────────┴────────┘    │
│                                                              │
│   Free forever for buyers. We don't sell listings.           │
│                                                              │
│   ─────────  How it works  ─────────                         │
│                                                              │
│   1. Paste any link    2. We check 8 things    3. 30s score  │
│                                                              │
│   ─────────  Live example  ─────────                         │
│                                                              │
│           [ Trust Score Badge — 42 / 100 RISKY ]             │
│                                                              │
│           ⚠ Listed 4 times across 3 portals                 │
│           ⚠ Photos appear on 7 other listings                │
│           ⚠ Price 22% below locality average                 │
│           ⚠ RERA number does not match Karnataka records     │
│                                                              │
│           Before paying anyone:                              │
│           ☐ Visit the property in person                     │
│           ☐ Ask for sale deed + property tax record          │
│           ☐ Never pay token over UPI                         │
│                                                              │
│   ─────────  Three ways to use it  ─────────                 │
│                                                              │
│   [Web]   [Chrome Extension]   [WhatsApp]                    │
│                                                              │
│   ─────────  We don't sell listings  ─────────               │
│                                                              │
│   We're not Magicbricks. We're not a broker. We don't take   │
│   commissions. Our money comes from banks who use our API.   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2. Report page

The hero of the product. URL: `propcheck.in/check/chk_abc123`

```
┌──────────────────────────────────────────────────────────────┐
│  PropCheck                    [Share]  [Save PDF]  [New check]│
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │                                                      │   │
│   │            [ TRUST SCORE BADGE ]                     │   │
│   │                  42 / 100                            │   │
│   │                  RISKY                               │   │
│   │                                                      │   │
│   │   This listing has 4 high-risk signals.              │   │
│   │   Read the red flags below before you pay anyone.    │   │
│   │                                                      │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   PROPERTY                                                   │
│   ───────                                                    │
│   3 BHK Apartment in Whitefield, Bangalore                   │
│   ₹1.20 Cr  ·  1,450 sqft  ·  ₹8,275/sqft                    │
│   Source: Magicbricks · Listing ID 12345 · 87 days old       │
│   [ View original listing → ]                                │
│                                                              │
│   RED FLAGS (4)                                              │
│   ──────────                                                 │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ ⚠ Duplicate listings detected             [HIGH RISK]│   │
│   │ Listed 4 times across 3 portals at 3 different       │   │
│   │ prices (₹1.2 Cr, ₹1.35 Cr, ₹1.1 Cr).                 │   │
│   │ See: Magicbricks · 99acres · Housing                 │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ ⚠ Photos likely stolen                    [HIGH RISK]│   │
│   │ Listing photos appear on 7 other unrelated listings. │   │
│   │ Source: Google reverse image search                  │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ ⚠ RERA mismatch                           [HIGH RISK]│   │
│   │ The RERA number on this listing does not match any   │   │
│   │ Karnataka RERA project record.                       │   │
│   │ Source: Karnataka RERA portal                        │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ ⚠ Builder has 6 complaints                  [MEDIUM] │   │
│   │ "ABC Developers" has 6 open complaints + 2 delays.   │   │
│   │ Source: Karnataka RERA complaint registry            │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│   GREEN FLAGS                                                │
│   ───────────                                                │
│   None found.                                                │
│                                                              │
│   PRE-PURCHASE CHECKLIST                                     │
│   ──────────────────────                                     │
│   ☐ Visit the property in person before paying any token    │
│   ☐ Ask for the sale deed                                    │
│   ☐ Verify property tax record at municipal portal           │
│   ☐ Never pay token over UPI to a personal account           │
│   ☐ Verify owner identity with Aadhaar + utility bill        │
│   ☐ Cross-check broker license                               │
│   ☐ Ask for the original RERA registration certificate       │
│                                                              │
│   VERIFICATION DETAILS                                       │
│   ─────────────────────                                      │
│   RERA status:        MISMATCH                               │
│   Listing age:        87 days                                │
│   Locality avg price: ₹10,600 / sqft (this is 22% below)    │
│   Image matches:      7 other listings                       │
│   Builder complaints: 6                                      │
│                                                              │
│   ─────────  Want full title verification? ─────────         │
│   Get the encumbrance certificate + ownership chain          │
│   via our partner Landeed.    [ ₹999 deep report → ]         │
│                                                              │
│   Was this score wrong?  [Flag for review]                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3. Chrome extension overlay

Two modes: badge on each listing card, full sidebar on detail pages.

**Badge mode** — appears in top-right corner of every listing card on portal listing pages:

```
   ┌───────────────────────────────────────┐
   │  [photo]   3 BHK Whitefield           │
   │            ₹1.2 Cr · 1450 sqft        │
   │                                       │
   │                          ┌─────┐      │
   │                          │ 42  │ ← badge (color = score color)
   │                          └─────┘      │
   │                          RISKY        │
   └───────────────────────────────────────┘
```

**Sidebar mode** — appears as a 360px-wide panel on the right edge of any portal listing detail page:

```
   ┌────────────────────────┐
   │  PropCheck       ✕     │
   │                        │
   │   ┌────────────────┐   │
   │   │   42 / 100     │   │
   │   │     RISKY      │   │
   │   └────────────────┘   │
   │                        │
   │   ⚠ Duplicate listings│
   │   ⚠ Photos stolen     │
   │   ⚠ RERA mismatch     │
   │   ⚠ 6 complaints      │
   │                        │
   │   [ See full report → ]│
   │                        │
   │   [ Open in WhatsApp ] │
   │                        │
   └────────────────────────┘
```

### 4. WhatsApp bot

Pure text. No images at MVP. Format on every check:

```
🔍 PropCheck — Trust Report

Trust Score: 42 / 100 — RISKY

Property
3 BHK in Whitefield, Bangalore
₹1.20 Cr · 1,450 sqft · Magicbricks

Red flags (4):
1. Listed 4 times at different prices
2. Photos appear on 7 other listings
3. RERA number does not match Karnataka records
4. Builder has 6 open complaints

Before paying anyone:
☐ Visit in person
☐ Ask for sale deed + property tax record
☐ Never pay token over UPI

Full report: propcheck.in/c/abc123
Forward this message to family.
```

---

## Component library (shadcn-based)

| Component | Use |
|---|---|
| `<TrustScoreBadge size="hero|md|sm" score={42} />` | The score viz at every size |
| `<FlagCard severity="high|medium|low" icon code label evidence />` | Red and green flag rendering |
| `<ChecklistItem checked label link? />` | Pre-purchase checklist line |
| `<VerificationRow label value status />` | Bottom data table on report |
| `<SourceCitation source url />` | Tiny grey link under every fact |
| `<PortalLogo portal />` | MB / 99acres / Housing / NoBroker icons |
| `<ShareSheet url />` | Copy link, WhatsApp, X (Twitter), email |
| `<CheckInput onSubmit />` | Hero paste-link input on landing |

All components use shadcn primitives where possible (Card, Button, Input, Dialog, Tooltip).

---

## Mobile design notes

The web tool will get 70%+ mobile traffic from day 1.

- Hero input must be **thumb-reachable** — paste button at the bottom on mobile, not the top.
- Trust Score Badge stays large on mobile (240px) — it's the whole point.
- Red flag cards stack vertically. Each card is full-width.
- Checklist must support large tap targets (min 48×48px).
- Sticky footer CTA on mobile: "New check" — easy access without scrolling up.
- Avoid horizontal scrolling in tables — use stacked rows on mobile.

---

## Accessibility

- WCAG AA color contrast everywhere. Test the score badge backgrounds especially.
- All score colors have **icon + text label** — never color alone (red-green colorblind users still need to read "RISKY" text).
- All interactive elements keyboard-accessible. Visible focus rings.
- Score badge has `role="img"` + `aria-label="Trust Score 42 out of 100, Risky"`.
- Forms: every input has a label. No placeholder-only.
- Dark mode: ship light-only at MVP. Dark mode adds complexity for the score colors.

---

## Animation principles

- **Subtle, fast, functional.** No bouncing, no parallax.
- Score reveal: fade-in + count-up animation when report loads (1s, ease-out).
- Card hover: 100ms shadow lift, no transforms.
- Loading state: skeleton blocks with shimmer (don't show spinners — they suggest "this is slow").
- No animations on the Chrome extension overlay — it must feel instant, like a native portal feature.

---

## Brand assets to create (for designer)

- Logo (wordmark + icon variant)
- Favicon (32×32, 16×16, 512×512)
- Open Graph image (1200×630) — used when someone shares a check on Twitter / WhatsApp
- Chrome extension icon (128×128, 48×48, 16×16)
- WhatsApp bot avatar
- 5–6 illustrations for landing page (How it works, Why we exist, etc.) — keep them line-art, single-color, not stock-photo style

---

## What NOT to design at MVP

- Settings page (no auth at MVP)
- Onboarding flow (the product IS the onboarding)
- Email templates (no marketing emails until Pro)
- Mobile app screens (web is enough)
- Multi-language UI (English only at launch)
- Dark mode
- Pricing page (until Pro launch in Month 4)
