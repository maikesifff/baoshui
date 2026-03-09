/**
 * 自报税 - 手机端交互（注册/登录，验证码+密码双方式）
 */

document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('registerModal');
  const companyModal = document.getElementById('companyModal');
  const btnRegister = document.getElementById('btnRegister');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const btnCloseCompany = document.getElementById('btnCloseCompany');
  const btnLogout = document.getElementById('btnLogout');
  const registerForm = document.getElementById('registerForm');
  const loginForm = document.getElementById('loginForm');
  const companyForm = document.getElementById('companyForm');
  const btnSendCode = document.getElementById('btnSendCode');
  const btnLoginSendCode = document.getElementById('btnLoginSendCode');
  const phoneInput = document.getElementById('phone');
  const codeInput = document.getElementById('code');
  const passwordInput = document.getElementById('password');
  const loginPhoneInput = document.getElementById('loginPhone');
  const loginCodeInput = document.getElementById('loginCode');
  const loginPasswordInput = document.getElementById('loginPassword');
  const companyNameInput = document.getElementById('companyName');
  const guestArea = document.getElementById('guestArea');
  const userArea = document.getElementById('userArea');
  const userDisplay = document.getElementById('userDisplay');
  const authTabs = document.querySelectorAll('.auth-tab');
  const loginCodeGroup = document.getElementById('loginCodeGroup');
  const loginPwdGroup = document.getElementById('loginPwdGroup');

  const API = window.API_CONFIG || { BASE_URL: '', ENDPOINTS: { SEND_CODE: '/api/sms/send', LOGIN: '/api/auth/login', REGISTER: '/api/auth/register', COMPANY_NAME: '/api/user/company-name', COMPANIES: '/api/user/companies', REPORT_SUMMARY: '/api/report/summary' } };

  var companiesList = [];

  function getCompanies() {
    return companiesList;
  }

  function loadCompanies(cb) {
    var token = localStorage.getItem('token');
    if (!token) {
      companiesList = [];
      renderCompanyDropdown();
      if (cb) cb();
      return;
    }
    var url = (API.BASE_URL || '') + API.ENDPOINTS.COMPANIES;
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(res) {
        if (!res.ok) {
          companiesList = [];
          renderCompanyDropdown();
          if (cb) cb();
          return;
        }
        return res.json();
      })
      .then(function(data) {
        if (!data) return;
        companiesList = (data && data.data) ? data.data : [];
        if (data && data.code === 401) companiesList = [];
        renderCompanyDropdown();
        if (cb) cb();
      })
      .catch(function() {
        companiesList = [];
        renderCompanyDropdown();
        if (cb) cb();
      });
  }

  function setCurrentCompany(id) {
    localStorage.setItem('currentCompanyId', id || '');
  }

  function getCurrentCompanyId() {
    return localStorage.getItem('currentCompanyId') || '';
  }

  function sameCompanyId(a, b) {
    if (a == null && b == null) return true;
    return String(a || '') === String(b || '');
  }

  function renderCompanyDropdown() {
    var list = getCompanies();
    var currentId = getCurrentCompanyId();
    var currentExists = list.some(function(c) { return sameCompanyId(c.id, currentId); });
    if (list.length > 0 && (!currentId || !currentExists)) {
      var firstId = list[0].id != null ? String(list[0].id) : '';
      setCurrentCompany(firstId);
      currentId = firstId;
    }
    var html = '';
    if (list.length === 0) {
      html = '<div class="company-option company-empty" data-id="">暂无企业</div>';
    } else {
      list.forEach(function(c) {
        var id = c.id != null ? String(c.id) : '';
        var isSelected = sameCompanyId(c.id, currentId);
        if (isSelected) setCurrentCompany(id);
        html += '<div class="company-option' + (isSelected ? ' selected' : '') + '" data-id="' + (id || '') + '">' + (c.name || '') + (isSelected ? '<span class="check">✓</span>' : '') + '</div>';
      });
    }
    var el = document.getElementById('companyList');
    if (el) el.innerHTML = html;
    updateCompanyDisplay();
  }

  function updateCompanyDisplay() {
    var list = getCompanies();
    var currentId = getCurrentCompanyId();
    var current = list.find(function(c) { return sameCompanyId(c.id, currentId); }) || list[0];
    var display = document.getElementById('companyNameDisplay');
    if (display) display.textContent = current ? current.name : '请选择企业';
  }

  function updateLoginUI() {
    var user = null;
    try { user = JSON.parse(localStorage.getItem('user') || '{}'); } catch (e) {}
    var homeGuestView = document.getElementById('homeGuestView');
    var homeLoggedView = document.getElementById('homeLoggedView');
    var mineGuest = document.getElementById('mineGuest');
    var mineLogged = document.getElementById('mineLogged');
    if (user && user.phone) {
      if (homeGuestView) homeGuestView.style.display = 'none';
      if (homeLoggedView) homeLoggedView.style.display = 'block';
      var maskedPhone = (user.phone || '').replace(/(\d{3})\d{4}(\d{4})/, '$1****$2');
      if (userDisplay) userDisplay.textContent = maskedPhone;
      var dot = document.getElementById('menuDot');
      if (dot) dot.classList.add('has-notice');
      if (mineGuest) mineGuest.style.display = 'none';
      if (mineLogged) {
        mineLogged.style.display = 'block';
        mineLogged.setAttribute('aria-hidden', 'false');
        var minePhoneDisplay = document.getElementById('minePhoneDisplay');
        var mineAvatar = document.getElementById('mineAvatar');
        if (minePhoneDisplay) minePhoneDisplay.textContent = maskedPhone;
        if (mineAvatar && user.phone) mineAvatar.textContent = (user.phone.charAt(0) || '头');
      }
    } else {
      if (homeGuestView) homeGuestView.style.display = 'block';
      if (homeLoggedView) homeLoggedView.style.display = 'none';
      var dot = document.getElementById('menuDot');
      if (dot) dot.classList.remove('has-notice');
      if (mineGuest) mineGuest.style.display = 'block';
      if (mineLogged) {
        mineLogged.style.display = 'none';
        mineLogged.setAttribute('aria-hidden', 'true');
      }
    }
  }

  function loadTodoButtonStatus() {
    var token = localStorage.getItem('token');
    var companyId = getCurrentCompanyId();
    var btnBookkeeping = document.getElementById('todoBtnBookkeeping');
    var btnTaxBureau = document.getElementById('todoBtnTaxBureau');
    var btnTaxUkey = document.getElementById('todoBtnTaxUkey');
    var btnPersonalTax = document.getElementById('todoBtnPersonalTax');
    var setDefault = function() {
      if (btnBookkeeping) btnBookkeeping.textContent = '立即选择';
      if (btnTaxBureau) btnTaxBureau.textContent = '立即处理';
      if (btnTaxUkey) btnTaxUkey.textContent = '立即处理';
      if (btnPersonalTax) btnPersonalTax.textContent = '立即处理';
    };
    if (!token || !companyId) {
      setDefault();
      return;
    }
    var url = (API.BASE_URL || '') + (API.ENDPOINTS.COMPANY_SETTINGS_STATUS || '/api/company/settings/status') + '?company_id=' + encodeURIComponent(companyId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(res) { return res.ok ? res.json() : null; })
      .then(function(data) {
        if (!data || data.code !== 0 || !data.data) {
          setDefault();
          return;
        }
        var s = data.data;
        if (btnBookkeeping) btnBookkeeping.textContent = s.bookkeeping_method ? '修改' : '立即选择';
        if (btnTaxBureau) btnTaxBureau.textContent = s.tax_bureau ? '修改' : '立即处理';
        if (btnTaxUkey) btnTaxUkey.textContent = s.tax_ukey ? '修改' : '立即处理';
        if (btnPersonalTax) btnPersonalTax.textContent = s.personal_tax ? '修改' : '立即处理';
      })
      .catch(function() { setDefault(); });
  }

  function loadSubscriptionStatus() {
    var token = localStorage.getItem('token');
    var companyId = getCurrentCompanyId();
    var btnTodoOpen = document.getElementById('btnTodoOpen');
    if (!btnTodoOpen) return;
    var card = btnTodoOpen.closest('.todo-fixed-card');
    var subEl = card ? card.querySelector('.todo-fixed-card-sub') : null;
    if (!token || !companyId) {
      if (subEl) subEl.textContent = '\u5f53\u524d\u8bd5\u7528\u7248\u4e0d\u5305\u542b\u5ba1\u8d26\u62a5\u7a0e\u670d\u52a1';
      btnTodoOpen.textContent = '\u7acb\u5373\u5f00\u901a';
      return;
    }
    var url = (API.BASE_URL || '') + '/api/subscription/status?company_id=' + encodeURIComponent(companyId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(res) { return res.ok ? res.json() : null; })
      .then(function(data) {
        if (data && data.code === 0 && data.data && data.data.has_official && data.data.expires_at) {
          if (subEl) subEl.textContent = '\u6b63\u5f0f\u7248\u5df2\u5f00\u901a\u81f3 ' + data.data.expires_at;
          btnTodoOpen.textContent = '\u67e5\u770b';
        } else {
          if (subEl) subEl.textContent = '\u5f53\u524d\u8bd5\u7528\u7248\u4e0d\u5305\u542b\u5ba1\u8d26\u62a5\u7a0e\u670d\u52a1';
          btnTodoOpen.textContent = '\u7acb\u5373\u5f00\u901a';
        }
      })
      .catch(function() {
        if (subEl) subEl.textContent = '\u5f53\u524d\u8bd5\u7528\u7248\u4e0d\u5305\u542b\u5ba1\u8d26\u62a5\u7a0e\u670d\u52a1';
        btnTodoOpen.textContent = '\u7acb\u5373\u5f00\u901a';
      });
  }

  updateLoginUI();
  loadCompanies(function() { loadTodoButtonStatus();
      loadSubscriptionStatus(); loadSubscriptionStatus(); });

  function formatMonthDay(d) {
    return (d.getMonth() + 1) + '\u6708' + d.getDate() + '\u65e5';
  }
  function updatePeriodInfoDates() {
    var now = new Date();
    var y = now.getFullYear();
    var m = now.getMonth();
    var day = now.getDate();
    var accountBlock = document.querySelector('.period-info-wrap .period-info[data-tab="account"]');
    var taxBlock = document.querySelector('.period-info-wrap .period-info[data-tab="tax"]');
    if (accountBlock) {
      var lastMonth = new Date(y, m - 1, 1);
      var thisMonthStart = new Date(y, m, 1);
      var periodStart1 = new Date(y, m - 1, 24);
      var periodEnd1 = new Date(y, m, 9);
      var periodStart2 = new Date(y, m, 24);
      var periodEnd2 = new Date(y, m + 1, 9);
      var line1 = accountBlock.querySelector('p:first-child');
      var line2 = accountBlock.querySelector('.period-remain');
      if (day <= 9) {
        var endOfPeriod = new Date(y, m, 9, 23, 59, 59);
        line1.textContent = '\u6b63\u5728\u8bb0' + (m || 12) + '\u6708\u8d26, \u5f55\u5165\u65f6\u95f4: ' + formatMonthDay(periodStart1) + '~' + formatMonthDay(periodEnd1);
        if (line2) {
          if (now > endOfPeriod) {
            line2.textContent = '\u5df2\u8fc7\u671f';
          } else {
            var remain = endOfPeriod - now;
            var days = Math.floor(remain / 86400000);
            var hours = Math.floor((remain % 86400000) / 3600000);
            var mins = Math.floor((remain % 3600000) / 60000);
            line2.textContent = '\u5269\u4f59 ' + days + '\u5929' + hours + '\u5c0f\u65f6' + mins + '\u5206';
          }
        }
      } else if (day >= 24) {
        var endOfPeriod2 = new Date(y, m + 1, 9, 23, 59, 59);
        line1.textContent = '\u6b63\u5728\u8bb0' + (m + 1) + '\u6708\u8d26, \u5f55\u5165\u65f6\u95f4: ' + formatMonthDay(periodStart2) + '~' + formatMonthDay(periodEnd2);
        if (line2) {
          if (now > endOfPeriod2) {
            line2.textContent = '\u5df2\u8fc7\u671f';
          } else {
            var remain = endOfPeriod2 - now;
            var days = Math.floor(remain / 86400000);
            var hours = Math.floor((remain % 86400000) / 3600000);
            var mins = Math.floor((remain % 3600000) / 60000);
            line2.textContent = '\u5269\u4f59 ' + days + '\u5929' + hours + '\u5c0f\u65f6' + mins + '\u5206';
          }
        }
      } else {
        line1.textContent = '\u5f53\u524d\u4e0d\u5728\u8bb0\u8d26\u671f';
        if (line2) line2.textContent = '\u4e0b\u4e00\u671f \u5f55\u5165\u65f6\u95f4: ' + formatMonthDay(periodStart2) + '~' + formatMonthDay(periodEnd2);
      }
    }
    if (taxBlock) {
      var taxLine1 = taxBlock.querySelector('p:first-child');
      if (taxLine1) {
        if (day <= 16) {
          taxLine1.textContent = '\u5c06\u5728' + (m + 1) + '\u670810\u65e5~16\u65e5\u5b8c\u6210\u672c\u671f\u62a5\u7a0e';
        } else {
          var nextM = m + 1;
          var nextMonth = nextM > 11 ? 1 : nextM + 1;
          taxLine1.textContent = '\u5c06\u5728' + nextMonth + '\u670810\u65e5~16\u65e5\u5b8c\u6210\u672c\u671f\u62a5\u7a0e';
        }
      }
    }
  }
  updatePeriodInfoDates();

  var headerCompany = document.getElementById('headerCompany');
  var headerMenu = document.getElementById('headerMenu');
  var companyDropdown = document.getElementById('companyDropdown');
  var btnAddCompany = document.getElementById('btnAddCompany');
  var addCompanyPage = document.getElementById('addCompanyPage');
  var btnBackAddCompany = document.getElementById('btnBackAddCompany');
  var btnSubmitAddCompany = document.getElementById('btnSubmitAddCompany');
  var addCompanyNameInput = document.getElementById('addCompanyName');
  var addLegalPersonInput = document.getElementById('addLegalPerson');

  var companyListEl = document.getElementById('companyList');

  function toggleCompanyDropdown() {
    if (companyDropdown) companyDropdown.classList.toggle('show');
  }
  if (headerCompany && companyDropdown) {
    headerCompany.addEventListener('click', function(e) {
      e.stopPropagation();
      toggleCompanyDropdown();
    });
    document.addEventListener('click', function(e) {
      if (!companyDropdown.contains(e.target) && !headerCompany.contains(e.target) && !(headerMenu && headerMenu.contains(e.target))) {
        companyDropdown.classList.remove('show');
      }
    });
  }
  if (headerMenu && companyDropdown) {
    headerMenu.addEventListener('click', function(e) {
      e.stopPropagation();
      toggleCompanyDropdown();
    });
  }

  // 企业列表点击切换：委托到 #companyList，确保动态选项可点击
  if (companyListEl && companyDropdown) {
    companyListEl.addEventListener('click', function(e) {
      var opt = e.target.closest('.company-option');
      if (!opt || opt.classList.contains('company-empty')) return;
      var id = opt.getAttribute('data-id');
      if (id === null) return;
      e.preventDefault();
      e.stopPropagation();
      setCurrentCompany(id);
      renderCompanyDropdown();
      loadTodoButtonStatus();
      loadSubscriptionStatus();
      companyDropdown.classList.remove('show');
    });
  }

  if (btnAddCompany) {
    btnAddCompany.addEventListener('click', function() {
      if (companyDropdown) companyDropdown.classList.remove('show');
      if (!localStorage.getItem('token')) {
        alert('请先登录');
        if (btnRegister) btnRegister.click();
        return;
      }
      if (addCompanyPage) addCompanyPage.classList.add('show');
    });
  }

  if (btnBackAddCompany) {
    btnBackAddCompany.addEventListener('click', function() {
      if (addCompanyPage) addCompanyPage.classList.remove('show');
    });
  }

  if (btnSubmitAddCompany && addCompanyNameInput) {
    btnSubmitAddCompany.addEventListener('click', function() {
      var name = (addCompanyNameInput.value || '').trim();
      if (!name) { alert('请输入企业/个体户全称'); return; }
      var token = localStorage.getItem('token');
      if (!token) { alert('请先登录'); return; }
      var url = (API.BASE_URL || '') + API.ENDPOINTS.COMPANIES;
      btnSubmitAddCompany.disabled = true;
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ name: name, legal_person: (addLegalPersonInput && addLegalPersonInput.value) || '' })
      })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.code === 0) {
            setCurrentCompany(data.data && data.data.id);
            loadCompanies(function() { loadTodoButtonStatus(); loadSubscriptionStatus(); });
            addCompanyPage.classList.remove('show');
            addCompanyNameInput.value = '';
            if (addLegalPersonInput) addLegalPersonInput.value = '';
            alert('添加成功');
          } else {
            throw new Error(data.message || '添加失败');
          }
        })
        .catch(function(err) {
          alert(err.message || '添加失败');
        })
        .finally(function() {
          btnSubmitAddCompany.disabled = false;
        });
    });
  }

  var mainTabs = document.querySelectorAll('.main-tab');
  var progressLine = document.querySelector('.progress-line');
  var periodInfos = document.querySelectorAll('.period-info');
  mainTabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      var tabName = tab.getAttribute('data-tab');
      mainTabs.forEach(function(t) { t.classList.remove('active'); });
      tab.classList.add('active');
      document.querySelectorAll('.progress-dot').forEach(function(d) {
        d.classList.toggle('active', d.getAttribute('data-tab') === tabName);
      });
      document.querySelectorAll('.progress-segment').forEach(function(s) { s.classList.remove('active'); });
      var tabIndex = Array.from(mainTabs).indexOf(tab);
      document.querySelectorAll('.progress-segment').forEach(function(s, i) {
        if (i < tabIndex) s.classList.add('active');
      });
      if (progressLine) progressLine.setAttribute('aria-valuenow', String(tabIndex + 1));
      periodInfos.forEach(function(block) {
        block.classList.toggle('active', block.getAttribute('data-tab') === tabName);
      });
    });
  });

  var todoTabs = document.querySelectorAll('.todo-tab');
  var todoPanelTodo = document.getElementById('todoPanelTodo');
  var todoPanelNotice = document.getElementById('todoPanelNotice');
  function loadNotifications() {
    var token = localStorage.getItem('token');
    var emptyEl = document.getElementById('todoNoticeEmpty');
    var listEl = document.getElementById('todoNoticeList');
    if (!token || !listEl) return;
    var url = (API.BASE_URL || '') + (API.ENDPOINTS.NOTIFICATIONS || '/api/notifications');
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(r) { return r.json(); })
      .then(function(res) {
        if (res.code !== 0 || !res.data || !res.data.length) {
          if (emptyEl) emptyEl.style.display = 'block';
          listEl.style.display = 'none';
          return;
        }
        emptyEl.style.display = 'none';
        listEl.style.display = 'block';
        listEl.innerHTML = res.data.map(function(n) {
          return '<div class="todo-notice-item" data-id="' + n.id + '"><div class="todo-notice-item-title">' + (n.title || '') + '</div><div class="todo-notice-item-time">' + (n.created_at ? n.created_at.slice(0, 19) : '') + '</div><div class="todo-notice-item-content">' + (n.content || '') + '</div></div>';
        }).join('');
      });
  }
  todoTabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      var which = tab.getAttribute('data-todo');
      todoTabs.forEach(function(t) { t.classList.remove('active'); });
      tab.classList.add('active');
      if (todoPanelTodo) todoPanelTodo.classList.toggle('active', which === 'todo');
      if (todoPanelNotice) todoPanelNotice.classList.toggle('active', which === 'notice');
      if (which === 'notice') loadNotifications();
    });
  });

  function initTodoCollapse() {
    var items = document.querySelectorAll('#todoList .todo-item');
    var firstIncomplete = null;
    items.forEach(function(item) {
      var done = item.getAttribute('data-done') === 'true';
      if (!done && !firstIncomplete) firstIncomplete = item;
    });
    var expandTarget = firstIncomplete || items[0];
    items.forEach(function(item) {
      if (item === expandTarget) {
        item.classList.remove('collapsed');
        item.classList.add('expanded');
      } else {
        item.classList.add('collapsed');
        item.classList.remove('expanded');
      }
    });
  }

  function setupTodoToggle() {
    document.querySelectorAll('#todoList .todo-item-header').forEach(function(header) {
      header.addEventListener('click', function() {
        var item = header.closest('.todo-item');
        if (!item) return;
        item.classList.toggle('collapsed');
        item.classList.toggle('expanded');
      });
    });
    document.querySelectorAll('#todoList .todo-action, #todoList .todo-card a').forEach(function(btn) {
      btn.addEventListener('click', function(e) { e.stopPropagation(); });
    });
  }

  initTodoCollapse();
  setupTodoToggle();

  btnRegister.addEventListener('click', function() {
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
  });

  function closeModal() {
    modal.classList.remove('show');
    document.body.style.overflow = '';
  }

  btnCloseModal.addEventListener('click', closeModal);
  modal.addEventListener('click', function(e) {
    if (e.target === modal) closeModal();
  });

  function closeCompanyModal() {
    if (companyModal) {
      companyModal.classList.remove('show');
      document.body.style.overflow = '';
    }
  }

  if (btnCloseCompany) btnCloseCompany.addEventListener('click', closeCompanyModal);
  if (companyModal) companyModal.addEventListener('click', function(e) {
    if (e.target === companyModal) closeCompanyModal();
  });

  if (btnLogout) btnLogout.addEventListener('click', function() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    updateLoginUI();
  });
  var mineLoginRegister = document.getElementById('mineLoginRegister');
  var mineLogout = document.getElementById('mineLogout');
  if (mineLoginRegister && modal) {
    mineLoginRegister.addEventListener('click', function() {
      switchPanel('home');
      modal.classList.add('show');
      document.body.style.overflow = 'hidden';
    });
  }
  if (mineLogout) {
    mineLogout.addEventListener('click', function() {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('currentCompanyId');
      updateLoginUI();
    });
  }

  var tipModal = document.getElementById('tipModal');
  var tipModalTitle = document.getElementById('tipModalTitle');
  var tipModalBody = document.getElementById('tipModalBody');
  var tipModalClose = document.getElementById('tipModalClose');
  function openTipModal(title, body) {
    if (tipModalTitle) tipModalTitle.textContent = title;
    if (tipModalBody) tipModalBody.textContent = body;
    if (tipModal) {
      tipModal.classList.add('show');
      document.body.style.overflow = 'hidden';
    }
  }
  function closeTipModal() {
    if (tipModal) {
      tipModal.classList.remove('show');
      document.body.style.overflow = '';
    }
  }
  if (tipModalClose) tipModalClose.addEventListener('click', closeTipModal);
  if (tipModal) tipModal.addEventListener('click', function(e) { if (e.target === tipModal) closeTipModal(); });
  var todoDetailLink = document.getElementById('todoDetailLink');
  if (todoDetailLink) {
    todoDetailLink.addEventListener('click', function(e) {
      e.preventDefault();
      openTipModal('票据保管说明', '按记账月份将纸质票据订在一起，妥善保管。\n\n更多说明可咨询客服。');
    });
  }
  var btnTodoWechat = document.getElementById('btnTodoWechat');
  if (btnTodoWechat) {
    btnTodoWechat.addEventListener('click', function() {
      var url = (API.BASE_URL || '') + (API.ENDPOINTS.CONFIG_CONTACT || '/api/config/contact');
      fetch(url).then(function(r) { return r.json(); }).then(function(res) {
        var wechat = (res.data && res.data.wechat) ? res.data.wechat : '';
        var desc = (res.data && res.data.desc) ? res.data.desc : '请通过应用内客服或官网获取';
        openTipModal('客服微信', '添加客服微信获取记账报税服务。\n\n客服微信号：' + (wechat || '请通过应用内客服或官网获取') + '\n\n' + desc);
      }).catch(function() {
        openTipModal('客服微信', '添加客服微信获取记账报税服务。\n\n请通过应用内客服或官网获取微信号。');
      });
    });
  }
  var btnTodoOpen = document.getElementById('btnTodoOpen');
  if (btnTodoOpen) {
    btnTodoOpen.addEventListener('click', function() {
      window.location.href = 'activate-official.html';
    });
  }
  var linkUnsupported = document.getElementById('linkUnsupported');
  if (linkUnsupported) {
    linkUnsupported.addEventListener('click', function(e) {
      e.preventDefault();
      openTipModal('不支持的企业', '如遇不支持的企业类型，请联系客服咨询。');
    });
  }
  // 设置入口已使用 <a href="settings.html">

  // 注册/登录 Tab 切换
  authTabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      var mode = tab.getAttribute('data-mode');
      authTabs.forEach(function(t) { t.classList.remove('active'); });
      tab.classList.add('active');
      if (mode === 'register') {
        registerForm.style.display = 'block';
        loginForm.style.display = 'none';
      } else {
        registerForm.style.display = 'none';
        loginForm.style.display = 'block';
      }
    });
  });

  // 登录方式切换：底部链接「切换为密码登录」/「切换为验证码登录」
  var loginModeSwitch = document.getElementById('loginModeSwitch');
  var loginMode = 'code';
  if (loginModeSwitch && loginCodeGroup && loginPwdGroup) {
    loginModeSwitch.addEventListener('click', function(e) {
      e.preventDefault();
      if (loginMode === 'code') {
        loginMode = 'pwd';
        loginCodeGroup.style.display = 'none';
        loginPwdGroup.style.display = 'block';
        loginModeSwitch.textContent = '切换为验证码登录';
      } else {
        loginMode = 'code';
        loginCodeGroup.style.display = 'block';
        loginPwdGroup.style.display = 'none';
        loginModeSwitch.textContent = '切换为密码登录';
      }
    });
  }

  // 验证码倒计时
  var countdown = 0;
  var countdown2 = 0;

  function startCountdown(btn) {
    var c = (btn === btnLoginSendCode) ? 2 : 1;
    if (c === 2) countdown2 = 60; else countdown = 60;
    btn.disabled = true;
    btn.textContent = '60秒后重试';
    var timer = setInterval(function() {
      if (c === 2) countdown2--; else countdown--;
      var left = (c === 2) ? countdown2 : countdown;
      btn.textContent = left + '秒后重试';
      if (left <= 0) {
        clearInterval(timer);
        btn.disabled = false;
        btn.textContent = '获取验证码';
      }
    }, 1000);
  }

  function doSendCode(phone, btn) {
    if (!phone) {
      alert('请输入手机号或账号');
      return;
    }
    var c = (btn === btnLoginSendCode) ? countdown2 : countdown;
    if (c > 0) return;

    var url = (API.BASE_URL || '') + API.ENDPOINTS.SEND_CODE;
    btn.disabled = true;
    btn.textContent = '发送中...';
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: phone })
    })
      .then(function(res) {
        if (!res.ok) throw new Error('发送失败');
        return res.json();
      })
      .then(function(data) {
        if (data.code !== undefined && data.code !== 0 && data.code !== 200) {
          throw new Error(data.msg || data.message || '发送失败');
        }
        startCountdown(btn);
      })
      .catch(function(err) {
        btn.disabled = false;
        btn.textContent = '获取验证码';
        alert(err.message || '验证码发送失败');
      });
  }

  btnSendCode.addEventListener('click', function() {
    doSendCode(phoneInput.value.trim(), btnSendCode);
  });

  btnLoginSendCode.addEventListener('click', function() {
    doSendCode(loginPhoneInput.value.trim(), btnLoginSendCode);
  });

  // 注册提交
  registerForm.addEventListener('submit', function(e) {
    e.preventDefault();
    if (!document.getElementById('authPrivacyCheck').checked) {
      alert('请先阅读并勾选同意《隐私政策》后再注册');
      return;
    }
    var phone = phoneInput.value.trim();
    var code = codeInput.value.trim();
    var password = passwordInput.value.trim();

    if (!phone) {
      alert('请输入手机号或账号');
      return;
    }
    if (!/^\d{4,6}$/.test(code)) {
      alert('请输入正确的验证码');
      return;
    }
    if (!password || password.length < 6) {
      alert('请设置 6 位以上登录密码');
      return;
    }

    var url = (API.BASE_URL || '') + API.ENDPOINTS.REGISTER;
    var submitBtn = registerForm.querySelector('.btn-submit');
    var originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '注册中...';

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: phone, code: code, password: password })
    })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.code !== 0 && data.code !== 200) throw new Error(data.message || '注册失败');
        var token = data.token;
        if (token) {
          localStorage.setItem('token', token);
          if (data.user) localStorage.setItem('user', JSON.stringify(data.user));
        }
        closeModal();
        registerForm.reset();
        updateLoginUI();
        loadCompanies(function() { loadTodoButtonStatus(); loadSubscriptionStatus(); });
        if (data.need_company_name && companyModal) {
          companyModal.classList.add('show');
          document.body.style.overflow = 'hidden';
        } else {
          alert('注册成功');
        }
      })
      .catch(function(err) {
        alert(err.message || '注册失败');
      })
      .finally(function() {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      });
  });

  // 登录提交
  loginForm.addEventListener('submit', function(e) {
    e.preventDefault();
    if (!document.getElementById('authPrivacyCheck').checked) {
      alert('请先阅读并勾选同意《隐私政策》后再登录');
      return;
    }
    var phone = loginPhoneInput.value.trim();
    var isPwdMode = loginPwdGroup && loginPwdGroup.style.display !== 'none';
    var code = loginCodeInput.value.trim();
    var password = loginPasswordInput.value.trim();

    if (!phone) {
      alert('请输入手机号或账号');
      return;
    }

    var body = { phone: phone };
    if (isPwdMode) {
      if (!password) {
        alert('请输入密码');
        return;
      }
      body.password = password;
    } else {
      if (!/^\d{4,6}$/.test(code)) {
        alert('请输入正确的验证码');
        return;
      }
      body.code = code;
    }

    var url = (API.BASE_URL || '') + API.ENDPOINTS.LOGIN;
    var submitBtn = loginForm.querySelector('.btn-submit');
    var originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = '登录中...';

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.code !== 0 && data.code !== 200 && !data.token) {
          throw new Error(data.message || '登录失败');
        }
        var token = data.token;
        if (token) {
          localStorage.setItem('token', token);
          if (data.user) localStorage.setItem('user', JSON.stringify(data.user));
        }
        closeModal();
        loginForm.reset();
        updateLoginUI();
        loadCompanies(function() { loadTodoButtonStatus(); loadSubscriptionStatus(); });
        if (data.need_company_name && companyModal) {
          companyModal.classList.add('show');
          document.body.style.overflow = 'hidden';
        } else {
          alert('登录成功');
        }
      })
      .catch(function(err) {
        alert(err.message || '登录失败');
      })
      .finally(function() {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      });
  });

  // 填写公司名称
  if (companyForm && companyNameInput) {
    companyForm.addEventListener('submit', function(e) {
      e.preventDefault();
      var companyName = (companyNameInput.value || '').trim();
      if (!companyName) {
        alert('请输入公司名称');
        return;
      }
      var token = localStorage.getItem('token');
      if (!token) {
        alert('请先登录');
        closeCompanyModal();
        return;
      }
      var submitBtn = companyForm.querySelector('.btn-submit');
      var originalText = submitBtn.textContent;
      submitBtn.disabled = true;
      submitBtn.textContent = '保存中...';
      fetch((API.BASE_URL || '') + API.ENDPOINTS.COMPANY_NAME, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token, company_name: companyName })
      })
        .then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.code === 0) {
            var user = JSON.parse(localStorage.getItem('user') || '{}');
            user.company_name = companyName;
            localStorage.setItem('user', JSON.stringify(user));
            loadCompanies(function() { loadTodoButtonStatus(); loadSubscriptionStatus(); });
            alert('公司名称已保存');
            closeCompanyModal();
            companyForm.reset();
            updateLoginUI();
          } else {
            throw new Error(data.message || '保存失败');
          }
        })
        .catch(function(err) {
          alert(err.message || '保存失败');
        })
        .finally(function() {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        });
    });
  }

  // 底部导航：四个切换面板，中间「记账」打开底部悬浮窗
  var ledgerDrawer = document.getElementById('ledgerDrawer');
  var ledgerDrawerOverlay = document.getElementById('ledgerDrawerOverlay');
  var btnCloseLedgerDrawer = document.getElementById('btnCloseLedgerDrawer');

  function escapeChatPreview(s) {
    if (s == null || s === '') return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }
  function loadChatConversationList() {
    var token = localStorage.getItem('token');
    var listWrap = document.getElementById('chatConversationListWrap');
    var listEl = document.getElementById('chatConversationList');
    if (!listWrap || !listEl) return;
    if (!token) return;
    var url = (API.BASE_URL || '') + (API.ENDPOINTS.CHAT_MESSAGES || '/api/chat/messages');
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(r) { return r.json(); })
      .then(function(res) {
        var data = (res.code === 0 && res.data && res.data.length) ? res.data : [];
        var last = data.length ? data[data.length - 1] : null;
        var rawPreview = last ? String(last.content || '').slice(0, 30) : '';
        if (last && String(last.content || '').length > 30) rawPreview += '…';
        var preview = rawPreview ? escapeChatPreview(rawPreview) : '暂无消息';
        var time = last && last.created_at ? last.created_at.slice(0, 16) : '';
        listEl.innerHTML = '<li class="chat-conversation-item" data-chat="service" tabindex="0" role="button">' +
          '<span class="chat-conversation-title">客服</span>' +
          '<span class="chat-conversation-preview">' + preview + '</span>' +
          '<span class="chat-conversation-time">' + time + '</span></li>';
        listEl.querySelector('.chat-conversation-item').addEventListener('click', function() {
          var detailWrap = document.getElementById('chatDetailWrap');
          if (listWrap) listWrap.style.display = 'none';
          if (detailWrap) {
            detailWrap.style.display = 'block';
            loadChatMessages();
            var msgList = document.getElementById('chatMessageList');
            if (msgList) msgList.scrollTop = msgList.scrollHeight;
          }
        });
      });
  }

  function loadChatMessages() {
    var token = localStorage.getItem('token');
    var listEl = document.getElementById('chatMessageList');
    if (!listEl) return;
    if (!token) return;
    var url = (API.BASE_URL || '') + (API.ENDPOINTS.CHAT_MESSAGES || '/api/chat/messages');
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(r) { return r.json(); })
      .then(function(res) {
        if (res.code !== 0 || !res.data || !res.data.length) {
          listEl.innerHTML = '<p class="placeholder-desc">暂无消息，发送一条开始对话</p>';
        } else {
          listEl.innerHTML = res.data.map(function(m) {
            var isUser = m.direction === 'user';
            return '<div class="chat-msg ' + (isUser ? 'chat-msg-user' : 'chat-msg-admin') + '"><span class="chat-msg-content">' + (m.content || '') + '</span><span class="chat-msg-time">' + (m.created_at ? m.created_at.slice(0, 16) : '') + '</span></div>';
          }).join('');
          listEl.scrollTop = listEl.scrollHeight;
        }
      });
  }

  function showChatListAndHideDetail() {
    var listWrap = document.getElementById('chatConversationListWrap');
    var detailWrap = document.getElementById('chatDetailWrap');
    var placeholder = document.getElementById('chatPlaceholder');
    if (placeholder) placeholder.style.display = 'none';
    if (detailWrap) detailWrap.style.display = 'none';
    if (listWrap) listWrap.style.display = 'block';
    loadChatConversationList();
  }
  function loadDiscover() {
    var url = (API.BASE_URL || '') + (API.ENDPOINTS.DISCOVER || '/api/discover');
    var wrap = document.getElementById('discoverListWrap');
    var placeholder = document.getElementById('discoverPlaceholder');
    fetch(url).then(function(r) { return r.json(); }).then(function(res) {
      if (res.code !== 0 || !res.data || !res.data.length) {
        if (wrap) wrap.style.display = 'none';
        if (placeholder) placeholder.style.display = 'block';
        return;
      }
      if (placeholder) placeholder.style.display = 'none';
      if (wrap) {
        wrap.style.display = 'block';
        wrap.innerHTML = '<div class="discover-list">' + res.data.map(function(d) {
          return '<a href="' + (d.link_url || '#') + '" class="discover-item" target="_blank" rel="noopener">' + (d.title || '') + '</a>';
        }).join('') + '</div>';
      }
    });
  }
  function switchPanel(panelName) {
    document.querySelectorAll('.nav-panel').forEach(function(p) {
      p.classList.toggle('active', p.id === 'panel' + panelName.charAt(0).toUpperCase() + panelName.slice(1));
    });
    document.querySelectorAll('.bottom-nav .nav-item').forEach(function(item) {
      var p = item.getAttribute('data-panel');
      item.classList.toggle('active', p === panelName && !item.classList.contains('nav-center'));
    });
    if (panelName === 'home') { loadTodoButtonStatus(); loadSubscriptionStatus(); }
    if (panelName === 'chat') {
      var chatListWrap = document.getElementById('chatConversationListWrap');
      var chatDetailWrap = document.getElementById('chatDetailWrap');
      var chatPlaceholder = document.getElementById('chatPlaceholder');
      if (localStorage.getItem('token')) {
        if (chatPlaceholder) chatPlaceholder.style.display = 'none';
        if (chatDetailWrap) chatDetailWrap.style.display = 'none';
        if (chatListWrap) chatListWrap.style.display = 'block';
        loadChatConversationList();
      } else {
        if (chatListWrap) chatListWrap.style.display = 'none';
        if (chatDetailWrap) chatDetailWrap.style.display = 'none';
        if (chatPlaceholder) chatPlaceholder.style.display = 'block';
      }
    }
    if (panelName === 'discover') loadDiscover();
  }

  function openLedgerDrawer() {
    if (ledgerDrawerOverlay) ledgerDrawerOverlay.classList.add('show');
    if (ledgerDrawer) ledgerDrawer.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeLedgerDrawer() {
    if (ledgerDrawerOverlay) ledgerDrawerOverlay.classList.remove('show');
    if (ledgerDrawer) ledgerDrawer.classList.remove('show');
    document.body.style.overflow = '';
  }

  var ledgerLoginPromptModal = document.getElementById('ledgerLoginPromptModal');
  var ledgerLoginPromptCancel = document.getElementById('ledgerLoginPromptCancel');
  var ledgerLoginPromptLogin = document.getElementById('ledgerLoginPromptLogin');

  function closeLedgerLoginPrompt() {
    if (ledgerLoginPromptModal) ledgerLoginPromptModal.classList.remove('show');
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.bottom-nav .nav-item').forEach(function(item) {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      var panel = item.getAttribute('data-panel');
      if (panel === 'ledger') {
        if (!localStorage.getItem('token')) {
          if (ledgerLoginPromptModal) {
            ledgerLoginPromptModal.classList.add('show');
            document.body.style.overflow = 'hidden';
          }
        } else {
          openLedgerDrawer();
        }
        return;
      }
      if (panel) switchPanel(panel);
    });
  });

  if (ledgerLoginPromptCancel) ledgerLoginPromptCancel.addEventListener('click', closeLedgerLoginPrompt);
  if (ledgerLoginPromptLogin && modal) {
    ledgerLoginPromptLogin.addEventListener('click', function() {
      closeLedgerLoginPrompt();
      modal.classList.add('show');
      document.body.style.overflow = 'hidden';
    });
  }
  if (ledgerLoginPromptModal) ledgerLoginPromptModal.addEventListener('click', function(e) {
    if (e.target === ledgerLoginPromptModal) closeLedgerLoginPrompt();
  });

  if (btnCloseLedgerDrawer) btnCloseLedgerDrawer.addEventListener('click', closeLedgerDrawer);
  if (ledgerDrawerOverlay) ledgerDrawerOverlay.addEventListener('click', closeLedgerDrawer);

  var chatDetailBack = document.getElementById('chatDetailBack');
  if (chatDetailBack) {
    chatDetailBack.addEventListener('click', function() { showChatListAndHideDetail(); });
  }

  var chatSend = document.getElementById('chatSend');
  var chatInput = document.getElementById('chatInput');
  if (chatSend && chatInput) {
    chatSend.addEventListener('click', function() {
      var token = localStorage.getItem('token');
      if (!token) return;
      var content = (chatInput.value || '').trim();
      if (!content) return;
      var url = (API.BASE_URL || '') + (API.ENDPOINTS.CHAT_MESSAGES || '/api/chat/messages');
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ content: content })
      }).then(function(r) { return r.json(); }).then(function(res) {
        if (res.code === 0) {
          chatInput.value = '';
          loadChatMessages();
        }
      });
    });
  }

  // 从套餐页「立即开通」跳转回来时打开登录/注册弹窗
  if (typeof location !== 'undefined' && location.search && location.search.indexOf('openAuth=1') !== -1) {
    switchPanel('home');
    if (modal) { modal.classList.add('show'); document.body.style.overflow = 'hidden'; }
    if (history.replaceState) history.replaceState({}, '', location.pathname || '/');
  }
});
