// Copies the GENUINE iTwin.js runtime public assets shipped inside the
// installed @itwin/core-frontend package into this app's `public/` directory
// (Vite's native static root). Vite serves `public/<x>` at `/<x>` verbatim in
// dev and copies it into `dist/` on build — with correct content-types and no
// middleware-ordering issues.
//
// iTwin.js fetches these at runtime from `${IModelApp.publicPath}<path>`
// (default publicPath = "/"):
//   /scripts/parse-imdl-worker.js   (the iMdl decode Web Worker)
//   /scripts/draco_decoder.wasm     (+ draco encoder/wrapper)
//   /locales, /images, /cursors, /sprites, /assets
//
// The files are copied UNMODIFIED from the installed package, so the version
// always matches the resolved @itwin/core-frontend. node_modules is not
// modified. This script is idempotent and safe to run before dev/build.
import { cp, mkdir, rm } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const appDir = resolve(here, '..')
const srcDir = resolve(appDir, 'node_modules/@itwin/core-frontend/lib/public')
// Land the assets in a dedicated subfolder of public/ so they are obviously
// third-party and never clash with app-owned public files.
const destRoot = resolve(appDir, 'public')

if (!existsSync(srcDir)) {
  console.error(`[copy-itwin-assets] Source not found: ${srcDir}\nIs @itwin/core-frontend installed?`)
  process.exit(1)
}

// Copy each top-level entry of the package public dir to public/<entry>, so
// they resolve at the root URLs iTwin.js expects (e.g. /scripts/..., /locales/...).
const entries = ['scripts', 'locales', 'images', 'cursors', 'sprites', 'assets']
let copied = 0
for (const entry of entries) {
  const from = resolve(srcDir, entry)
  if (!existsSync(from)) continue
  const to = resolve(destRoot, entry)
  await rm(to, { recursive: true, force: true })
  await mkdir(dirname(to), { recursive: true })
  await cp(from, to, { recursive: true })
  copied += 1
}
console.log(`[copy-itwin-assets] Copied ${copied} iTwin.js public asset group(s) into public/ from core-frontend.`)
