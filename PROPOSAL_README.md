# GoldVault Proposal Landing Page

## Overview
A premium, REVOLQ-styled landing page for presenting GoldVault to Moozhayil Gold & Diamonds.

## What You Need

Create `proposal.html` with these sections:

### 1. Hero Section
- REVOLQ branding badge
- "GoldVault" in Cormorant Garamond (gold)
- Tagline: "Military-Grade Security for Your Gold Legacy"
- Subtitle: "Trusted by Moozhayil Gold & Diamonds"
- CTA button to pricing

### 2. Problem Section (₹50 Lakh Problem)
Four cards:
- **Calculation Errors**: Manual 995 basis conversion → ₹50K-₹5L per incident
- **Fraud & Theft**: No audit trail → ₹10L+ per fraud
- **Time Wastage**: 10+ hours/week → ₹2L/year lost productivity
- **Data Vulnerability**: No encryption → Reputation damage

### 3. Solution Section (The GoldVault Solution)
Three feature cards:
- **Unhackable by Design**: AES-256-GCM, 100% offline, USB auto-lock
- **Gold-Specific Intelligence**: 995 basis conversion, 88/91.6 carat support, direction rounding
- **Complete Audit Control**: Every action logged, user-level access, change requests

### 4. ROI Section
Four metrics:
- ₹2L Time Savings
- ₹5L Error Prevention
- ₹10L+ Fraud Protection
- ₹50K Compliance Value

**Payback highlight**: 20 days | Total value: ₹17.5L | Investment: ₹95K

### 5. Pricing Section
Three tiers:
- **Standard** (₹75K): 2 USBs, 1-year support, remote training
- **Professional** (₹95K) [RECOMMENDED]: 3 USBs, 3-year support, on-site training, branding
- **Enterprise** (₹1.25L): 5 USBs, 5-year support, dedicated manager

### 6. Comparison Table
Compare GoldVault vs Tally vs Marg vs Excel on:
- Pricing, gold-specific logic, offline operation, encryption, audit trail
- Show 3-year cost: GoldVault ₹95K vs Tally ₹1.62L vs Marg ₹2.25L

### 7. Package Breakdown (Professional Tier)
Six items with values:
- Hardware (₹15K): 3 USBs
- Software (₹60K): Enterprise license
- Customization (₹20K): Moozhayil branding
- Implementation (₹25K): On-site setup
- Support (₹30K): 3-year premium
- Documentation (₹5K): Manuals + videos

Total value: ₹1,55,000 → Your price: ₹95,000 (39% savings)

### 8. Technical Specs Section
Highlight from codebase:
- **Security**: AES-256-GCM, PBKDF2 (600K iterations), in-memory SQLite
- **Calculations**: `to_995_basis()`, floor/ceil rounding, purity auto-detect
- **Audit**: Complete before/after snapshots, JSON serialization
- **Reports**: 8 types (daily, smith-wise, balance, etc.)
- **Architecture**: Python + Eel, PyInstaller single .exe, Windows 10/11

### 9. Testimonial/Trust Section
"Built for Kerala's Gold Trade" - designed specifically for businesses like Moozhayil

### 10. Final CTA
- "Secure Your Gold Legacy Today"
- Call button: +91 [Your Number]
- Badges: 30-day guarantee, lifetime license, 100% security, Made in India

## Design System

### Colors
```css
--gold: #D4AF37
--dark-gold: #B8941F
--deep-blue: #0A1828
--rich-navy: #162238
--cream: #F5F3EE
--accent-red: #C41E3A
```

### Typography
- **Headings**: Cormorant Garamond (serif, elegant)
- **Body**: Montserrat (sans-serif, clean)
- Load from Google Fonts

### Animations
- Fade in down for hero
- Fade in up for CTAs
- Pulse effect for background glow
- Bounce for scroll indicator
- Hover lift for cards

### Layout
- Hero: 100vh, centered, gradient background
- Sections: 100px padding, max-width 1200px
- Cards: Grid layout, auto-fit minmax(280px, 1fr)
- Responsive: Mobile-first, breakpoint at 768px

## REVOLQ Branding
- Add "BUILT BY REVOLQ DIGITAL AGENCY • KERALA" badge at top
- Footer: "Engineered by REVOLQ — Building systems that work"
- Link to revolq.vercel.app

## Key Selling Points to Emphasize
1. **One-time payment** vs subscriptions (Tally/Marg)
2. **100% offline** = unhackable
3. **Gold-specific** calculations (not generic accounting)
4. **ROI in 20 days** (₹95K investment, ₹17.5L annual value)
5. **Built for Kerala** jewelry businesses
6. **Military-grade security** (AES-256-GCM)
7. **Complete audit trail** (regulatory compliance)
8. **Moozhayil-ready** (custom branding, on-site setup)

## Call to Action Strategy
- Primary CTA: "Secure Your Vault Today" → #pricing
- Secondary CTA: "Call Now: +91 [Number]"
- Tertiary CTA: "WhatsApp Us"
- Trial offer: "₹10K deposit, 15-day trial, full refund if not satisfied"

## File Structure
```
proposal.html (single file, ~15-20KB)
├── Inline CSS (no external stylesheets)
├── Inline JavaScript (smooth scroll, animations)
└── Google Fonts CDN only
```

## Deployment
1. Host on Vercel/Netlify (free)
2. Custom domain: goldvault.revolq.in or goldvault.vercel.app
3. Share link with Moozhayil: "View our proposal: [link]"

## Next Steps
1. Create the complete HTML file using this structure
2. Test on mobile + desktop
3. Add your contact number
4. Deploy and share with Moozhayil

---

**Built by REVOLQ Digital Agency**  
Kerala, India • 2025  
"Building systems that work."
