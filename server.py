#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自报税 - 后端 API（登录/验证码）"""
import os
import re
import sys
import sqlite3
from urllib.parse import quote
import random
import string
import time
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

# 验证码配置从 payroll 查找（支持 /opt/payroll 或 /root/payroll）
_PAYROLL_PATHS = [p for p in ['/opt/payroll', '/root/payroll'] if os.path.isdir(p)]
if _PAYROLL_PATHS:
    _payroll_root = _PAYROLL_PATHS[0]
    if _payroll_root not in sys.path:
        sys.path.insert(0, _payroll_root)

app = Flask(__name__, static_folder='.', static_url_path='')

# 内存存储验证码（生产环境应使用 Redis 等）
_sms_codes = {}  # {phone: (code, expires_at)}
TOKEN_SECRET = os.environ.get('BAOSHUI_SECRET', 'baoshui-dev-secret')
BAOSHUI_DB = os.environ.get('BAOSHUI_DB', os.path.join(os.path.dirname(__file__), 'data', 'baoshui.db'))
UPLOAD_DIR = os.environ.get('BAOSHUI_UPLOAD_DIR', os.path.join(os.path.dirname(__file__), 'data', 'uploads'))
ADMIN_PASSWORD = os.environ.get('BAOSHUI_ADMIN_PASSWORD', '123456')
_admin_tokens = set()  # 内存存储后台登录 token，重启清空


def _get_db():
    os.makedirs(os.path.dirname(BAOSHUI_DB) or '.', exist_ok=True)
    conn = sqlite3.connect(BAOSHUI_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    db = _get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        company_name TEXT DEFAULT '',
        password TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    try:
        db.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
        if 'password' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN password TEXT DEFAULT ''")
    except Exception:
        pass
    db.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        phone TEXT NOT NULL,
        expires_at REAL NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        name TEXT NOT NULL,
        legal_person TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS company_settings (
        phone TEXT NOT NULL,
        company_id TEXT NOT NULL,
        bookkeeping_method TEXT DEFAULT '',
        tax_ukey_type TEXT DEFAULT '',
        tax_bureau_website TEXT DEFAULT '',
        tax_bureau_login_method TEXT DEFAULT '',
        tax_bureau_legal_id TEXT DEFAULT '',
        tax_bureau_legal_password TEXT DEFAULT '',
        tax_bureau_verified INTEGER DEFAULT 0,
        personal_tax_account TEXT DEFAULT '',
        personal_tax_password TEXT DEFAULT '',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (phone, company_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS redemption_codes (
        code TEXT PRIMARY KEY,
        tax_type TEXT NOT NULL,
        biz_type TEXT NOT NULL,
        duration INTEGER NOT NULL,
        used_at TEXT,
        used_by_phone TEXT,
        used_by_company_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        phone TEXT NOT NULL,
        company_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (phone, company_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ledger_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ledger_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        company_id TEXT NOT NULL,
        period TEXT NOT NULL,
        type TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        remark TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ledger_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS tax_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        company_id TEXT NOT NULL,
        period TEXT NOT NULL,
        tax_type TEXT NOT NULL,
        status TEXT DEFAULT 'done',
        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        phone TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT DEFAULT '',
        PRIMARY KEY (phone, key)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS site_config (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY,
        discount_type TEXT NOT NULL,
        discount_value REAL NOT NULL,
        valid_from TEXT,
        valid_until TEXT,
        used_at TEXT,
        used_by_phone TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        direction TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS discover_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        link_url TEXT DEFAULT '',
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS admin_sessions (
        token TEXT PRIMARY KEY,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    # 初始化默认收支分类
    if db.execute('SELECT COUNT(*) FROM ledger_categories').fetchone()[0] == 0:
        defaults = [
            ('销售收入', 'income', 1), ('其他收入', 'income', 2),
            ('采购支出', 'expense', 1), ('费用支出', 'expense', 2), ('工资薪金', 'expense', 3), ('其他支出', 'expense', 4)
        ]
        for name, t, so in defaults:
            db.execute('INSERT INTO ledger_categories (name, type, sort_order) VALUES (?, ?, ?)', (name, t, so))
    db.commit()
    db.close()


def _password_hash(password, salt_secret):
    return hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), (salt_secret or 'baoshui').encode('utf-8'), 100000).hex()


def _password_verify(password, stored_hash, salt_secret):
    if not stored_hash:
        return False
    return _password_hash(password, salt_secret) == stored_hash


def _normalize_phone(raw):
    raw = (raw or '').strip().replace(' ', '').replace('-', '')
    if raw.startswith('+86'):
        raw = raw[3:].strip()
    return raw if re.match(r'^1[3-9]\d{9}$', raw) else None


def _send_sms_via_payroll(phone, code):
    """使用 payroll 的腾讯云短信配置发送验证码"""
    try:
        from utils.sms import sms_client
        result = sms_client.send_code(phone, str(code))
        if result.get('success'):
            return True, None
        return False, result.get('error', '发送失败')
    except Exception as e:
        return False, str(e)


@app.route('/api/sms/send', methods=['POST'])
def send_sms():
    """发送验证码（使用 payroll 配置的腾讯云短信）"""
    data = request.get_json() or {}
    phone = _normalize_phone(data.get('phone', ''))
    if not phone:
        return jsonify({'code': 400, 'message': '手机号无效，请填写 11 位手机号'}), 400

    # 60 秒限频
    if phone in _sms_codes:
        _, exp = _sms_codes[phone]
        if time.time() < exp - 540:  # 60s 内
            return jsonify({'code': 400, 'message': '发送太频繁，请 60 秒后再试'}), 400

    code = ''.join(random.choices(string.digits, k=6))
    expires_at = time.time() + 600  # 10 分钟
    _sms_codes[phone] = (code, expires_at)

    # 使用 payroll 配置真实发送
    if _PAYROLL_PATHS:
        ok, err = _send_sms_via_payroll(phone, code)
        if not ok:
            app.logger.warning('[sms] 发送失败 phone=%s*** err=%s', phone[:3], err)
            return jsonify({'code': 500, 'message': err or '验证码发送失败，请稍后重试'}), 500
    else:
        app.logger.info('[sms] 未找到 payroll，控制台输出 phone=%s*** code=%s', phone[:3], code)
        print('[baoshui] 验证码 %s*** -> %s' % (phone[:3], code))

    return jsonify({'code': 0, 'message': '验证码已发送'})


def _verify_token(token):
    """验证 token，返回 phone 或 None"""
    if not token:
        return None
    db = _get_db()
    try:
        row = db.execute(
            'SELECT phone FROM sessions WHERE token = ? AND expires_at > ?',
            (token, time.time())
        ).fetchone()
        return row['phone'] if row else None
    finally:
        db.close()


def _user_owns_company(phone, company_id):
    """当前用户是否拥有该企业：company_id 在 companies 表或为 '0'（users 合并的原企业）"""
    if not phone or company_id is None or company_id == '':
        return False
    db = _get_db()
    try:
        if company_id == '0':
            return True
        row = db.execute('SELECT id FROM companies WHERE phone = ? AND id = ?', (phone, company_id)).fetchone()
        return row is not None
    finally:
        db.close()


def _do_login_success(phone):
    """登录成功：生成 token、查用户信息"""
    raw = '%s:%s:%s' % (phone, TOKEN_SECRET, time.time())
    token = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = time.time() + 30 * 24 * 3600  # 30 天

    db = _get_db()
    try:
        db.execute('INSERT OR REPLACE INTO sessions (token, phone, expires_at) VALUES (?, ?, ?)',
                   (token, phone, expires_at))
        row = db.execute('SELECT company_name FROM users WHERE phone = ?', (phone,)).fetchone()
        company_name = (row['company_name'] or '').strip() if row else ''
        if not row:
            db.execute('INSERT OR IGNORE INTO users (phone, company_name) VALUES (?, ?)', (phone, ''))
        db.commit()
    finally:
        db.close()

    return token, company_name


@app.route('/api/auth/register', methods=['POST'])
def register():
    """注册：手机号 + 验证码 + 设置密码"""
    _init_db()
    data = request.get_json() or {}
    phone = _normalize_phone(data.get('phone', ''))
    code = (data.get('code') or '').strip()
    password = (data.get('password') or '').strip()

    if not phone:
        return jsonify({'code': 400, 'message': '请输入 11 位手机号'}), 400
    if not code or not code.isdigit():
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    if not password or len(password) < 6:
        return jsonify({'code': 400, 'message': '请设置 6 位以上登录密码'}), 400

    if phone not in _sms_codes:
        return jsonify({'code': 400, 'message': '验证码错误或已过期，请重新获取'}), 400

    stored_code, expires_at = _sms_codes[phone]
    if time.time() > expires_at:
        del _sms_codes[phone]
        return jsonify({'code': 400, 'message': '验证码已过期，请重新获取'}), 400

    if code != stored_code:
        return jsonify({'code': 400, 'message': '验证码错误，请核对后重试'}), 400

    del _sms_codes[phone]

    db = _get_db()
    try:
        row = db.execute('SELECT phone FROM users WHERE phone = ?', (phone,)).fetchone()
        if row:
            return jsonify({'code': 400, 'message': '该手机号已注册，请直接登录'}), 400

        pw_hash = _password_hash(password, TOKEN_SECRET)
        db.execute('INSERT INTO users (phone, company_name, password) VALUES (?, ?, ?)', (phone, '', pw_hash))
        db.commit()
    finally:
        db.close()

    token, company_name = _do_login_success(phone)
    return jsonify({
        'code': 0,
        'message': '注册成功',
        'token': token,
        'user': {'phone': phone, 'name': '', 'company_name': company_name},
        'need_company_name': True
    })


@app.route('/api/auth/login', methods=['POST'])
def login():
    """登录：支持验证码登录、密码登录两种方式；账号不限制格式。"""
    _init_db()
    data = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    password = (data.get('password') or '').strip()

    if not phone:
        return jsonify({'code': 400, 'message': '请输入账号'}), 400

    # 密码登录
    if password:
        db = _get_db()
        try:
            row = db.execute('SELECT phone, company_name, password FROM users WHERE phone = ?', (phone,)).fetchone()
            if not row:
                return jsonify({'code': 400, 'message': '该账号未注册，请先注册'}), 400
            stored_hash = (row['password'] or '').strip()
            if not _password_verify(password, stored_hash, TOKEN_SECRET):
                return jsonify({'code': 400, 'message': '密码错误'}), 400
            company_name = (row['company_name'] or '').strip()
        finally:
            db.close()
        token, _ = _do_login_success(phone)
        return jsonify({
            'code': 0,
            'message': '登录成功',
            'token': token,
            'user': {'phone': phone, 'name': '', 'company_name': company_name},
            'need_company_name': not company_name
        })

    # 验证码登录
    if not code or not code.isdigit():
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400

    if phone not in _sms_codes:
        return jsonify({'code': 400, 'message': '验证码错误或已过期，请重新获取'}), 400

    stored_code, expires_at = _sms_codes[phone]
    if time.time() > expires_at:
        del _sms_codes[phone]
        return jsonify({'code': 400, 'message': '验证码已过期，请重新获取'}), 400

    if code != stored_code:
        return jsonify({'code': 400, 'message': '验证码错误，请核对后重试'}), 400

    del _sms_codes[phone]
    token, company_name = _do_login_success(phone)
    return jsonify({
        'code': 0,
        'message': '登录成功',
        'token': token,
        'user': {'phone': phone, 'name': '', 'company_name': company_name},
        'need_company_name': not company_name
    })


@app.route('/api/user/company-name', methods=['POST'])
def update_company_name():
    """注册后填写公司名称"""
    _init_db()
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    company_name = (data.get('company_name') or '').strip()

    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_name:
        return jsonify({'code': 400, 'message': '请输入公司名称'}), 400

    db = _get_db()
    try:
        db.execute(
            'INSERT INTO users (phone, company_name, updated_at) VALUES (?, ?, datetime("now")) '
            'ON CONFLICT(phone) DO UPDATE SET company_name = ?, updated_at = datetime("now")',
            (phone, company_name, company_name)
        )
        db.execute(
            'INSERT INTO companies (phone, name, legal_person) VALUES (?, ?, ?)',
            (phone, company_name, '')
        )
        db.commit()
    finally:
        db.close()

    return jsonify({
        'code': 0,
        'message': '公司名称已保存',
        'user': {'phone': phone, 'company_name': company_name}
    })


@app.route('/api/user/companies', methods=['GET'])
def list_companies():
    """当前用户的企业列表（需登录）"""
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    db = _get_db()
    try:
        rows = db.execute(
            'SELECT id, name, legal_person FROM companies WHERE phone = ? ORDER BY id',
            (phone,)
        ).fetchall()
        list_ = [{'id': str(r['id']), 'name': r['name'] or '', 'legalPerson': r['legal_person'] or ''} for r in rows]
        # 合并 users 表中的 company_name，避免添加企业后原来的企业消失
        user_row = db.execute('SELECT company_name FROM users WHERE phone = ?', (phone,)).fetchone()
        if user_row and (user_row['company_name'] or '').strip():
            name = (user_row['company_name'] or '').strip()
            if not any((c.get('name') or '') == name for c in list_):
                list_.insert(0, {'id': '0', 'name': name, 'legalPerson': ''})
        return jsonify({'code': 0, 'data': list_})
    finally:
        db.close()


@app.route('/api/user/companies', methods=['POST'])
def add_company():
    """添加企业（需登录）"""
    _init_db()
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    name = (data.get('name') or '').strip()
    legal_person = (data.get('legal_person') or data.get('legalPerson') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not name:
        return jsonify({'code': 400, 'message': '请输入企业/个体户全称'}), 400
    db = _get_db()
    try:
        db.execute('INSERT INTO companies (phone, name, legal_person) VALUES (?, ?, ?)', (phone, name, legal_person))
        db.commit()
        cid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'code': 0, 'message': '添加成功', 'data': {'id': str(cid), 'name': name, 'legalPerson': legal_person}})
    finally:
        db.close()


@app.route('/api/user/companies/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    """修改企业（需登录，仅限本人）"""
    _init_db()
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not _user_owns_company(phone, str(company_id)):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    if company_id == 0:
        return jsonify({'code': 400, 'message': '默认企业请通过个人资料修改'}), 400
    name = (data.get('name') or data.get('company_name') or '').strip()
    legal_person = (data.get('legal_person') or data.get('legalPerson') or '').strip()
    if not name:
        return jsonify({'code': 400, 'message': '请输入企业名称'}), 400
    db = _get_db()
    try:
        cur = db.execute('UPDATE companies SET name = ?, legal_person = ? WHERE id = ? AND phone = ?',
                        (name, legal_person, company_id, phone))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({'code': 404, 'message': '企业不存在'}), 404
        return jsonify({'code': 0, 'message': '修改成功', 'data': {'id': str(company_id), 'name': name, 'legalPerson': legal_person}})
    finally:
        db.close()


def _do_delete_company(phone, company_id):
    """执行删除企业（company_id 为 int；0 表示 users 表里的那条，只清 company_name 和 settings）"""
    db = _get_db()
    try:
        if company_id == 0:
            db.execute("UPDATE users SET company_name = '' WHERE phone = ?", (phone,))
            db.commit()
        else:
            db.execute('DELETE FROM companies WHERE id = ? AND phone = ?', (company_id, phone))
            db.commit()
        db.execute('DELETE FROM company_settings WHERE phone = ? AND company_id = ?', (phone, str(company_id)))
        db.commit()
        return True
    finally:
        db.close()


@app.route('/api/user/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    """删除企业（需登录，仅限本人）"""
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not _user_owns_company(phone, str(company_id)):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    _do_delete_company(phone, company_id)
    return jsonify({'code': 0, 'message': '已删除'})


@app.route('/api/user/companies/<int:company_id>/delete', methods=['POST'])
def delete_company_post(company_id):
    """删除企业（POST 路径带 id，部分代理可能仍 405）"""
    _init_db()
    token = (request.get_json(silent=True) or {}).get('token') or (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not _user_owns_company(phone, str(company_id)):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    _do_delete_company(phone, company_id)
    return jsonify({'code': 0, 'message': '已删除'})


def _delete_company_by_body_impl():
    """删除企业逻辑：body 或 header 的 token，body 的 company_id。"""
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    try:
        company_id = int((data.get('company_id') or data.get('companyId') or '').strip())
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '缺少 company_id'}), 400
    if not _user_owns_company(phone, str(company_id)):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    _do_delete_company(phone, company_id)
    return jsonify({'code': 0, 'message': '已删除'})


@app.route('/api/user/companies/delete', methods=['POST'])
def delete_company_by_body():
    """删除企业（POST body 传 company_id）"""
    _init_db()
    return _delete_company_by_body_impl()


@app.route('/api/user/company-remove', methods=['POST'])
def company_remove():
    """删除企业（备用路径，不含 delete 字样，避免代理/WAF 对 POST .../delete 返回 405）"""
    _init_db()
    return _delete_company_by_body_impl()


@app.route('/api/company/settings', methods=['GET'])
def get_company_settings():
    """获取当前企业的设置（需登录，按企业绑定）"""
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 400, 'message': '请选择企业'}), 400
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        row = db.execute(
            'SELECT bookkeeping_method, tax_ukey_type, tax_bureau_website, tax_bureau_login_method, '
            'tax_bureau_legal_id, tax_bureau_legal_password, tax_bureau_verified, personal_tax_account, personal_tax_password, updated_at '
            'FROM company_settings WHERE phone = ? AND company_id = ?',
            (phone, company_id)
        ).fetchone()
        if not row:
            return jsonify({'code': 0, 'data': {}})
        data = {
            'bookkeeping_method': row['bookkeeping_method'] or '',
            'tax_ukey_type': row['tax_ukey_type'] or '',
            'tax_bureau_website': row['tax_bureau_website'] or '',
            'tax_bureau_login_method': row['tax_bureau_login_method'] or '',
            'tax_bureau_legal_id': row['tax_bureau_legal_id'] or '',
            'tax_bureau_legal_password': '******' if (row['tax_bureau_legal_password'] or '') else '',
            'tax_bureau_verified': row['tax_bureau_verified'] or 0,
            'personal_tax_account': row['personal_tax_account'] or '',
            'personal_tax_password': '******' if (row['personal_tax_password'] or '') else '',
            'updated_at': row['updated_at'] or '',
        }
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/company/settings', methods=['POST'])
def save_company_settings():
    """保存当前企业的设置（需登录，按企业绑定）"""
    _init_db()
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    company_id = (data.get('company_id') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 400, 'message': '请选择企业'}), 400
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        existing = db.execute(
            'SELECT bookkeeping_method, tax_ukey_type, tax_bureau_website, tax_bureau_login_method, '
            'tax_bureau_legal_id, tax_bureau_legal_password, tax_bureau_verified, personal_tax_account, personal_tax_password '
            'FROM company_settings WHERE phone = ? AND company_id = ?', (phone, company_id)
        ).fetchone()
        defaults = {
            'bookkeeping_method': '', 'tax_ukey_type': '', 'tax_bureau_website': '', 'tax_bureau_login_method': '',
            'tax_bureau_legal_id': '', 'tax_bureau_legal_password': '', 'tax_bureau_verified': 0,
            'personal_tax_account': '', 'personal_tax_password': '',
        }
        if existing:
            defaults = {k: (existing[k] if existing[k] is not None else '') for k in defaults}
            if defaults.get('tax_bureau_verified') is None:
                defaults['tax_bureau_verified'] = 0
        for key in ('bookkeeping_method', 'tax_ukey_type', 'tax_bureau_website', 'tax_bureau_login_method',
                    'tax_bureau_legal_id', 'tax_bureau_legal_password', 'tax_bureau_verified', 'personal_tax_account', 'personal_tax_password'):
            if key in data:
                if key == 'tax_bureau_verified':
                    defaults[key] = 1 if data.get(key) else 0
                else:
                    val = (data.get(key) or '').strip()
                    if key == 'tax_bureau_legal_password' and val == '******':
                        continue
                    if key == 'personal_tax_password' and val == '******':
                        continue
                    defaults[key] = val
        if existing:
            db.execute('''UPDATE company_settings SET
                bookkeeping_method=?, tax_ukey_type=?, tax_bureau_website=?, tax_bureau_login_method=?,
                tax_bureau_legal_id=?, tax_bureau_legal_password=?, tax_bureau_verified=?,
                personal_tax_account=?, personal_tax_password=?, updated_at=datetime('now')
                WHERE phone=? AND company_id=?''',
                (defaults['bookkeeping_method'], defaults['tax_ukey_type'], defaults['tax_bureau_website'], defaults['tax_bureau_login_method'],
                 defaults['tax_bureau_legal_id'], defaults['tax_bureau_legal_password'], defaults['tax_bureau_verified'],
                 defaults['personal_tax_account'], defaults['personal_tax_password'], phone, company_id))
        else:
            db.execute('''INSERT INTO company_settings (phone, company_id, bookkeeping_method, tax_ukey_type, tax_bureau_website,
                tax_bureau_login_method, tax_bureau_legal_id, tax_bureau_legal_password, tax_bureau_verified,
                personal_tax_account, personal_tax_password) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (phone, company_id, defaults['bookkeeping_method'], defaults['tax_ukey_type'], defaults['tax_bureau_website'],
                 defaults['tax_bureau_login_method'], defaults['tax_bureau_legal_id'], defaults['tax_bureau_legal_password'], defaults['tax_bureau_verified'],
                 defaults['personal_tax_account'], defaults['personal_tax_password']))
        db.commit()
        return jsonify({'code': 0, 'message': '保存成功'})
    finally:
        db.close()


@app.route('/api/company/settings/status')
def company_settings_status():
    """获取当前企业四项设置是否已保存（用于首页显示「修改」）"""
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 0, 'data': {'bookkeeping_method': False, 'tax_ukey': False, 'tax_bureau': False, 'personal_tax': False}})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 0, 'data': {'bookkeeping_method': False, 'tax_ukey': False, 'tax_bureau': False, 'personal_tax': False}})
    db = _get_db()
    try:
        row = db.execute(
            'SELECT bookkeeping_method, tax_ukey_type, tax_bureau_legal_id, personal_tax_account FROM company_settings WHERE phone = ? AND company_id = ?',
            (phone, company_id)
        ).fetchone()
        if not row:
            return jsonify({'code': 0, 'data': {'bookkeeping_method': False, 'tax_ukey': False, 'tax_bureau': False, 'personal_tax': False}})
        return jsonify({
            'code': 0,
            'data': {
                'bookkeeping_method': bool((row['bookkeeping_method'] or '').strip()),
                'tax_ukey': bool((row['tax_ukey_type'] or '').strip()),
                'tax_bureau': bool((row['tax_bureau_legal_id'] or '').strip()),
                'personal_tax': bool((row['personal_tax_account'] or '').strip()),
            }
        })
    finally:
        db.close()


def _verify_admin():
    """验证后台 token，成功返回 True，失败返回 (json_response, status_code)。token 存在内存或 DB 均有效。"""
    auth = (request.headers.get('Authorization') or '').strip().replace('Bearer ', '')
    data = request.get_json(silent=True) or {}
    token = auth or (data.get('admin_token') or data.get('token') or '').strip()
    if not token:
        return (jsonify({'code': 401, 'message': '请先登录后台'}), 401)
    if token in _admin_tokens:
        return True
    db = _get_db()
    try:
        row = db.execute('SELECT 1 FROM admin_sessions WHERE token = ?', (token,)).fetchone()
        if row:
            _admin_tokens.add(token)
            return True
    finally:
        db.close()
    return (jsonify({'code': 401, 'message': '请先登录后台'}), 401)


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """后台登录：密码 123456（或 BAOSHUI_ADMIN_PASSWORD），返回 token。token 持久化到 DB，重启后仍有效。"""
    data = request.get_json() or {}
    pwd = (data.get('password') or '').strip()
    if pwd != ADMIN_PASSWORD:
        return jsonify({'code': 401, 'message': '密码错误'}), 401
    token = hashlib.sha256((TOKEN_SECRET + str(time.time()) + ''.join(random.choices(string.ascii_letters, k=8))).encode()).hexdigest()
    _admin_tokens.add(token)
    _init_db()
    db = _get_db()
    try:
        db.execute('INSERT OR IGNORE INTO admin_sessions (token) VALUES (?)', (token,))
        db.commit()
    finally:
        db.close()
    return jsonify({'code': 0, 'token': token})


@app.route('/api/admin/users')
def admin_list_users():
    """用户列表（需后台 token）。"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        rows = db.execute(
            'SELECT u.phone, u.company_name, u.created_at, '
            '(SELECT COUNT(*) FROM companies c WHERE c.phone = u.phone) AS companies_count '
            'FROM users u ORDER BY u.created_at DESC'
        ).fetchall()
        users = [
            {
                'phone': r['phone'],
                'company_name': r['company_name'] or '',
                'created_at': r['created_at'] or '',
                'companies_count': r['companies_count'] or 0,
            }
            for r in rows
        ]
        return jsonify({'code': 0, 'data': users})
    finally:
        db.close()


@app.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    """后台手动创建用户：手机号、登录密码、可选注册时企业名。"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    data = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    password = (data.get('password') or '').strip()
    company_name = (data.get('company_name') or '').strip() or ''

    if not phone:
        return jsonify({'code': 400, 'message': '请输入账号'}), 400

    _init_db()
    db = _get_db()
    try:
        row = db.execute('SELECT phone FROM users WHERE phone = ?', (phone,)).fetchone()
        if row:
            return jsonify({'code': 400, 'message': '该账号已存在'}), 400
        pw_hash = _password_hash(password or '', TOKEN_SECRET)
        db.execute('INSERT INTO users (phone, company_name, password) VALUES (?, ?, ?)', (phone, company_name, pw_hash))
        db.commit()
        return jsonify({'code': 0, 'message': '创建成功', 'phone': phone})
    finally:
        db.close()


@app.route('/api/admin/users/<phone>')
def admin_user_detail(phone):
    """单个用户全部信息：users 表 + 企业列表 + 各企业设置 + 会话数。"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        u = db.execute(
            'SELECT phone, company_name, password, created_at, updated_at FROM users WHERE phone = ?',
            (phone,)
        ).fetchone()
        if not u:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        companies = [
            {'id': r['id'], 'name': r['name'], 'legal_person': r['legal_person'] or '', 'created_at': r['created_at'] or ''}
            for r in db.execute('SELECT id, name, legal_person, created_at FROM companies WHERE phone = ? ORDER BY id', (phone,)).fetchall()
        ]
        # 注册时的企业（users.company_name）合并为企业列表第一条，id=0，与前台 list_companies 一致
        reg_name = (u['company_name'] or '').strip()
        if reg_name:
            companies.insert(0, {'id': 0, 'name': reg_name, 'legal_person': '', 'created_at': ''})
        settings_rows = db.execute(
            'SELECT company_id, bookkeeping_method, tax_ukey_type, tax_bureau_website, tax_bureau_login_method, '
            'tax_bureau_legal_id, tax_bureau_legal_password, tax_bureau_verified, personal_tax_account, personal_tax_password, updated_at '
            'FROM company_settings WHERE phone = ?',
            (phone,)
        ).fetchall()
        settings = [
            {
                'company_id': r['company_id'],
                'bookkeeping_method': r['bookkeeping_method'] or '',
                'tax_ukey_type': r['tax_ukey_type'] or '',
                'tax_bureau_website': r['tax_bureau_website'] or '',
                'tax_bureau_login_method': r['tax_bureau_login_method'] or '',
                'tax_bureau_legal_id': r['tax_bureau_legal_id'] or '',
                'tax_bureau_legal_password': r['tax_bureau_legal_password'] or '',
                'tax_bureau_verified': r['tax_bureau_verified'] or 0,
                'personal_tax_account': r['personal_tax_account'] or '',
                'personal_tax_password': r['personal_tax_password'] or '',
                'updated_at': r['updated_at'] or '',
            }
            for r in settings_rows
        ]
        sessions_count = db.execute('SELECT COUNT(*) AS n FROM sessions WHERE phone = ?', (phone,)).fetchone()['n']
        return jsonify({
            'code': 0,
            'data': {
                'user': {
                    'phone': u['phone'],
                    'company_name': u['company_name'] or '',
                    'created_at': u['created_at'] or '',
                    'updated_at': u['updated_at'] or '',
                },
                'companies': companies,
                'company_settings': settings,
                'sessions_count': sessions_count,
            }
        })
    finally:
        db.close()


@app.route('/api/admin/users/<phone>/reset-password', methods=['POST'])
def admin_reset_user_password(phone):
    """后台重置用户登录密码。"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    data = request.get_json() or {}
    password = (data.get('password') or '').strip()
    if not password or len(password) < 6:
        return jsonify({'code': 400, 'message': '请设置 6 位以上登录密码'}), 400

    _init_db()
    db = _get_db()
    try:
        row = db.execute('SELECT phone FROM users WHERE phone = ?', (phone,)).fetchone()
        if not row:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        pw_hash = _password_hash(password, TOKEN_SECRET)
        db.execute('UPDATE users SET password = ?, updated_at = datetime(\'now\') WHERE phone = ?', (pw_hash, phone))
        db.commit()
        return jsonify({'code': 0, 'message': '密码已重置'})
    finally:
        db.close()


# ---------- 兑换码与订阅 ----------
_VALID_TAX = ('small', 'general')
_VALID_BIZ = ('with', 'without')
_VALID_DURATION = (1, 12, 24, 36)


def _add_months_to_date(dt, months):
    """在日期上加月数，返回 date."""
    from datetime import date
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt[:10], '%Y-%m-%d').date()
        except Exception:
            dt = date.today()
    elif hasattr(dt, 'date'):
        dt = dt.date()
    else:
        dt = date.today()
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


@app.route('/api/admin/redemption-codes', methods=['GET'])
def admin_list_redemption_codes():
    """兑换码列表（需 admin token），可选 ?used=0|1 筛选"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    used_param = request.args.get('used')
    db = _get_db()
    try:
        if used_param == '1':
            rows = db.execute(
                'SELECT code, tax_type, biz_type, duration, used_at, used_by_phone, used_by_company_id, created_at '
                'FROM redemption_codes WHERE used_at IS NOT NULL ORDER BY used_at DESC'
            ).fetchall()
        elif used_param == '0':
            rows = db.execute(
                'SELECT code, tax_type, biz_type, duration, used_at, used_by_phone, used_by_company_id, created_at '
                'FROM redemption_codes WHERE used_at IS NULL ORDER BY created_at DESC'
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT code, tax_type, biz_type, duration, used_at, used_by_phone, used_by_company_id, created_at '
                'FROM redemption_codes ORDER BY created_at DESC'
            ).fetchall()
        data = [
            {
                'code': r['code'],
                'tax_type': r['tax_type'],
                'biz_type': r['biz_type'],
                'duration': r['duration'],
                'used_at': r['used_at'],
                'used_by_phone': r['used_by_phone'],
                'used_by_company_id': r['used_by_company_id'],
                'created_at': r['created_at'],
            }
            for r in rows
        ]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/admin/redemption-codes', methods=['POST'])
def admin_create_redemption_code():
    """创建兑换码（需 admin token）"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    data = request.get_json() or {}
    code = (data.get('code') or '').strip().upper()
    tax_type = (data.get('tax_type') or '').strip().lower()
    biz_type = (data.get('biz_type') or '').strip().lower()
    try:
        duration = int(data.get('duration', 0))
    except (TypeError, ValueError):
        duration = 0
    if not code:
        return jsonify({'code': 400, 'message': '兑换码不能为空'}), 400
    if tax_type not in _VALID_TAX:
        return jsonify({'code': 400, 'message': '纳税类型无效'}), 400
    if biz_type not in _VALID_BIZ:
        return jsonify({'code': 400, 'message': '记账类型无效'}), 400
    if duration not in _VALID_DURATION:
        return jsonify({'code': 400, 'message': '开通时长无效'}), 400
    db = _get_db()
    try:
        exists = db.execute('SELECT 1 FROM redemption_codes WHERE code = ?', (code,)).fetchone()
        if exists:
            return jsonify({'code': 400, 'message': '该兑换码已存在'}), 400
        db.execute(
            'INSERT INTO redemption_codes (code, tax_type, biz_type, duration) VALUES (?, ?, ?, ?)',
            (code, tax_type, biz_type, duration)
        )
        db.commit()
        return jsonify({'code': 0, 'message': '创建成功', 'data': {'code': code}})
    finally:
        db.close()


@app.route('/api/admin/redemption-codes/delete', methods=['POST'])
def admin_delete_redemption_code():
    """删除未使用的兑换码（需 admin token）"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    data = request.get_json() or {}
    code = (data.get('code') or '').strip().upper()
    if not code:
        return jsonify({'code': 400, 'message': '兑换码不能为空'}), 400
    db = _get_db()
    try:
        row = db.execute('SELECT used_at FROM redemption_codes WHERE code = ?', (code,)).fetchone()
        if not row:
            return jsonify({'code': 404, 'message': '兑换码不存在'}), 404
        if row['used_at']:
            return jsonify({'code': 400, 'message': '已使用的兑换码不能删除'}), 400
        db.execute('DELETE FROM redemption_codes WHERE code = ?', (code,))
        db.commit()
        return jsonify({'code': 0, 'message': '已删除'})
    finally:
        db.close()


@app.route('/api/admin/notifications', methods=['GET'])
def admin_list_notifications():
    """后台通知列表，可选 ?phone= 按用户筛选"""
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    phone_filter = (request.args.get('phone') or '').strip()
    db = _get_db()
    try:
        if phone_filter:
            rows = db.execute(
                'SELECT id, phone, title, content, is_read, created_at FROM notifications WHERE phone = ? ORDER BY created_at DESC LIMIT 500',
                (phone_filter,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT id, phone, title, content, is_read, created_at FROM notifications ORDER BY created_at DESC LIMIT 500'
            ).fetchall()
        data = [
            {'id': r['id'], 'phone': r['phone'] or '', 'title': r['title'] or '', 'content': r['content'] or '',
             'is_read': r['is_read'] or 0, 'created_at': r['created_at'] or ''}
            for r in rows
        ]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/admin/notifications', methods=['POST'])
def admin_create_notification():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    phone = (data.get('phone') or '').strip()
    if not title:
        return jsonify({'code': 400, 'message': '标题不能为空'}), 400
    db = _get_db()
    try:
        if phone:
            db.execute('INSERT INTO notifications (phone, title, content) VALUES (?, ?, ?)', (phone, title, content))
        else:
            for r in db.execute('SELECT phone FROM users').fetchall():
                db.execute('INSERT INTO notifications (phone, title, content) VALUES (?, ?, ?)', (r['phone'], title, content))
        db.commit()
        return jsonify({'code': 0, 'message': '已发送'})
    finally:
        db.close()


@app.route('/api/admin/notifications/<int:nid>', methods=['PUT'])
def admin_update_notification(nid):
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title:
        return jsonify({'code': 400, 'message': '标题不能为空'}), 400
    db = _get_db()
    try:
        cur = db.execute('UPDATE notifications SET title = ?, content = ? WHERE id = ?', (title, content, nid))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({'code': 404, 'message': '通知不存在'}), 404
        return jsonify({'code': 0, 'message': '已更新'})
    finally:
        db.close()


@app.route('/api/admin/notifications/<int:nid>', methods=['DELETE'])
def admin_delete_notification(nid):
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    db = _get_db()
    try:
        cur = db.execute('DELETE FROM notifications WHERE id = ?', (nid,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({'code': 404, 'message': '通知不存在'}), 404
        return jsonify({'code': 0, 'message': '已删除'})
    finally:
        db.close()


@app.route('/api/admin/chat/<phone>')
def admin_chat_list(phone):
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        rows = db.execute('SELECT id, direction, content, created_at FROM chat_messages WHERE phone = ? ORDER BY created_at ASC', (phone,)).fetchall()
        data = [{'id': r['id'], 'direction': r['direction'] or '', 'content': r['content'] or '', 'created_at': r['created_at'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/admin/chat/reply', methods=['POST'])
def admin_chat_reply():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    data = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    content = (data.get('content') or '').strip()
    if not phone or not content:
        return jsonify({'code': 400, 'message': '缺少 phone 或 content'}), 400
    db = _get_db()
    try:
        db.execute('INSERT INTO chat_messages (phone, direction, content) VALUES (?, ?, ?)', (phone, 'admin', content))
        db.commit()
        return jsonify({'code': 0, 'message': '已回复'})
    finally:
        db.close()


@app.route('/api/admin/discover')
def admin_discover_list():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        rows = db.execute('SELECT id, title, link_url, sort_order FROM discover_items ORDER BY sort_order, id').fetchall()
        data = [{'id': r['id'], 'title': r['title'] or '', 'link_url': r['link_url'] or '', 'sort_order': r['sort_order'] or 0} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/admin/discover', methods=['POST'])
def admin_discover_add():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    link_url = (data.get('link_url') or '').strip()
    sort_order = int(data.get('sort_order', 0) or 0)
    if not title:
        return jsonify({'code': 400, 'message': '标题不能为空'}), 400
    db = _get_db()
    try:
        db.execute('INSERT INTO discover_items (title, link_url, sort_order) VALUES (?, ?, ?)', (title, link_url, sort_order))
        db.commit()
        return jsonify({'code': 0, 'message': '已添加'})
    finally:
        db.close()


@app.route('/api/admin/discover/<int:did>', methods=['PUT'])
def admin_discover_update(did):
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    link_url = (data.get('link_url') or '').strip()
    sort_order = int(data.get('sort_order', 0) or 0)
    if not title:
        return jsonify({'code': 400, 'message': '标题不能为空'}), 400
    db = _get_db()
    try:
        cur = db.execute('UPDATE discover_items SET title = ?, link_url = ?, sort_order = ? WHERE id = ?',
                         (title, link_url, sort_order, did))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({'code': 404, 'message': '发现项不存在'}), 404
        return jsonify({'code': 0, 'message': '已更新'})
    finally:
        db.close()


@app.route('/api/admin/discover/<int:did>', methods=['DELETE'])
def admin_discover_delete(did):
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    db = _get_db()
    try:
        cur = db.execute('DELETE FROM discover_items WHERE id = ?', (did,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({'code': 404, 'message': '发现项不存在'}), 404
        return jsonify({'code': 0, 'message': '已删除'})
    finally:
        db.close()


@app.route('/api/admin/coupons')
def admin_coupons_list():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        rows = db.execute('SELECT code, discount_type, discount_value, valid_from, valid_until, used_at, used_by_phone, created_at FROM coupons ORDER BY created_at DESC').fetchall()
        data = [{'code': r['code'], 'discount_type': r['discount_type'], 'discount_value': r['discount_value'], 'valid_from': r['valid_from'], 'valid_until': r['valid_until'], 'used_at': r['used_at'], 'used_by_phone': r['used_by_phone'], 'created_at': r['created_at']} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/admin/coupons', methods=['POST'])
def admin_coupons_create():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    data = request.get_json() or {}
    code = (data.get('code') or '').strip().upper()
    discount_type = (data.get('discount_type') or 'fixed').strip().lower()
    discount_value = float(data.get('discount_value') or 0)
    valid_from = (data.get('valid_from') or '').strip() or None
    valid_until = (data.get('valid_until') or '').strip() or None
    if not code:
        return jsonify({'code': 400, 'message': '优惠券码不能为空'}), 400
    db = _get_db()
    try:
        if db.execute('SELECT 1 FROM coupons WHERE code = ?', (code,)).fetchone():
            return jsonify({'code': 400, 'message': '该优惠券码已存在'}), 400
        db.execute('INSERT INTO coupons (code, discount_type, discount_value, valid_from, valid_until) VALUES (?, ?, ?, ?, ?)', (code, discount_type, discount_value, valid_from, valid_until))
        db.commit()
        return jsonify({'code': 0, 'message': '已创建'})
    finally:
        db.close()


@app.route('/api/admin/config/contact', methods=['GET', 'POST'])
def admin_config_contact():
    v = _verify_admin()
    if v is not True:
        return v[0], v[1]
    _init_db()
    db = _get_db()
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            wechat = (data.get('wechat') or '').strip()
            desc = (data.get('desc') or '').strip()
            db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES ('contact_wechat', ?)", (wechat,))
            db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES ('contact_desc', ?)", (desc,))
            db.commit()
            return jsonify({'code': 0, 'message': '已保存'})
        wechat = db.execute("SELECT value FROM site_config WHERE key = 'contact_wechat'").fetchone()
        desc = db.execute("SELECT value FROM site_config WHERE key = 'contact_desc'").fetchone()
        wechat_val = (wechat['value'] if wechat else '').strip() or '18301979482'
        return jsonify({'code': 0, 'data': {'wechat': wechat_val, 'desc': desc['value'] if desc else ''}})
    finally:
        db.close()


@app.route('/api/redemption/redeem', methods=['POST'])
def redeem_code():
    """用户兑换：token + company_id + code，以码为准开通对应套餐时长"""
    _init_db()
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    company_id = (data.get('company_id') or data.get('companyId') or '').strip()
    code = (data.get('code') or '').strip().upper()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 400, 'message': '请选择企业'}), 400
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限操作该企业'}), 403
    if not code:
        return jsonify({'code': 400, 'message': '请输入兑换码'}), 400
    db = _get_db()
    try:
        row = db.execute(
            'SELECT code, tax_type, biz_type, duration, used_at FROM redemption_codes WHERE code = ?', (code,)
        ).fetchone()
        if not row:
            return jsonify({'code': 404, 'message': '兑换码不存在'}), 404
        if row['used_at']:
            return jsonify({'code': 400, 'message': '该兑换码已被使用'}), 400
        duration = int(row['duration'])
        now = datetime.utcnow()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        sub = db.execute(
            'SELECT expires_at FROM subscriptions WHERE phone = ? AND company_id = ?',
            (phone, company_id)
        ).fetchone()
        if sub and sub['expires_at']:
            try:
                base_date = datetime.strptime(sub['expires_at'][:10], '%Y-%m-%d')
            except Exception:
                base_date = now
            if base_date.date() > now.date():
                new_expires = _add_months_to_date(base_date, duration)
            else:
                new_expires = _add_months_to_date(now, duration)
        else:
            new_expires = _add_months_to_date(now, duration)
        new_expires_str = new_expires.strftime('%Y-%m-%d')
        db.execute(
            'INSERT INTO subscriptions (phone, company_id, expires_at, updated_at) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(phone, company_id) DO UPDATE SET expires_at = excluded.expires_at, updated_at = excluded.updated_at',
            (phone, company_id, new_expires_str, now_str)
        )
        db.execute(
            'UPDATE redemption_codes SET used_at = ?, used_by_phone = ?, used_by_company_id = ? WHERE code = ?',
            (now_str, phone, company_id, code)
        )
        db.commit()
        return jsonify({
            'code': 0,
            'message': '兑换成功',
            'data': {'expires_at': new_expires_str}
        })
    finally:
        db.close()


@app.route('/api/subscription/status')
def subscription_status():
    """当前企业正式版状态：token + company_id"""
    _init_db()
    token = (request.args.get('token') or (request.headers.get('Authorization') or '').replace('Bearer ', '')).strip()
    company_id = (request.args.get('company_id') or request.args.get('companyId') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 0, 'data': {'has_official': False, 'expires_at': None}})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 0, 'data': {'has_official': False, 'expires_at': None}})
    db = _get_db()
    try:
        row = db.execute(
            'SELECT expires_at FROM subscriptions WHERE phone = ? AND company_id = ?',
            (phone, company_id)
        ).fetchone()
        if not row or not row['expires_at']:
            return jsonify({'code': 0, 'data': {'has_official': False, 'expires_at': None}})
        exp = row['expires_at'][:10]
        from datetime import date
        try:
            exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        except Exception:
            exp_date = date.today()
        if exp_date < date.today():
            return jsonify({'code': 0, 'data': {'has_official': False, 'expires_at': exp}})
        return jsonify({'code': 0, 'data': {'has_official': True, 'expires_at': exp}})
    finally:
        db.close()


@app.route('/api/ledger/categories')
def ledger_categories():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    t = request.args.get('type', '').strip()
    db = _get_db()
    try:
        if t in ('income', 'expense'):
            rows = db.execute('SELECT id, name, type, sort_order FROM ledger_categories WHERE type = ? ORDER BY sort_order', (t,)).fetchall()
        else:
            rows = db.execute('SELECT id, name, type, sort_order FROM ledger_categories ORDER BY type, sort_order').fetchall()
        data = [{'id': r['id'], 'name': r['name'], 'type': r['type'], 'sort_order': r['sort_order']} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/ledger/entries')
def ledger_entries_list():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    period = (request.args.get('period') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id or not period:
        return jsonify({'code': 0, 'data': []})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        rows = db.execute(
            'SELECT e.id, e.period, e.type, e.category_id, e.amount, e.remark, e.created_at, c.name as category_name '
            'FROM ledger_entries e LEFT JOIN ledger_categories c ON e.category_id = c.id '
            'WHERE e.phone = ? AND e.company_id = ? AND e.period = ? ORDER BY e.created_at DESC',
            (phone, company_id, period)
        ).fetchall()
        out = []
        for r in rows:
            att = db.execute('SELECT id, file_path FROM ledger_attachments WHERE entry_id = ?', (r['id'],)).fetchall()
            out.append({
                'id': r['id'], 'period': r['period'], 'type': r['type'], 'category_id': r['category_id'],
                'category_name': r['category_name'] or '', 'amount': r['amount'], 'remark': r['remark'] or '',
                'created_at': r['created_at'] or '',
                'attachments': [{'id': a['id'], 'file_path': a['file_path']} for a in att]
            })
        return jsonify({'code': 0, 'data': out})
    finally:
        db.close()


@app.route('/api/ledger/entries', methods=['POST'])
def ledger_entries_add():
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    company_id = (data.get('company_id') or '').strip()
    period = (data.get('period') or '').strip()
    typ = (data.get('type') or '').strip()
    category_id = data.get('category_id')
    amount = data.get('amount')
    remark = (data.get('remark') or '').strip()
    attachment_paths = data.get('attachment_paths') or []
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id or not period or not typ or category_id is None:
        return jsonify({'code': 400, 'message': '缺少参数'}), 400
    if typ not in ('income', 'expense'):
        return jsonify({'code': 400, 'message': '类型无效'}), 400
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '金额无效'}), 400
    db = _get_db()
    try:
        db.execute(
            'INSERT INTO ledger_entries (phone, company_id, period, type, category_id, amount, remark) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (phone, company_id, period, typ, int(category_id), amount, remark)
        )
        db.commit()
        eid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        for path in (attachment_paths if isinstance(attachment_paths, list) else []):
            if isinstance(path, str) and path:
                db.execute('INSERT INTO ledger_attachments (entry_id, file_path) VALUES (?, ?)', (eid, path))
        db.commit()
        return jsonify({'code': 0, 'message': '添加成功', 'data': {'id': eid}})
    finally:
        db.close()


@app.route('/api/ledger/entries/<int:entry_id>', methods=['PUT'])
def ledger_entries_update(entry_id):
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    db = _get_db()
    try:
        row = db.execute('SELECT id, phone, company_id, amount FROM ledger_entries WHERE id = ?', (entry_id,)).fetchone()
        if not row or row['phone'] != phone:
            return jsonify({'code': 404, 'message': '记录不存在'}), 404
        typ = (data.get('type') or '').strip()
        category_id = data.get('category_id')
        amount = data.get('amount')
        remark = (data.get('remark') or '').strip()
        if typ not in ('income', 'expense'):
            return jsonify({'code': 400, 'message': '类型无效'}), 400
        amt = float(amount) if amount is not None else row['amount']
        cat_id = int(category_id) if category_id is not None else None
        per = (data.get('period') or '').strip()
        if cat_id is not None and per:
            db.execute('UPDATE ledger_entries SET type = ?, category_id = ?, amount = ?, remark = ?, period = ? WHERE id = ?',
                       (typ, cat_id, amt, remark, per, entry_id))
        elif cat_id is not None:
            db.execute('UPDATE ledger_entries SET type = ?, category_id = ?, amount = ?, remark = ? WHERE id = ?',
                       (typ, cat_id, amt, remark, entry_id))
        else:
            db.execute('UPDATE ledger_entries SET type = ?, amount = ?, remark = ? WHERE id = ?', (typ, amt, remark, entry_id))
        db.commit()
        return jsonify({'code': 0, 'message': '修改成功'})
    finally:
        db.close()


@app.route('/api/ledger/entries/delete', methods=['POST'])
def ledger_entries_delete():
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    entry_id = data.get('entry_id') or data.get('id')
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if entry_id is None:
        return jsonify({'code': 400, 'message': '缺少 entry_id'}), 400
    try:
        entry_id = int(entry_id)
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': 'entry_id 无效'}), 400
    db = _get_db()
    try:
        row = db.execute('SELECT id, phone FROM ledger_entries WHERE id = ?', (entry_id,)).fetchone()
        if not row or row['phone'] != phone:
            return jsonify({'code': 404, 'message': '记录不存在'}), 404
        db.execute('DELETE FROM ledger_attachments WHERE entry_id = ?', (entry_id,))
        db.execute('DELETE FROM ledger_entries WHERE id = ?', (entry_id,))
        db.commit()
        return jsonify({'code': 0, 'message': '已删除'})
    finally:
        db.close()


@app.route('/api/upload', methods=['POST'])
def upload_file():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    if request.form:
        token = token or (request.form.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    f = request.files.get('file') or request.files.get('file_path')
    if not f or not f.filename:
        return jsonify({'code': 400, 'message': '请选择文件'}), 400
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(f.filename)[1] or '.bin'
    safe_name = '%s%s%s' % (int(time.time() * 1000), '_', (f.filename or 'file').replace('..', '').replace('/', '_')[-50:])
    if len(safe_name) > 100:
        safe_name = safe_name[:100] + ext
    path = os.path.join(UPLOAD_DIR, safe_name)
    try:
        f.save(path)
        rel = 'uploads/' + safe_name
        return jsonify({'code': 0, 'data': {'url': rel, 'file_path': rel}})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@app.route('/api/documents')
def documents_list():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    period = (request.args.get('period') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id or not period:
        return jsonify({'code': 0, 'data': []})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        rows = db.execute(
            'SELECT e.id, e.period, e.type, e.amount, e.remark, e.created_at, c.name as category_name '
            'FROM ledger_entries e LEFT JOIN ledger_categories c ON e.category_id = c.id '
            'WHERE e.phone = ? AND e.company_id = ? AND e.period = ? ORDER BY e.created_at DESC',
            (phone, company_id, period)
        ).fetchall()
        out = []
        for r in rows:
            att = db.execute('SELECT id, file_path FROM ledger_attachments WHERE entry_id = ?', (r['id'],)).fetchall()
            out.append({
                'id': r['id'], 'period': r['period'], 'type': r['type'], 'amount': r['amount'],
                'remark': r['remark'] or '', 'created_at': r['created_at'] or '', 'category_name': r['category_name'] or '',
                'attachments': [{'id': a['id'], 'file_path': a['file_path']} for a in att]
            })
        return jsonify({'code': 0, 'data': out})
    finally:
        db.close()


_VALID_TAX = ('small', 'general')
_VALID_BIZ = ('with', 'without')
_VALID_DURATION = (1, 12, 24, 36)


def _add_months_to_date(dt, months):
    from datetime import date
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt[:10], '%Y-%m-%d').date()
        except Exception:
            dt = date.today()
    elif hasattr(dt, 'date'):
        dt = dt.date()
    else:
        dt = date.today()
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


@app.route('/ping')
def ping():
    """连通性测试"""
    return 'OK', 200, {'Content-Type': 'text/plain'}


def _report_summary_data(db, phone, company_id, period):
    income = 0.0
    expense = 0.0
    if company_id and period:
        for r in db.execute(
            'SELECT type, amount FROM ledger_entries WHERE phone = ? AND company_id = ? AND period = ?',
            (phone, company_id, period)
        ).fetchall():
            if r['type'] == 'income':
                income += float(r['amount'] or 0)
            else:
                expense += float(r['amount'] or 0)
    return {
        'tax': {'status': None, 'period': period},
        'profit': {'earned': round(income - expense, 2), 'expense': round(expense, 2), 'income': round(income, 2)},
        'accounts': [
            {'name': '银行存款', 'value': None}, {'name': '其他货币资金', 'value': None},
            {'name': '现金', 'value': None}, {'name': '库存商品', 'value': None},
            {'name': '固定资产', 'value': None}, {'name': '往年亏损', 'value': None},
            {'name': '对外投资', 'value': None}, {'name': '理财投资', 'value': None},
        ],
        'stats_time': period,
    }


@app.route('/api/report/summary')
def report_summary():
    """报表概览数据（需登录，按用户绑定；有 company_id/period 时从记账汇总）"""
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    period = (request.args.get('period') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if company_id and not _user_owns_company(phone, company_id):
        company_id = ''
    db = _get_db()
    try:
        data = _report_summary_data(db, phone, company_id, period)
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/report/tax-history')
def report_tax_history():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 0, 'data': []})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        rows = db.execute(
            'SELECT id, period, tax_type, status, submitted_at FROM tax_submissions WHERE phone = ? AND company_id = ? ORDER BY submitted_at DESC',
            (phone, company_id)
        ).fetchall()
        data = [{'id': r['id'], 'period': r['period'], 'tax_type': r['tax_type'], 'status': r['status'] or '', 'submitted_at': r['submitted_at'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/report/other-tax')
def report_other_tax():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not company_id:
        return jsonify({'code': 0, 'data': []})
    if not _user_owns_company(phone, company_id):
        return jsonify({'code': 403, 'message': '无权限'}), 403
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT id, period, tax_type, status, submitted_at FROM tax_submissions WHERE phone = ? AND company_id = ? AND tax_type != 'main' ORDER BY submitted_at DESC",
            (phone, company_id)
        ).fetchall()
        data = [{'id': r['id'], 'period': r['period'], 'tax_type': r['tax_type'], 'status': r['status'] or '', 'submitted_at': r['submitted_at'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


def _report_detail_empty():
    return jsonify({'code': 0, 'data': {'rows': [], 'period': None}})


@app.route('/api/report/balance-sheet')
@app.route('/api/report/profit')
@app.route('/api/report/cash-flow')
@app.route('/api/report/fixed-assets')
@app.route('/api/report/account-balance')
def report_detail():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    company_id = (request.args.get('company_id') or '').strip()
    period = (request.args.get('period') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if company_id and not _user_owns_company(phone, company_id):
        return _report_detail_empty()
    return _report_detail_empty()


@app.route('/api/notifications')
def notifications_list():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    db = _get_db()
    try:
        rows = db.execute('SELECT id, title, content, is_read, created_at FROM notifications WHERE phone = ? ORDER BY created_at DESC LIMIT 100', (phone,)).fetchall()
        data = [{'id': r['id'], 'title': r['title'] or '', 'content': r['content'] or '', 'is_read': bool(r['is_read']), 'created_at': r['created_at'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/notifications/read', methods=['POST'])
def notifications_read():
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    ids = data.get('ids') or ([data.get('id')] if data.get('id') is not None else [])
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not ids:
        return jsonify({'code': 0, 'message': 'ok'})
    db = _get_db()
    try:
        for i in ids:
            if i is not None:
                db.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND phone = ?', (int(i), phone))
        db.commit()
        return jsonify({'code': 0, 'message': 'ok'})
    finally:
        db.close()


@app.route('/api/user/settings')
def user_settings_get():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    db = _get_db()
    try:
        rows = db.execute('SELECT key, value FROM user_settings WHERE phone = ?', (phone,)).fetchall()
        data = {r['key']: r['value'] for r in rows}
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/user/settings', methods=['POST'])
def user_settings_save():
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    key = (data.get('key') or '').strip()
    value = (data.get('value') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not key:
        return jsonify({'code': 400, 'message': '缺少 key'}), 400
    db = _get_db()
    try:
        db.execute('INSERT OR REPLACE INTO user_settings (phone, key, value) VALUES (?, ?, ?)', (phone, key, value))
        db.commit()
        return jsonify({'code': 0, 'message': '已保存'})
    finally:
        db.close()


@app.route('/api/config/contact')
def config_contact():
    _init_db()
    db = _get_db()
    try:
        wechat = db.execute("SELECT value FROM site_config WHERE key = 'contact_wechat'").fetchone()
        desc = db.execute("SELECT value FROM site_config WHERE key = 'contact_desc'").fetchone()
        return jsonify({
            'code': 0,
            'data': {
                'wechat': (wechat['value'] if wechat else '').strip() or os.environ.get('BAOSHUI_CONTACT_WECHAT', '18301979482'),
                'desc': (desc['value'] if desc else '').strip() or os.environ.get('BAOSHUI_CONTACT_DESC', '请通过应用内客服或官网获取')
            }
        })
    finally:
        db.close()


@app.route('/api/order/validate-coupon', methods=['POST'])
def order_validate_coupon():
    _init_db()
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'code': 400, 'message': '请输入优惠券码'}), 400
    db = _get_db()
    try:
        row = db.execute('SELECT code, discount_type, discount_value, valid_from, valid_until, used_at FROM coupons WHERE code = ?', (code,)).fetchone()
        if not row:
            return jsonify({'code': 404, 'message': '优惠券不存在'}), 404
        if row['used_at']:
            return jsonify({'code': 400, 'message': '该优惠券已使用'}), 400
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        if row['valid_until'] and row['valid_until'] < now_str:
            return jsonify({'code': 400, 'message': '优惠券已过期'}), 400
        if row['valid_from'] and row['valid_from'] > now_str:
            return jsonify({'code': 400, 'message': '优惠券未到使用时间'}), 400
        return jsonify({
            'code': 0,
            'data': {'valid': True, 'discount_type': row['discount_type'] or 'fixed', 'discount_value': float(row['discount_value'] or 0)}
        })
    finally:
        db.close()


@app.route('/api/chat/messages')
def chat_messages_list():
    _init_db()
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip() or (request.args.get('token') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    db = _get_db()
    try:
        rows = db.execute('SELECT id, direction, content, created_at FROM chat_messages WHERE phone = ? ORDER BY created_at ASC LIMIT 200', (phone,)).fetchall()
        data = [{'id': r['id'], 'direction': r['direction'] or '', 'content': r['content'] or '', 'created_at': r['created_at'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/api/chat/messages', methods=['POST'])
def chat_messages_send():
    _init_db()
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    content = (data.get('content') or '').strip()
    phone = _verify_token(token)
    if not phone:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    if not content:
        return jsonify({'code': 400, 'message': '请输入内容'}), 400
    db = _get_db()
    try:
        db.execute('INSERT INTO chat_messages (phone, direction, content) VALUES (?, ?, ?)', (phone, 'user', content))
        db.commit()
        return jsonify({'code': 0, 'message': '已发送'})
    finally:
        db.close()


@app.route('/api/discover')
def discover_list():
    _init_db()
    db = _get_db()
    try:
        rows = db.execute('SELECT id, title, link_url, sort_order FROM discover_items ORDER BY sort_order, id').fetchall()
        data = [{'id': r['id'], 'title': r['title'] or '', 'link_url': r['link_url'] or ''} for r in rows]
        return jsonify({'code': 0, 'data': data})
    finally:
        db.close()


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/index2')
def index2():
    """简洁版首页 - 纯 HTML"""
    return send_from_directory('.', 'index2.html')


@app.route('/download')
def download_page():
    """下载页（禁止缓存，避免看到旧版）"""
    with open(os.path.join(os.path.dirname(__file__), 'download.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    prefix = _base_prefix()
    if prefix:
        html = html.replace('href="/', 'href="%s/' % prefix)
    resp = Response(html, mimetype='text/html; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/download/ios')
def download_ios():
    """iOS 构建 - 重定向到 GitHub Release"""
    return redirect('https://github.com/alexwang-2021/baoshui/releases/latest', code=302)


def _base_prefix():
    """当前请求的路径前缀（如 /baoshui）"""
    return request.headers.get('X-Forwarded-Prefix', '').rstrip('/')


def _ota_base_url():
    """OTA 安装的 base URL（需 HTTPS）"""
    base = os.environ.get('BAOSHUI_OTA_BASE_URL')
    if base:
        return base.rstrip('/')
    prefix = _base_prefix()
    # 代理可能传递多个值，取第一个
    proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'https').split(',')[0].strip()
    host = (request.headers.get('X-Forwarded-Host') or request.host or '').split(',')[0].strip()
    return '%s://%s%s' % (proto or 'https', host, prefix)


@app.route('/download/ios-manifest.plist')
def ios_ota_manifest():
    """iOS OTA 安装 - manifest.plist"""
    base = _ota_base_url()
    ipa_url = base + '/download/App.ipa'
    plist = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>%s</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>com.baoshui.app</string>
                <key>bundle-version</key>
                <string>1.0</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>自报税</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>''' % ipa_url
    return Response(plist, mimetype='application/xml')


@app.route('/ios-upload')
def ios_upload_page():
    """iOS IPA 上传页"""
    with open(os.path.join(os.path.dirname(__file__), 'ios-upload.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    prefix = _base_prefix()
    if prefix:
        html = html.replace('href="/', 'href="%s/' % prefix)
    return Response(html, mimetype='text/html; charset=utf-8')


@app.route('/api/ios/upload-ipa', methods=['POST'])
def upload_ipa():
    """上传 App.ipa"""
    ipa_file = request.files.get('ipa')
    if not ipa_file:
        return jsonify({'code': 400, 'message': '请选择 .ipa 文件'}), 400
    if not ipa_file.filename.lower().endswith('.ipa'):
        return jsonify({'code': 400, 'message': '请上传 .ipa 格式文件'}), 400
    try:
        dest = os.path.join(os.path.dirname(__file__), 'App.ipa')
        ipa_file.save(dest)
        return jsonify({'code': 0, 'message': '上传成功'})
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@app.route('/download/ios-install')
def ios_install_page():
    """iOS OTA 安装页"""
    with open(os.path.join(os.path.dirname(__file__), 'ios-install.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    prefix = _base_prefix()
    base = _ota_base_url()
    manifest_url = base + '/download/ios-manifest.plist'
    install_href = 'itms-services://?action=download-manifest&url=' + quote(manifest_url, safe='')
    if prefix:
        html = html.replace('href="/', 'href="%s/' % prefix)
    html = html.replace('{{INSTALL_HREF}}', install_href)
    return Response(html, mimetype='text/html; charset=utf-8')


@app.route('/download/<filename>')
def download_file(filename):
    """下载安装包（文件需放在项目根目录，如 app-debug.apk）"""
    allowed = ('app-debug.apk', 'baoshui-apk.zip', 'baoshui-ios-source.zip', 'App-simulator.zip', 'App.ipa')
    if filename not in allowed:
        return Response('<h1>404</h1><p>该文件不可下载</p>', status=404, mimetype='text/html; charset=utf-8')
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.isfile(path):
        return Response(
            '<h1>404</h1><p>安装包尚未上传，请将 %s 放到项目根目录后重试。</p>' % filename,
            status=404,
            mimetype='text/html; charset=utf-8'
        )
    return send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=True,
        download_name=filename
    )


@app.route('/privacy')
def privacy_page():
    """隐私政策页，支持浏览器直接访问 /privacy 或 /privacy.html"""
    return send_from_directory('.', 'privacy.html', mimetype='text/html; charset=utf-8')


@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')


@app.route('/icon-180.png')
@app.route('/icon-192.png')
@app.route('/icon-512.png')
def icons():
    name = request.path.strip('/')
    return send_from_directory('.', name)


@app.route('/video/<path:filename>')
def serve_video(filename):
    """新手引导等视频文件"""
    return send_from_directory('video', filename)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """凭证等上传文件"""
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/<path:path>')
def static_files(path):
    if path in ('index.html', 'report.html', 'report-tax-history.html', 'report-other-tax.html', 'report-detail.html', 'styles.css', 'report.css', 'app.js', 'report.js', 'config.js', 'download.html', 'apple-cert.html', 'ios-upload.html', 'ios-install.html', 'chat.html', 'ledger.html', 'discover.html', 'mine.html', 'documents.html', 'tax-bureau-login.html', 'choose-bookkeeping.html', 'tax-ukey.html', 'personal-tax-login.html', 'feature-self-accounting.html', 'feature-auto-tax.html', 'feature-tax-annual.html', 'feature-realtime-ledger.html', 'feature-social-security.html', 'feature-business-annual.html', 'pricing.html', 'video-guide.html', 'my-companies.html', 'coming-soon.html', 'activate-official.html', 'activate-official-order.html', 'admin.html', 'admin-user.html', 'admin-redemption.html', 'admin-notifications.html', 'admin-discover.html', 'admin-coupons.html', 'admin-contact.html', 'settings.html', 'privacy.html'):
        return send_from_directory('.', path)
    return '', 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8083, debug=True)
