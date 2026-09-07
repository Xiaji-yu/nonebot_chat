import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('Usage: node scripts/render-diagram.mjs <input.mmd> <output.svg>');
  process.exit(1);
}

const [inputFile, outputFile] = args;

// Setup DOM for mermaid via jsdom
const { JSDOM } = await import('jsdom');
const { window } = new JSDOM('<!DOCTYPE html><html><body><div id="container"></div></body></html>');
global.document = window.document;
global.window = window;
global.CSSStyleSheet = window.CSSStyleSheet;

const mermaid = await import('mermaid');

async function main() {
  mermaid.default.initialize({
    startOnLoad: false,
    theme: 'default',
  });

  const definition = readFileSync(join(projectRoot, inputFile), 'utf8');
  const uniqueId = 'mermaid-' + Date.now();
  const { svg } = await mermaid.default.render(uniqueId, definition);
  writeFileSync(join(projectRoot, outputFile), svg, 'utf8');
  console.log(`Rendered ${inputFile} -> ${outputFile}`);
}

main().catch((err) => {
  console.error('Render failed:', err);
  process.exit(1);
});
