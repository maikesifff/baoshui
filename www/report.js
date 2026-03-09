/**
 * 报表页 - 交互逻辑（需登录，数据与用户绑定）
 */
document.addEventListener('DOMContentLoaded', function() {
  var user = null;
  try { user = JSON.parse(localStorage.getItem('user') || '{}'); } catch (e) {}
  if (user && user.phone) {
    var dot = document.getElementById('reportMenuDot');
    if (dot) dot.classList.add('has-notice');
  }

  var token = localStorage.getItem('token');
  var companyId = localStorage.getItem('currentCompanyId') || '';
  if (!token) {
    return;
  }
  var now = new Date();
  var period = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  var API = window.API_CONFIG || { BASE_URL: '', ENDPOINTS: { REPORT_SUMMARY: '/api/report/summary' } };
  var url = (API.BASE_URL || '') + API.ENDPOINTS.REPORT_SUMMARY + '?company_id=' + encodeURIComponent(companyId) + '&period=' + encodeURIComponent(period);
  fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.code === 401) return;
      var d = data.data;
      if (!d) return;
      var tax = d.tax || {};
      var taxStatus = document.getElementById('reportTaxStatus');
      var taxPeriod = document.getElementById('reportTaxPeriod');
      if (taxStatus) taxStatus.textContent = tax.status != null ? tax.status : '--';
      if (taxPeriod) taxPeriod.textContent = tax.period != null ? '(' + tax.period + ')' : '(--)';
      var profit = d.profit || {};
      var elEarned = document.getElementById('reportEarned');
      var elExpense = document.getElementById('reportExpense');
      var elIncome = document.getElementById('reportIncome');
      if (elEarned) elEarned.textContent = profit.earned != null ? profit.earned : '--';
      if (elExpense) elExpense.textContent = profit.expense != null ? profit.expense : '--';
      if (elIncome) elIncome.textContent = profit.income != null ? profit.income : '--';
      var statsTime = document.getElementById('reportStatsTime');
      if (statsTime) statsTime.textContent = d.stats_time != null ? '(统计至 ' + d.stats_time + ')' : '(--)';
      var accounts = d.accounts || [];
      var grid = document.getElementById('reportAccountGrid');
      if (grid && accounts.length) {
        grid.innerHTML = accounts.map(function(a) {
          var v = a.value != null ? a.value : '--';
          return '<div class="account-item"><span class="account-value">' + v + '</span><span class="account-label">' + (a.name || '') + '</span></div>';
        }).join('');
      }
    })
    .catch(function() {});
});
