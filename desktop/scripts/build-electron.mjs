/**
 * Bundles the Electron main and preload scripts.
 *
 * Both emit `.cjs` because package.json declares `"type": "module"`, while
 * Electron's main process and a sandboxed preload must both be CommonJS.
 */
import { build } from 'esbuild';
import { rmSync } from 'node:fs';

rmSync('dist-electron', { recursive: true, force: true });

const shared = {
  bundle: true,
  platform: 'node',
  target: 'node20',
  format: 'cjs',
  sourcemap: true,
  // Electron is provided by the runtime, not bundled into the output.
  external: ['electron'],
  logLevel: 'info',
};

await build({ ...shared, entryPoints: ['electron/main.ts'], outfile: 'dist-electron/main.cjs' });
await build({
  ...shared,
  entryPoints: ['electron/preload.ts'],
  outfile: 'dist-electron/preload.cjs',
});

console.log('electron main + preload bundled -> dist-electron/');
