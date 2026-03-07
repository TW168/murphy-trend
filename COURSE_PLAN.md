# Plan: Stock Market Analysis Course

## Context

The user wants a structured stock market analysis course based on the Murphy technical analysis concepts that MurphyTrend already implements. The course will live at `/help/course` as a subpage under the existing Concepts page (`/help`). Currently the app has no nested routes — this will be the first subpage.

The app implements 15+ Murphy indicators across `app/services/analysis.py` and `app/services/patterns.py`. The existing `/help` page has quick-reference concept cards, but the course will be a **progressive learning experience** with structured modules, lessons, objectives, and "try it" CTAs.

## Course Structure

**5 Modules, 13 Lessons** — follows Murphy's book chapter order:

| Module | Lessons | Chapters |
|--------|---------|----------|
| 1. Foundations | 1. Trend & Dow Theory, 2. Support & Resistance | Ch. 1-4 |
| 2. Chart Patterns | 3. Reversal Patterns, 4. Continuation Patterns, 5. Gaps & Key Reversals | Ch. 5-6 |
| 3. Volume | 6. Volume Confirmation, 7. OBV | Ch. 7 |
| 4. MAs & Bands | 8. Moving Averages, 9. Bollinger Bands | Ch. 9 |
| 5. Oscillators & Targets | 10. RSI, 11. MACD, 12. Fibonacci, 13. Scoring & Price Targets | Ch. 10, 13 |

Each lesson includes: learning objectives, explanation, key takeaways, and a "Try it" link to `/analyze?ticker=XXX`.

## Format

Single-page scrollable with sticky TOC sidebar — reusing the exact pattern from `sad.html` (TOC generated from h2/h3 headings via JS + IntersectionObserver scrollspy).

## Changes

### 1. `app/routers/help_route.py` — Add route
Add `GET /help/course` handler returning `course.html` template (same pattern as existing `/help` route).

### 2. `app/templates/course.html` — New template (bulk of work)
- Extends `base.html`
- Left sidebar: sticky TOC (col-lg-3, reuse `sad.html` TOC JS)
- Right content (col-lg-9): course hero + 5 modules with 13 lessons
- Each lesson: card with learning objectives (teal left-border), content, key takeaways (blue left-border), try-it CTA
- Custom CSS in `{% block head %}` following existing inline-style pattern
- Dark mode support via existing CSS vars (`--mt-card`, `--mt-border`) + `[data-bs-theme="dark"]` overrides
- TOC JS in `{% block scripts %}` (copy from `sad.html` lines 42-79)

### 3. `app/templates/base.html` — Nav active state (line 38)
Change `request.url.path == '/help'` to `request.url.path.startswith('/help')` so "Concepts" nav link highlights on both `/help` and `/help/course`.

### 4. `app/templates/help.html` — Add course CTA banner
Insert a card between the hero and step-by-step sections with "Take the Full Course" heading and "Start Learning" button linking to `/help/course`.

### 5. `SAD.md` — Update docs
Add `GET /help/course` to the API Endpoints table and mention `course.html` in the folder structure.

## Key Files to Reference
- `app/templates/sad.html` — TOC sidebar + scrollspy JS pattern to reuse
- `app/templates/help.html` — Design patterns (concept cards, chapter tags, CTA styling)
- `app/services/analysis.py` — Indicator implementations for lesson content accuracy
- `app/services/patterns.py` — Pattern detection for chart patterns lessons
- `app/static/css/main.css` — Existing TOC CSS classes (`toc-sidebar`, `toc-nav`, `toc-link`, `toc-h2`, `toc-h3`)

## Verification
1. Run `uv run uvicorn app.main:app --reload --port 8000`
2. Visit `/help` — verify course CTA banner appears and links to `/help/course`
3. Visit `/help/course` — verify page loads with all 13 lessons and TOC sidebar
4. Verify TOC scrollspy highlights current section while scrolling
5. Verify dark mode toggle works on course page
6. Verify "Concepts" nav link is active on both `/help` and `/help/course`
7. Click "Try it" links — verify they open `/analyze?ticker=XXX` correctly
