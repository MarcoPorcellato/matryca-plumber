/**
 * Preload for `gitnexus analyze --embeddings` when gitnexus is installed globally
 * under /usr/local (root-owned). transformers.js defaults to a package-local
 * `.cache/` that is not writable; this redirects to HF_HOME or ~/.cache/huggingface.
 *
 * Usage:
 *   NODE_OPTIONS="--import ./scripts/gitnexus-hf-cache.mjs" gitnexus analyze --embeddings
 */
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';

const gitnexusRoot =
  process.env.GITNEXUS_MODULE_ROOT ?? '/usr/local/lib/node_modules/gitnexus';

try {
  const require = createRequire(join(gitnexusRoot, 'package.json'));
  const transformersEntry = require.resolve('@huggingface/transformers');
  const transformersMjs = transformersEntry.replace(/\.cjs$/, '.mjs');
  const { env } = await import(transformersMjs);
  const cacheDir = process.env.HF_HOME ?? join(homedir(), '.cache', 'huggingface');
  env.cacheDir = cacheDir;
  env.useFSCache = true;
  env.useBrowserCache = false;
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.warn(`gitnexus-hf-cache: could not set transformers cacheDir: ${message}`);
}
