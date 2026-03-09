#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为测试清单「需数据」项生成数据：通知、发现条目、兑换码；并为一名测试用户写入订阅与密码，便于密码登录验证。
用法：在项目根目录执行 python3 scripts/seed_test_data.py（需能访问 BASE_URL 与本地 BAOSHUI_DB）。
依赖：pip install requests。"""
import os
import sys
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# 与 server 一致
TOKEN_SECRET = os.environ.get('BAOSHUI_SECRET', 'baoshui-dev-secret')
BAOSHUI_DB = os.environ.get('BAOSHUI_DB', os.path.join(ROOT, 'data', 'baoshui.db'))
BASE_URL = os.environ.get('BAOSHUI_BASE_URL', 'https://me.gaoxin.xin/baoshui')


def _password_hash(password, salt_secret):
    return hashlib.pbkdf2_hmac(
        'sha256', (password or '').encode('utf-8'),
        (salt_secret or 'baoshui').encode('utf-8'), 100000
    ).hex()


def main():
    try:
        import requests
    except ImportError:
        print('需要 requests: pip install requests')
        sys.exit(1)

    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})

    # 1) 后台登录
    r = session.post(f'{BASE_URL}/api/admin/login', json={'password': '123456'})
    if r.status_code != 200 or r.json().get('code') != 0:
        print('后台登录失败:', r.status_code, r.text)
        sys.exit(1)
    token = r.json().get('token', '')
    session.headers.update({'Authorization': f'Bearer {token}'})

    # 2) 发一条通知（指定手机号，便于单用户验证）
    phone = None
    conn = sqlite3.connect(BAOSHUI_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.execute('SELECT phone FROM users LIMIT 1')
    row = cur.fetchone()
    if row:
        phone = row['phone']
    conn.close()
    if not phone:
        phone = ''
    r = session.post(f'{BASE_URL}/api/admin/notifications', json={
        'title': '【测试】系统通知',
        'content': '这是一条测试通知，用于验证「我的通知」列表展示。',
        'phone': phone or None
    })
    if r.status_code != 200 or r.json().get('code') != 0:
        print('创建通知失败:', r.status_code, r.text)
    else:
        print('已创建通知', '(指定手机:' + phone + ')' if phone else '(全员)')

    # 3) 添加发现条目
    r = session.post(f'{BASE_URL}/api/admin/discover', json={
        'title': '测试发现条目',
        'link_url': 'https://me.gaoxin.xin/baoshui/pricing.html',
        'sort_order': 0
    })
    if r.status_code != 200 or r.json().get('code') != 0:
        print('添加发现失败:', r.status_code, r.text)
    else:
        print('已添加发现条目')

    # 4) 创建兑换码（小规模、有业务、12 个月）
    code = 'TESTCODE' + datetime.now().strftime('%H%M%S')
    r = session.post(f'{BASE_URL}/api/admin/redemption-codes', json={
        'code': code,
        'tax_type': 'small',
        'biz_type': 'with',
        'duration': 12
    })
    if r.status_code != 200 or r.json().get('code') != 0:
        print('创建兑换码失败:', r.status_code, r.text)
    else:
        print('已创建兑换码:', code, '(小规模/有业务/12月)')

    # 5) 直接写 DB：为一名用户设置密码 123456，并为其一个企业写入正式版订阅
    conn = sqlite3.connect(BAOSHUI_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.execute('SELECT phone FROM users LIMIT 1')
    row = cur.fetchone()
    if not row:
        conn.close()
        print('无用户，跳过订阅与密码设置')
        return
    test_phone = row['phone']
    pw_hash = _password_hash('123456', TOKEN_SECRET)
    conn.execute("UPDATE users SET password = ? WHERE phone = ?", (pw_hash, test_phone))
    # 取该用户的一个企业 id（companies 表或注册企业 id=0；subscriptions 里 company_id 为字符串）
    cur = conn.execute('SELECT id FROM companies WHERE phone = ? ORDER BY id LIMIT 1', (test_phone,))
    company_row = cur.fetchone()
    if company_row:
        cid = str(company_row['id'])
    else:
        cid = '0'  # 注册时企业
    expires = (datetime.utcnow() + timedelta(days=365)).strftime('%Y-%m-%d')
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        'INSERT OR REPLACE INTO subscriptions (phone, company_id, expires_at, updated_at) VALUES (?, ?, ?, ?)',
        (test_phone, cid, expires, now_str)
    )
    conn.commit()
    conn.close()
    print('已为测试用户', test_phone, '设置密码 123456，并写入正式版订阅(企业id=%s, 到期%s)' % (cid, expires))
    print('可从前台「密码登录」使用该手机号 + 密码 123456 登录，验证：我的通知、发现、开通正式版卡片。')


if __name__ == '__main__':
    main()
