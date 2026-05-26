# Frontend Runtime Notes

This frontend uses Next.js 14 and must run on a supported Node runtime.

## Required Node Version
- Recommended: Node 20 LTS
- Supported range in this project: >=18 and <23
- Node 26 is unsupported and can cause dev chunk failures (for example `/_next/static/chunks/app/layout.js` 404) after code changes.

## Commands
- Development (hot reload):
  - `npm run dev`
- Stable local mode (no hot reload, most reliable):
  - `npm run dev:stable`
