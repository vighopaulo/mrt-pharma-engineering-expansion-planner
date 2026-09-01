/// <reference types="vitest/config" />
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const rootDir = dirname(fileURLToPath(import.meta.url))
const nodeModulesDir = resolve(rootDir, 'node_modules')

/**
 * Bentley's AppUI SCSS (core-react / components-react / appui-react /
 * imodel-components-react) still ships webpack-era `~`-prefixed imports, e.g.
 *   @use "~@itwin/core-react/lib/core-react/z-index" as *;
 * Modern Sass has no concept of the `~` prefix, so these fail to resolve under
 * Vite. This narrow FileImporter strips the leading `~` and resolves the rest
 * against node_modules — the standard migration path for legacy `~` imports.
 * It touches only `~`-prefixed URLs; every other import is left to Sass's
 * normal resolution. No node_modules files are modified.
 */
const bentleyTildeImporter = {
  findFileUrl(url: string): URL | null {
    if (!url.startsWith('~')) return null
    return pathToFileURL(resolve(nodeModulesDir, url.slice(1)))
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Must match the MRTway Development Viewer SPA redirect URI
    // (http://localhost:3000/signin-callback).
    port: 3000,
  },
  css: {
    preprocessorOptions: {
      scss: {
        // Silence the large volume of upstream Bentley/Sass deprecation
        // warnings that are internal to the @itwin packages (not our code).
        quietDeps: true,
        silenceDeprecations: ['import', 'global-builtin', 'legacy-js-api'],
        importers: [bentleyTildeImporter],
      },
    },
  },
  optimizeDeps: {
    // The viewer stack is large and pulls deep transitive deps; let Vite
    // pre-bundle them (and include ones it cannot auto-discover from the lazy
    // import graph) so the dev server serves the real viewer cleanly.
    include: [
      '@itwin/web-viewer-react',
      '@itwin/browser-authorization',
      '@itwin/core-frontend',
      '@itwin/core-common',
      '@itwin/core-bentley',
      '@itwin/appui-react',
      '@itwin/components-react',
      '@itwin/imodel-components-react',
      '@itwin/core-react',
      '@itwin/presentation-frontend',
      '@itwin/presentation-common',
      '@itwin/presentation-components',
      '@itwin/ecschema-metadata',
      '@itwin/ecschema-rpcinterface-common',
      '@itwin/core-orbitgt',
    ],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/vitest-setup.ts',
    // Do not load the heavy @itwin viewer stack in unit tests; it is only
    // imported by the lazy LiveItwinViewer, which tests never render.
    exclude: ['**/node_modules/**', '**/dist/**', '**/components/viewer/**'],
  },
})
