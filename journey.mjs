// Giám sát hành trình khách trả phí (THA-3746): landing -> CTA -> /app/draft -> editor tải -> nút xuất bản
// -> cửa đăng nhập -> điều kiện thanh toán. KHÔNG đăng nhập, KHÔNG tạo đơn/thiệp, KHÔNG ghi DB production.
// Dùng:  node journey.mjs            (in JSON kết quả; exit 0 = đạt, 1 = hỏng)
// Env:   LANDING_URL (mặc định https://thanmoi.vn)  APP_URL (mặc định https://app.thanmoi.vn)
//        PROD_APP_ORIGIN (origin mà CTA phải trỏ tới, mặc định https://app.thanmoi.vn)
//        JOURNEY_TEMPLATE (ép mẫu), JOURNEY_RETRY_MS (nghỉ trước lần thử lại, mặc định 45000)
import { chromium } from 'playwright-core'

const LANDING = (process.env.LANDING_URL ?? 'https://thanmoi.vn').replace(/\/$/, '')
const APP = (process.env.APP_URL ?? 'https://app.thanmoi.vn').replace(/\/$/, '')
const PROD_APP = (process.env.PROD_APP_ORIGIN ?? 'https://app.thanmoi.vn').replace(/\/$/, '')
const RETRY_MS = Number(process.env.JOURNEY_RETRY_MS ?? 45000)
// UA chứa "uptime"/"monitor" để bộ lọc bot của Finance (cf_landing.py BOT_RE) loại khỏi số khách thật.
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 ThanMoiUptimeMonitor/1.0'
const MIN_TEMPLATES = 10
const hosts = new Set([new URL(LANDING).host, new URL(APP).host])

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function get(url, init = {}) {
  return fetch(url, { redirect: 'manual', headers: { 'user-agent': UA }, signal: AbortSignal.timeout(20000), ...init })
}
function check(cond, msg) {
  if (!cond) throw new Error(msg)
}

async function stepLanding() {
  const r = await get(`${LANDING}/thiep-tat-nien`)
  check(r.status === 200, `landing /thiep-tat-nien HTTP ${r.status}`)
  const html = await r.text()
  const re = new RegExp(`href="${PROD_APP.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/app/new\\?template=([a-z]\\d{2})"`, 'g')
  const ids = [...new Set([...html.matchAll(re)].map((m) => m[1]))]
  check(ids.length >= MIN_TEMPLATES, `landing chỉ có ${ids.length} nút CTA /app/new?template=… (cần ≥ ${MIN_TEMPLATES}) — CTA gãy hoặc đổi trỏ`)
  return ids
}

async function stepCtaRedirects(ids) {
  const bad = []
  for (const id of ids) {
    const r = await get(`${APP}/app/new?template=${id}`)
    const loc = r.headers.get('location') ?? ''
    if (![301, 302, 303, 307, 308].includes(r.status) || !new RegExp(`/app/draft\\?template=${id}$`).test(loc)) bad.push(`${id}→${r.status} ${loc.slice(0, 60)}`)
  }
  check(bad.length === 0, `CTA không chuyển tới /app/draft: ${bad.slice(0, 3).join('; ')}${bad.length > 3 ? ` (+${bad.length - 3})` : ''}`)
}

async function stepEditor(browser, id) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, userAgent: UA, serviceWorkers: 'block' })
  try {
    // Chặn mọi host ngoài thanmoi (Pixel, analytics…) và beacon phễu: không làm bẩn số đo quảng cáo/funnel_events.
    await ctx.route('**/*', (route) => {
      const u = new URL(route.request().url())
      if (!hosts.has(u.host) || u.pathname.startsWith('/api/funnel') || u.pathname.startsWith('/cdn-cgi/rum')) return route.abort()
      return route.continue()
    })
    const p = await ctx.newPage()
    const jsRes = []
    const badStatic = []
    const errors = []
    p.on('response', (res) => {
      const u = new URL(res.url())
      if (!hosts.has(u.host) || !u.pathname.startsWith('/_next/static/')) return
      if (/\.js$/.test(u.pathname)) jsRes.push(res.status())
      if (res.status() >= 400) badStatic.push(`${res.status()} ${u.pathname.slice(-50)}`)
    })
    p.on('pageerror', (e) => errors.push(`pageerror: ${String(e.message).slice(0, 120)}`))
    p.on('console', (m) => {
      if (m.type() !== 'error') return
      const t = m.text()
      if (/Failed to load resource|net::ERR_|favicon/i.test(t)) return // do ta chặn host ngoài / beacon
      errors.push(`console.error: ${t.slice(0, 120)}`)
    })

    const nav = await p.goto(`${APP}/app/draft?template=${id}`, { waitUntil: 'load', timeout: 30000 })
    check(nav && nav.status() === 200, `/app/draft?template=${id} HTTP ${nav?.status()}`)
    check(jsRes.length >= 3, `editor chỉ tải ${jsRes.length} file JS (bundle không tải)`)
    check(badStatic.length === 0, `file tĩnh editor lỗi: ${badStatic.slice(0, 3).join('; ')}`)
    const tabs = p.getByRole('navigation', { name: 'Phần chỉnh sửa' })
    await p.getByRole('button', { name: 'Mở bảng chỉnh sửa' }).waitFor({ timeout: 20000 }).catch(() => {
      throw new Error('editor trắng trang / không hiện bảng chỉnh sửa sau 20s')
    })
    const frame = p.locator('iframe[title="Xem trước thiệp"]')
    await frame.waitFor({ timeout: 10000 }).catch(() => {
      throw new Error('editor không có khung xem trước thiệp')
    })
    const handle = await frame.elementHandle()
    const inner = await handle.contentFrame()
    await inner.waitForFunction(() => document.body && document.body.innerText.trim().length > 20, null, { timeout: 15000 }).catch(() => {
      throw new Error('khung xem trước thiệp rỗng')
    })

    await p.getByRole('button', { name: 'Mở bảng chỉnh sửa' }).click()
    await tabs.getByRole('button', { name: 'Xuất bản', exact: true }).click().catch(() => {
      throw new Error('không thấy tab "Xuất bản" trong editor')
    })
    await p.getByRole('button', { name: 'Đăng nhập để xuất bản' }).click({ timeout: 8000 }).catch(() => {
      throw new Error('không thấy nút "Đăng nhập để xuất bản" (bước xuất bản của khách ẩn danh)')
    })
    const google = p.locator('[role=dialog] a[href^="/api/auth/google"]')
    await google.waitFor({ timeout: 8000 }).catch(() => {
      throw new Error('cửa đăng nhập không có nút "Tiếp tục với Google"')
    })
    const registerHref = await p.locator('[role=dialog] a[href^="/app/register"]').first().getAttribute('href', { timeout: 3000 }).catch(() => null)
    check(registerHref, 'cửa đăng nhập không có link tạo tài khoản')
    check(errors.length === 0, `lỗi nghiêm trọng trong editor: ${errors.slice(0, 3).join(' | ')}`)
    return { googleHref: await google.first().getAttribute('href'), js: jsRes.length }
  } finally {
    await ctx.close()
  }
}

async function stepAuthAndPay(googleHref) {
  const g = await get(`${APP}${googleHref}`)
  const loc = g.headers.get('location') ?? ''
  check([302, 307].includes(g.status) && loc.startsWith('https://accounts.google.com/'), `Đăng nhập Google: HTTP ${g.status} → ${loc.slice(0, 50) || '(không redirect)'}`)
  for (const path of ['/app/login', '/app/register']) {
    const r = await get(`${APP}${path}`)
    check(r.status === 200, `${path} HTTP ${r.status}`)
  }
  const pr = await get(`${APP}/api/public/pricing`)
  check(pr.status === 200, `/api/public/pricing HTTP ${pr.status}`)
  const kinds = (await pr.json()).kinds ?? {}
  for (const k of ['wedding', 'yearend']) {
    const tiers = kinds[k]
    check(Array.isArray(tiers) && tiers.length > 0 && tiers.every((t) => Number.isInteger(t.price) && t.price > 0 && t.cap > 0), `bảng giá "${k}" rỗng/sai (không tạo được đơn đúng tiền)`)
  }
  // Webhook thu tiền còn sống: không khoá => 401 (từ chối trước khi đụng DB). 404/5xx => thanh toán không ghi nhận được.
  const wh = await get(`${APP}/api/payments/sepay/webhook`, { method: 'POST', headers: { 'user-agent': UA, 'content-type': 'application/json' }, body: '{}' })
  check(wh.status === 401, `webhook thanh toán SePay trả HTTP ${wh.status} (mong 401)`)
}

async function runOnce(browser) {
  const t0 = Date.now()
  const steps = []
  const step = async (name, fn) => {
    const s = Date.now()
    try {
      const out = await fn()
      steps.push({ name, ok: true, ms: Date.now() - s })
      return out
    } catch (e) {
      steps.push({ name, ok: false, ms: Date.now() - s, error: String(e.message ?? e).slice(0, 300) })
      throw e
    }
  }
  let ok = true
  try {
    const ids = await step('landing', stepLanding)
    await step('cta_redirect', () => stepCtaRedirects(ids))
    const id = process.env.JOURNEY_TEMPLATE ?? ids[Math.floor(Date.now() / 3600000) % ids.length]
    const ed = await step(`editor(${id})`, () => stepEditor(browser, id))
    await step('login_pricing_webhook', () => stepAuthAndPay(ed.googleHref))
  } catch {
    ok = false
  }
  return { ok, ms: Date.now() - t0, steps }
}

const browser = await chromium.launch()
let result
try {
  result = await runOnce(browser)
  if (!result.ok) {
    const first = result
    await sleep(RETRY_MS)
    result = await runOnce(browser)
    result.attempts = 2
    result.firstAttempt = first.steps.filter((s) => !s.ok).map((s) => `${s.name}: ${s.error}`)
  } else result.attempts = 1
} finally {
  await browser.close()
}
result.ts = new Date().toISOString()
console.log(JSON.stringify(result))
process.exit(result.ok ? 0 : 1)
