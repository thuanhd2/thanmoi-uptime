// Proxy LOCAL chuyển tiếp tới production (chỉ GET/HEAD + webhook POST không khoá) và cố ý làm hỏng MỘT bước,
// để kiểm monitor có báo đỏ. Không sửa gì trên production. Dùng: FAULT=<tên> node test/fault-proxy.mjs
// FAULT: none | cta | cta_redirect | editor_js | editor_blank | publish | google | pricing | webhook
// In ra 2 dòng env: LANDING_URL=… APP_URL=… rồi chạy tiếp tới khi bị kill.
import http from 'node:http'

const FAULT = process.env.FAULT ?? 'none'
const PROD_LANDING = 'https://thanmoi.vn'
const PROD_APP = 'https://app.thanmoi.vn'

function serve(upstream, port, selfOrigin, rewrites) {
  return new Promise((resolve) => {
    const srv = http.createServer(async (req, res) => {
      const u = new URL(req.url, upstream)
      if (req.method !== 'GET' && req.method !== 'HEAD' && !(req.method === 'POST' && u.pathname === '/api/payments/sepay/webhook')) {
        res.writeHead(405).end()
        return
      }
      if (FAULT === 'cta_redirect' && u.pathname === '/app/new') return res.writeHead(404).end('fault')
      if (FAULT === 'editor_js' && /^\/_next\/static\/chunks\/.*\.js$/.test(u.pathname) && /(app|main|page)/.test(u.pathname)) return res.writeHead(500).end('fault')
      if (FAULT === 'google' && u.pathname === '/api/auth/google') return res.writeHead(500).end('fault')
      if (FAULT === 'pricing' && u.pathname === '/api/public/pricing') return res.writeHead(200, { 'content-type': 'application/json' }).end('{"kinds":{}}')
      if (FAULT === 'webhook' && u.pathname === '/api/payments/sepay/webhook') return res.writeHead(502).end('fault')
      const body = req.method === 'POST' ? '{}' : undefined
      const up = await fetch(u, { method: req.method, body, redirect: 'manual', headers: { 'user-agent': req.headers['user-agent'] ?? '', 'accept-encoding': 'identity', 'content-type': req.headers['content-type'] ?? 'text/html' } })
      const type = up.headers.get('content-type') ?? ''
      const headers = Object.fromEntries([...up.headers].filter(([k]) => !['content-encoding', 'content-length', 'transfer-encoding', 'content-security-policy'].includes(k)))
      if (headers.location) headers.location = headers.location.replace(PROD_APP, ORIGINS.app).replace(PROD_LANDING, ORIGINS.landing)
      if (/text|javascript|json/.test(type)) {
        let t = await up.text()
        t = t.split(PROD_APP).join(ORIGINS.app).split(PROD_LANDING).join(ORIGINS.landing)
        for (const [from, to, pathRe] of rewrites) if (pathRe.test(u.pathname)) t = t.split(from).join(to)
        res.writeHead(up.status, headers).end(t)
      } else res.writeHead(up.status, headers).end(Buffer.from(await up.arrayBuffer()))
    })
    srv.listen(port, '127.0.0.1', () => resolve(srv))
  })
}

const ORIGINS = { landing: 'http://127.0.0.1:3901', app: 'http://127.0.0.1:3902' }
await serve(PROD_LANDING, 3901, ORIGINS.landing, FAULT === 'cta' ? [['/app/new?template=', '/app/neww?template=', /^\/thiep-tat-nien/]] : [])
await serve(PROD_APP, 3902, ORIGINS.app, [
  ...(FAULT === 'publish' ? [['Đăng nhập để xuất bản', 'Xuất bản ngay', /\.js$/]] : []),
  ...(FAULT === 'editor_blank' ? [['Xem trước thiệp', 'Xem truoc', /./]] : []),
])
console.log(`LANDING_URL=${ORIGINS.landing} APP_URL=${ORIGINS.app} FAULT=${FAULT}`)
