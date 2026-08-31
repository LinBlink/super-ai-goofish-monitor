import sys
import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='zh-CN')
    page = ctx.new_page()
    page.goto('http://127.0.0.1:8000/', timeout=20000)
    page.evaluate('localStorage.setItem("auth_username", "admin"); localStorage.setItem("auth_logged_in", "true");')
    page.goto('http://127.0.0.1:8000/dashboard', timeout=20000)
    time.sleep(5)
    page.screenshot(path='docs/screenshots/dashboard-overview.png', full_page=True)
    page.screenshot(path='docs/screenshots/dashboard-top.png')
    print('DASHBOARD URL:', page.url)

    # 任务管理页
    page.goto('http://127.0.0.1:8000/tasks', timeout=20000)
    time.sleep(3)
    page.screenshot(path='docs/screenshots/tasks-overview.png')

    # 结果查看
    page.goto('http://127.0.0.1:8000/results', timeout=20000)
    time.sleep(3)
    page.screenshot(path='docs/screenshots/results-overview.png')

    # 系统设置
    page.goto('http://127.0.0.1:8000/settings', timeout=20000)
    time.sleep(3)
    page.screenshot(path='docs/screenshots/settings-overview.png')

    # 运行日志
    page.goto('http://127.0.0.1:8000/logs', timeout=20000)
    time.sleep(3)
    page.screenshot(path='docs/screenshots/logs-overview.png')

    # 账号管理
    page.goto('http://127.0.0.1:8000/accounts', timeout=20000)
    time.sleep(3)
    page.screenshot(path='docs/screenshots/accounts-overview.png')

    # 登录页（先清掉认证）
    page.evaluate('localStorage.clear()')
    page.goto('http://127.0.0.1:8000/login', timeout=20000)
    time.sleep(2)
    page.screenshot(path='docs/screenshots/login.png')

    browser.close()
print('OK')
