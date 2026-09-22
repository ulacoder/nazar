// Builds the hosted (Vercel) UI: the dashboard as static files that talk to a local NAZAR backend.
// Usage: node scripts/build_static.mjs  (NAZAR_API_DEFAULT overrides the backend URL, default http://127.0.0.1:8000)
import {cpSync, mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';

const out = 'dist';
const api = process.env.NAZAR_API_DEFAULT || 'http://127.0.0.1:8000';
rmSync(out, {recursive: true, force: true});
mkdirSync(out, {recursive: true});
cpSync('app/static', `${out}/static`, {recursive: true});

let html = readFileSync('app/templates/index.html', 'utf8')
  .replace(/\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}/g, 'static/$1');
if (html.includes('{{') || html.includes('{%')) throw new Error('Unhandled Jinja syntax in index.html');
html = html.replace('<head>', `<head>\n  <script>window.NAZAR_API_DEFAULT=${JSON.stringify(api)};</script>`);
writeFileSync(`${out}/index.html`, html);
console.log(`Built ${out}/ (backend: ${api})`);
