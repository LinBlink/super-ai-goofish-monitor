import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const OUT = resolve(ROOT, 'docs', 'screenshots')

const BASE_URL = process.env.BASE_URL || 'http://localhost:4173'
const WIDTH = 390
const HEIGHT = 844

// name -> route. `full` captures the entire scrollable page.
const shots = [
  { name: 'dashboard-top', route: '/dashboard', full: false },
  { name: 'dashboard-overview', route: '/dashboard', full: true },
  { name: 'tasks-overview', route: '/tasks', full: false },
  { name: 'results-overview', route: '/results', full: false },
  { name: 'settings-overview', route: '/settings', full: false },
  { name: 'logs-overview', route: '/logs', full: false },
  { name: 'accounts-overview', route: '/accounts', full: false },
]

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: WIDTH, height: HEIGHT },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
})

const page = await context.newPage()

// Bypass the login screen by seeding the same localStorage flags the app reads.
await page.addInitScript(() => {
  localStorage.setItem('auth_logged_in', 'true')
  localStorage.setItem('auth_username', 'admin')
})

for (const shot of shots) {
  try {
    await page.goto(`${BASE_URL}${shot.route}`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    })
  } catch {
    // networkidle may never settle if a backend API is unreachable; proceed anyway.
  }
  await page.waitForTimeout(1000)
  const path = resolve(OUT, `${shot.name}.png`)
  await page.screenshot({ path, fullPage: shot.full })
  console.log(`captured ${shot.name}.png`)
}

await browser.close()
console.log(`done -> ${OUT}`)
