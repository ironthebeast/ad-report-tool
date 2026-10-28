// 로컬 개발 서버: public/ 정적 파일 + api/*.js (Vercel과 동일한 POST(Request) 핸들러)
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
const PORT = process.env.PORT || 3000;

createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  try {
    if (pathname.startsWith('/api/')) {
      const mod = await import(pathToFileURL(join(ROOT, `${pathname}.js`)).href);
      const chunks = [];
      for await (const c of req) chunks.push(c);
      const request = new Request(`http://localhost${req.url}`, {
        method: req.method, headers: req.headers, body: req.method === 'POST' ? Buffer.concat(chunks) : undefined,
      });
      const response = await mod[req.method](request);
      res.writeHead(response.status, Object.fromEntries(response.headers));
      res.end(Buffer.from(await response.arrayBuffer()));
      return;
    }
    const file = join(ROOT, 'public', pathname === '/' ? 'index.html' : pathname);
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch (e) {
    res.writeHead(e.code === 'ENOENT' || e.code === 'ERR_MODULE_NOT_FOUND' ? 404 : 500);
    res.end(String(e.message));
  }
}).listen(PORT, () => console.log(`http://localhost:${PORT}`));
