# Liquid Clock

A liquid analog clock by bitScribbles: two hands over a living background, with a surge every minute, a spin on the hour and a gathering at midnight. Drag a finger to stir it.

Live at https://liquidclock.bitscribbles.com

## How it's built
Plain files, no build step, served as they are from `main` by a Cloudflare Worker:
- `index.html` — everything: WebGL for the liquid, a 2D canvas for the hands and face, the settings panel and About.
- `sw.js` — the service worker that lets the clock open offline. Bump `CACHE` with each release.
- `manifest.json` and the icons (`icon-192.png`, `icon-512.png`, `maskable-512.png`, `apple-touch-icon.png`, `favicon.png`), made by `design/make-icons.py` from `design/liquid-icon.svg`.
- `fonts/` — the brand fonts, self-hosted (SIL Open Font License, see `fonts/OFL.txt`).
- `lib/gpu-io.min.js` — Amanda Ghassaei's [gpu-io](https://github.com/amandaghassaei/gpu-io) (MIT, `lib/gpu-io-LICENSE.txt`), the published build, unchanged. It runs the fluid (Stir) in the clock's own WebGL context.

## Working on it
- Changes go on a branch and a pull request; merging to `main` publishes.
- Bump `VERSION` in `index.html` **and** `CACHE` in `sw.js` on the branch, with an entry in `CHANGELOG.md`. The last number is for fixes, the middle one for features.
- Checks: `cd checks && npm install` once, then `python3 checks/check.py` from the repo root (needs Python Playwright with Chromium).
- Previews in the address: `?t=23:59:30` to fake a time (midnight), `?hour` for the minute before the next hour (the spin).

## Licence
MIT — see `LICENSE`. The names "Liquid Clock" and "bitScribbles" and the logos aren't covered by it (said in `LICENSE` too, from 1.15.0).

The fonts are under the SIL Open Font License (`fonts/OFL.txt`, linked from About → Credits). The liquid background's domain warping follows Inigo Quilez's article (https://iquilezles.org/articles/warp/), credited in About. The fluid runs on gpu-io by Amanda Ghassaei (MIT, `lib/gpu-io-LICENSE.txt`), also credited in About. There's no other outside code and no sound.
