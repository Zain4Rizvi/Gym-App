# Product

<!-- impeccable:product-schema 1 -->

Assumptions below are inferred from the repository and the restyle brief. This session had no question tool, and the brief already told the work to proceed.

## Platform

adaptive

## Users

One person (inferred: the account owner, logging for themselves) training and keeping a single private log of lifts, the day, supplements, and physique photos.

## Product Purpose

Replace scattered lift notes, daily macros, supplements, and physique photos with one log. Success is that a session, a day, a photo, and the trends can be written and read again without a second tool.

## Positioning

The typed note is the record. One note is one session. The phone and the website are the same Expo app, and each account is its own book.

## Operating Context

Used on a phone at the gym and in a browser on the same account. Dates come from the phone as `YYYY-MM-DD`. The API stores the book in local files.

## Capabilities and Constraints

- Create account and log in. Token in secure store on native and `localStorage` key `gym-token` on web.
- Notes is the home. Newest first, first line is the title, search, new, delete, full-screen plain text. Typing autosaves. The day label comes from the profile split. Unsent draft stays on device. `client_request_id` is a uuid. A text change re-parses when a model is configured, and otherwise marks the note pending and drops generated sets. Set review can patch weight, reps, RPE, set type, and exercise.
- Day: bodyweight, sleep, steps, summary, four macros, supplement checklist toggle, add checklist item, context note.
- Photo: date, pose front/side/back, pick or take a picture, upload, thumbnails via the authenticated file route. Web uses a file input.
- Dashboard: `/trends` as simple bars and a list. Empty state when there is no data. Lifts, bodyweight with 7-day mean, calories and protein, supplement adherence, muscle volume.
- API base `EXPO_PUBLIC_API_URL`, default `http://127.0.0.1:9477`.
- Do not send photos to Gemini. Do not add a second website or a chart library.

## Brand Commitments

The name is Gym. The home screen is a notepad. The dashboard is the diary those notes become. Warm paper, ink, one amber accent. One design system lives in `mobile/src/constants/theme.ts`.

## Evidence on Hand

Working screens under `mobile/src`. No marketing claims, prices, or testimonials. Do not invent them.

## Product Principles

- The typed note is the record; the screen should get out of the way of writing it.
- Empty means not recorded. A zero is a real zero.
- Every tab is the same log, not a separate product.
- Behavior that already works stays; the visual system is what changes.
