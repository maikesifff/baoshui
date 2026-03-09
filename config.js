/**
 * API 配置 - 按运行环境修改
 * 公网(me.gaoxin.xin/baoshui): BASE_URL: '/baoshui'
 * 本地调试: BASE_URL: ''
 * 模拟器: http://10.0.2.2:8083
 * 真机(同局域网): http://电脑IP:8083
 */
window.API_CONFIG = {
  BASE_URL: '/baoshui',
  ENDPOINTS: {
    SEND_CODE: '/api/sms/send',
    LOGIN: '/api/auth/login',
    REGISTER: '/api/auth/register',
    COMPANY_NAME: '/api/user/company-name',
    COMPANIES: '/api/user/companies',
    REPORT_SUMMARY: '/api/report/summary',
    COMPANY_SETTINGS: '/api/company/settings',
    COMPANY_SETTINGS_STATUS: '/api/company/settings/status',
    REDEEM: '/api/redemption/redeem',
    SUBSCRIPTION_STATUS: '/api/subscription/status',
    LEDGER_CATEGORIES: '/api/ledger/categories',
    LEDGER_ENTRIES: '/api/ledger/entries',
    UPLOAD: '/api/upload',
    DOCUMENTS: '/api/documents',
    REPORT_TAX_HISTORY: '/api/report/tax-history',
    REPORT_OTHER_TAX: '/api/report/other-tax',
    REPORT_BALANCE_SHEET: '/api/report/balance-sheet',
    REPORT_PROFIT: '/api/report/profit',
    REPORT_CASH_FLOW: '/api/report/cash-flow',
    REPORT_FIXED_ASSETS: '/api/report/fixed-assets',
    REPORT_ACCOUNT_BALANCE: '/api/report/account-balance',
    NOTIFICATIONS: '/api/notifications',
    NOTIFICATIONS_READ: '/api/notifications/read',
    USER_SETTINGS: '/api/user/settings',
    CONFIG_CONTACT: '/api/config/contact',
    VALIDATE_COUPON: '/api/order/validate-coupon',
    CHAT_MESSAGES: '/api/chat/messages',
    DISCOVER: '/api/discover'
  }
};
