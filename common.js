/* Store Configuration - Centralized settings */
var StoreConfig = (function() {
    var KEY = 'danzona_store_config';
    var defaults = {
        storeName: 'Shanks Shop Management', storeAddress: '', phoneNumber: '', emailAddress: '',
        currency: '₦', currencyLocale: 'en-NG', lowStockThreshold: 5, sessionTimeout: 30,
        storeLogo: '', footerText: 'Thank you for choosing Shanks Shop Management!', printerType: 'small',
        pharmacyName: 'Shanks Shop Management',
        taxEnabled: false, taxRate: 7.5, taxName: 'VAT',
        allowDiscount: true, maxDiscount: 20,
        requireManagerForDiscount: false, requireManagerForVoid: true,
        receiptPrefix: 'DAN', autoPrintReceipt: true, showReceiptLogo: true,
        expiryAlertDays: 30, expiryBlockSales: false,
        lowStockAlert: true, lowStockEmail: '',
        openingTime: '08:00', closingTime: '20:00', openDays: 'Mon-Sat',
        allowStoreAccount: true, allowGiftCard: true, allowCardPayment: true, allowPosPayment: true
    };
    function getAll() { try { var raw = localStorage.getItem(KEY); if (!raw) return JSON.parse(JSON.stringify(defaults)); var parsed = JSON.parse(raw); return Object.assign({}, defaults, parsed); } catch (e) { return JSON.parse(JSON.stringify(defaults)); } }
    function get(key) { var cfg = getAll(); return cfg[key] !== undefined ? cfg[key] : defaults[key]; }
    function set(key, value) { var cfg = getAll(); cfg[key] = value; save(cfg); }
    function save(cfg) { try { localStorage.setItem(KEY, JSON.stringify(cfg)); return true; } catch (e) { console.error('StoreConfig save error:', e); return false; } }
    function formatCurrency(amount) { var currency = get('currency'); var locale = get('currencyLocale'); try { return currency + (parseFloat(amount) || 0).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } catch (e) { return currency + (parseFloat(amount) || 0).toFixed(2); } }
    function formatDate(dateStr) { try { return new Date(dateStr).toLocaleDateString(get('currencyLocale'), { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return dateStr || '-'; } }
    function getStoreName() { return get('storeName') || defaults.storeName; }
    function getCurrency() { return get('currency') || defaults.currency; }
    function getLowStockThreshold() { return parseInt(get('lowStockThreshold')) || defaults.lowStockThreshold; }
    function getPharmacyName() { return get('pharmacyName') || get('storeName') || defaults.storeName; }
    async function syncFromServer() {
        try {
            if (!API.isLoggedIn()) return;
            var data = await API.get('/store-config');
            if (data && Object.keys(data).length > 0) {
                save(data);
            }
        } catch (e) {
            console.error('StoreConfig sync error:', e);
        }
    }
    async function syncToServer() {
        try {
            if (!API.isLoggedIn()) return;
            var cfg = getAll();
            await API.put('/store-config', cfg);
        } catch (e) {
            console.error('StoreConfig syncToServer error:', e);
        }
    }
    return { getAll: getAll, get: get, set: set, save: save, formatCurrency: formatCurrency, formatDate: formatDate, getStoreName: getStoreName, getCurrency: getCurrency, getLowStockThreshold: getLowStockThreshold, getPharmacyName: getPharmacyName, syncFromServer: syncFromServer, syncToServer: syncToServer, defaults: defaults, KEY: KEY };
})();

var Native = (function() {
    var Capacitor = null;
    var ready = false;
    var loading = false;
    function ensureLoaded() {
        if (ready) return Capacitor;
        if (window.Capacitor) { Capacitor = window.Capacitor; ready = true; return Capacitor; }
        return null;
    }
    function loadCapacitor() {
        if (loading || window.Capacitor) return Promise.resolve(window.Capacitor);
        loading = true;
        return new Promise(function(resolve) {
            var s = document.createElement('script');
            s.src = 'https://cdn.jsdelivr.net/npm/@capacitor/core@6/dist/capacitor.cdn.js';
            s.onload = function() { Capacitor = window.Capacitor; ready = true; loading = false; resolve(Capacitor); };
            s.onerror = function() { loading = false; resolve(null); };
            document.head.appendChild(s);
        });
    }
    function isNative() { try { return window.Capacitor && window.Capacitor.isPlatformAvailable ? window.Capacitor.isPlatformAvailable('android') || window.Capacitor.isPlatformAvailable('ios') : !!window.Capacitor; } catch (e) { return false; } }
    async function getDeviceInfo() {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.Device) return null;
        try { return await c.Device.getInfo(); } catch (e) { return null; }
    }
    async function impact(style) {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.Haptics) return;
        try { await c.Haptics.impact({ style: style || 'light' }); } catch (e) {}
    }
    async function notify(type) {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.Haptics) return;
        try { await c.Haptics.notification({ type: type || 'success' }); } catch (e) {}
    }
    async function setStatusBar(color) {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.StatusBar) return;
        try { await c.StatusBar.setBackgroundColor({ color: color || '#0f172a' }); } catch (e) {}
    }
    async function showSplash() {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.SplashScreen) return;
        try { await c.SplashScreen.show(); } catch (e) {}
    }
    async function hideSplash() {
        if (!window.Capacitor) await loadCapacitor();
        var c = ensureLoaded();
        if (!c || !c.SplashScreen) return;
        try { await c.SplashScreen.hide(); } catch (e) {}
    }
    function init() {
        ensureLoaded();
        if (isNative()) {
            document.body.classList.add('app-native');
            setStatusBar('#0f172a');
        }
    }
    return { init: init, isNative: isNative, getDeviceInfo: getDeviceInfo, impact: impact, notify: notify, setStatusBar: setStatusBar, showSplash: showSplash, hideSplash: hideSplash };
})();

var Theme = (function() {
    var KEY = 'danzona_theme';
    var dark = false;
    var toggleEl = null;
    function load() {
        try { dark = localStorage.getItem(KEY) === 'dark'; } catch (e) { dark = false; }
        apply();
    }
    function save() { try { localStorage.setItem(KEY, dark ? 'dark' : 'light'); } catch (e) {} }
    function apply() {
        if (dark) document.documentElement.setAttribute('data-theme', 'dark');
        else document.documentElement.removeAttribute('data-theme');
        if (toggleEl) toggleEl.innerHTML = dark ? '<i class="fas fa-sun"></i> Light' : '<i class="fas fa-moon"></i> Dark';
        var lbl = document.getElementById('themeToggleLabel');
        if (lbl) lbl.textContent = dark ? 'Light Mode' : 'Dark Mode';
    }
    function toggle() {
        dark = !dark;
        apply();
        save();
    }
    function isDark() { return dark; }
    function init() {
        load();
        var el = document.getElementById('themeToggle');
        if (el) { toggleEl = el; toggleEl.onclick = function(e) { e.stopPropagation(); toggle(); }; }
    }
    return { init: init, toggle: toggle, isDark: isDark, load: load, apply: apply };
})();

var Notifications = (function() {
    var list = [];
    var panelEl = null;
    var bellEl = null;
    var badgeEl = null;
    function getPanel() {
        if (!panelEl) panelEl = document.getElementById('notifPanel') || document.createElement('div');
        if (panelEl && !panelEl.parentNode) document.body.appendChild(panelEl);
        return panelEl;
    }
    function render() {
        var unread = list.filter(function(m) { return String(m.status || '').toLowerCase() === 'unread'; }).length;
        if (badgeEl) { badgeEl.textContent = unread > 0 ? unread : ''; badgeEl.className = 'notif-badge' + (unread > 0 ? '' : ' hidden'); }
        var html = '';
        if (!list.length) {
            html = '<div class="notif-empty"><i class="fas fa-bell-slash"></i><div style="margin-top:6px">No notifications</div></div>';
        } else {
            html = list.map(function(m) {
                var unreadCls = String(m.status || '').toLowerCase() === 'unread' ? 'unread' : '';
                var icon = String(m.status || '').toLowerCase() === 'unread' ? 'fas fa-bell' : 'fas fa-bell';
                var subject = esc(m.subject || 'Notification');
                var body = esc(m.body || '');
                var time = m.created_at ? new Date(m.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
                var mid = m.id || 0;
                return '<div class="notif-item ' + unreadCls + '" onclick="Notifications.markRead(' + mid + ')">' +
                    '<div class="ni-icon"><i class="' + icon + '"></i></div>' +
                    '<div class="ni-content">' +
                    '<span class="ni-subject">' + subject + '</span>' +
                    '<span class="ni-body">' + body + '</span>' +
                    (time ? '<span class="ni-time">' + time + '</span>' : '') +
                    '</div>' +
                    '</div>';
            }).join('');
        }
        var panel = getPanel();
        panel.innerHTML = '<div class="notif-header"><strong>Notifications</strong><span class="notif-mark" onclick="Notifications.markAllRead(event)">Mark all as read</span></div>' +
            '<div class="notif-body">' + html + '</div>' +
            '<div class="notif-footer"><button class="btn btn-secondary" onclick="Notifications.toggle()">Close</button></div>';
    }
    function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
    function load() {
        if (!API || !API.isLoggedIn || !API.isLoggedIn()) return;
        API.getMessages ? API.getMessages().then(function(data) {
            list = Array.isArray(data) ? data : [];
            render();
        }).catch(function() { list = []; render(); }) : (list = [], render());
    }
    function toggle() {
        if (!panelEl) { getPanel(); }
        if (!panelEl) return;
        var open = panelEl.classList.contains('open');
        if (open) { panelEl.classList.remove('open'); return; }
        panelEl.classList.add('open');
        render();
        document.addEventListener('click', function closeOutside(e) {
            if (!panelEl.contains(e.target) && (!bellEl || !bellEl.contains(e.target))) {
                panelEl.classList.remove('open');
                document.removeEventListener('click', closeOutside);
            }
        });
    }
    function markRead(mid, e) {
        if (e) e.stopPropagation();
        if (!API || !API.updateMessage) return;
        API.updateMessage(mid, { status: 'read' }).then(function() {
            var m = list.find(function(x) { return String(x.id) === String(mid); });
            if (m) m.status = 'read';
            render();
        }).catch(function() {});
    }
    function markAllRead(e) {
        if (e) e.stopPropagation();
        if (!API || !API.updateMessage) return;
        var unread = list.filter(function(m) { return String(m.status || '').toLowerCase() === 'unread'; });
        var pending = unread.length;
        if (!pending) return;
        unread.forEach(function(m) {
            API.updateMessage(m.id, { status: 'read' }).then(function() {
                pending--;
                if (pending === 0) { list.forEach(function(x) { x.status = 'read'; }); render(); }
            }).catch(function() { pending--; if (pending === 0) render(); });
        });
    }
    return { load: load, toggle: toggle, markRead: markRead, markAllRead: markAllRead, render: render, getPanel: getPanel, setBell: function(el) { bellEl = el; }, setBadge: function(el) { badgeEl = el; } };
})();

var POS = (function() {
    var pages = {
        'index.html': { label: 'Home', icon: 'fa-home' },
        'dashboard.html': { label: 'Dashboard', icon: 'fa-home' },
        'sales.html': { label: 'SALES', icon: 'fa-shopping-cart' },
        'suspended-sales.html': { label: 'Suspended Sales', icon: 'fa-pause' },
        'receipt.html': { label: 'Receipt', icon: 'fa-receipt' },
        'variations.html': { label: 'Add / Edit Product', icon: 'fa-plus-circle' },
        'inventory.html': { label: 'Inventory', icon: 'fa-boxes' },
        'customers.html': { label: 'Customers', icon: 'fa-users' },
        'suppliers.html': { label: 'Suppliers', icon: 'fa-truck' },
        'reports.html': { label: 'Reports', icon: 'fa-chart-bar' },
        'receiving.html': { label: 'Receiving', icon: 'fa-file-import' },
        'expenses.html': { label: 'Expenses', icon: 'fa-receipt' },
        'employees.html': { label: 'Employees', icon: 'fa-user-tie' },
        'shifts.html': { label: 'Shift Manager', icon: 'fa-clock' },
        'appointments.html': { label: 'Appointments', icon: 'fa-calendar' },
        'giftcards.html': { label: 'Gift Cards', icon: 'fa-gift' },
        'invoices.html': { label: 'Invoices', icon: 'fa-file-invoice' },
        'deliveries.html': { label: 'Deliveries', icon: 'fa-truck-loading' },
        'cashier-closeout.html': { label: 'Cashier Closeout', icon: 'fa-calculator' },
        'sales-returns.html': { label: 'Sales Returns', icon: 'fa-rotate-left' },
        'audit-log.html': { label: 'Audit Log', icon: 'fa-clipboard-list' },
        'stock-transfer.html': { label: 'Stock Transfer', icon: 'fa-truck-ramp-box' },
        'stock-count.html': { label: 'Stock Count', icon: 'fa-clipboard-check' },
        'purchase-orders.html': { label: 'Purchase Orders', icon: 'fa-file-invoice-dollar' },
        'daily-summary.html': { label: 'Daily Sales Summary', icon: 'fa-calendar-day' },
        'bank-reconciliation.html': { label: 'Bank Reconciliation', icon: 'fa-building-columns' },
        'user-roles.html': { label: 'User Roles & Permissions', icon: 'fa-user-shield' },
        'tax-settings.html': { label: 'Tax & Vat', icon: 'fa-percent' },
        'backups.html': { label: 'System Backups', icon: 'fa-download' },
        'promo-engine.html': { label: 'Promos & Discounts', icon: 'fa-tags' },
        'prescriptions.html': { label: 'Prescriptions / Rx', icon: 'fa-prescription' },
        'expiry-alerts.html': { label: 'Expiry & Batch Alerts', icon: 'fa-triangle-exclamation' },
        'drug-categories.html': { label: 'Drug Categories', icon: 'fa-tags' },
        'payments.html': { label: 'Payments', icon: 'fa-credit-card' },
        'locations.html': { label: 'Locations', icon: 'fa-store' },

        'messages.html': { label: 'Messages', icon: 'fa-envelope' },
        'config.html': { label: 'Store Config', icon: 'fa-cog' },
        'login.html': { label: 'Logout', icon: 'fa-sign-out-alt' }
    };
    function $(id) { return document.getElementById(id); }
    function esc(value) {
        var text = value == null ? '' : String(value);
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }
    function navigateTo(page) { window.location.href = page; }
    function formatCurrency(value) { try { return StoreConfig.formatCurrency(value); } catch (e) { return '₦' + (parseFloat(value) || 0).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } }
    function formatNumber(value) { try { var locale = StoreConfig.get('currencyLocale') || 'en-NG'; return (parseFloat(value) || 0).toLocaleString(locale); } catch (e) { return (parseFloat(value) || 0).toLocaleString('en-NG'); } }
    function formatDate(value, options) {
        if (!value) return '-';
        try { var locale = StoreConfig.get('currencyLocale') || 'en-NG'; return new Date(value).toLocaleDateString(locale, options || { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return new Date(value).toLocaleDateString('en-NG', options || { day: 'numeric', month: 'short', year: 'numeric' }); }
    }
    function today() { return new Date().toISOString().split('T')[0]; }
    function getDatePart(d) {
        if (!d) return '';
        var s = String(d);
        var idx = s.indexOf(' ');
        return idx > -1 ? s.substring(0, idx) : s;
    }
    function getQueryParameter(name) { return new URLSearchParams(window.location.search).get(name) || ''; }
    function showToast(message, isError) {
        var t = $('toast');
        if (!t) return;
        t.textContent = message;
        t.className = 'toast' + (isError ? ' error' : '');
        t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3500);
    }
    function openModal(id) { var el = $(id); if (el) el.classList.add('open'); }
    function closeModal(id) { var el = $(id); if (el) el.classList.remove('open'); }
    function csvCell(value) {
        var text = value == null ? '' : String(value);
        return '"' + text.split('"').join('""') + '"';
    }
    function exportCSV(filename, headers, rows) {
        var lines = [headers.map(csvCell).join(',')];
        rows.forEach(function(row) { lines.push(headers.map(function(h) { return csvCell(row[h] == null ? '' : row[h]); }).join(',')); });
        var blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('CSV exported');
    }
    function printTable(title, headers, rows) {
        var html = '<html><head><title>' + esc(title) + '</title><style>body{font-family:Inter,Arial,sans-serif;padding:24px;}table{width:100%;border-collapse:collapse;}th,td{border:1px solid #ddd;padding:10px;text-align:left;}th{background:#f8fafc;}h2{text-align:center;color:#10b981;}</style></head><body><h2>' + esc(title) + '</h2><p>Generated: ' + esc(new Date().toLocaleString()) + '</p><table><thead><tr>';
        headers.forEach(function(h) { html += '<th>' + esc(h) + '</th>'; });
        html += '</tr></thead><tbody>';
        rows.forEach(function(row) { html += '<tr>'; headers.forEach(function(h) { html += '<td>' + esc(row[h] == null ? '' : row[h]) + '</td>'; }); html += '</tr>'; });
        html += '</tbody></table></body></html>';
        var win = window.open('', '', 'width=980,height=700');
        if (win) { win.document.write(html); win.document.close(); win.focus(); win.print(); }
    }
    var pageConfig = null;
    var userAccess = null;
    var DEFAULT_GROUPS = [
        {title:'Main',items:[['index.html','Home','fa-home'],['dashboard.html','Dashboard','fa-home'],['sales.html','SALES','fa-shopping-cart'],['suspended-sales.html','Suspended Sales','fa-pause'],['variations.html','Add Product','fa-plus-circle'],['inventory.html','Inventory','fa-boxes'],['receiving.html','Receiving','fa-file-import'],['reports.html','Reports','fa-chart-bar']]},
        {title:'Catalogue',items:[['customers.html','Customers','fa-users'],['suppliers.html','Suppliers','fa-truck'],['locations.html','Locations','fa-store'],['product-variations.html','Product Variations','fa-layer-group']]},
        {title:'Pharmacy',items:[['prescriptions.html','Prescriptions / Rx','fa-prescription'],['expiry-alerts.html','Expiry & Batch Alerts','fa-triangle-exclamation'],['drug-categories.html','Drug Categories','fa-tags']]},
        {title:'Finance',items:[['payments.html','Payments','fa-credit-card'],['store_account_payment.html','Store Account','fa-wallet'],['bank-reconciliation.html','Bank Reconciliation','fa-building-columns'],['tax-settings.html','Tax & Vat','fa-percent'],['promo-engine.html','Promos & Discounts','fa-tags'],['expenses.html','Expenses','fa-receipt'],['invoices.html','Invoices','fa-file-invoice'],['purchase-orders.html','Purchase Orders','fa-file-invoice-dollar']]},
        {title:'Operations',items:[['employees.html','Employees','fa-user-tie'],['user-roles.html','User Roles','fa-user-shield'],['appointments.html','Appointments','fa-calendar'],['shifts.html','Shift Manager','fa-clock'],['suspended-sales.html','Suspended Sales','fa-pause'],['receipt.html','Receipt','fa-receipt'],['todays-receipts.html','Today\'s Receipts','fa-receipt'],['audit.html','Audit Log','fa-clipboard-list'],['giftcards.html','Gift Cards','fa-gift'],['deliveries.html','Deliveries','fa-truck-loading'],['cashier-closeout.html','Cashier Closeout','fa-calculator'],['daily-summary.html','Daily Sales Summary','fa-calendar-day'],['sales-returns.html','Sales Returns','fa-rotate-left'],['stock-transfer.html','Stock Transfer','fa-truck-ramp-box'],['stock-count.html','Stock Count','fa-clipboard-check'],['messages.html','Messages','fa-envelope']]},
        {title:'Reports',items:[['audit-log.html','Audit Log','fa-clipboard-list'],['backups.html','System Backups','fa-download'],['config.html','Store Config','fa-cog'],['customer-history.html','Customer History','fa-user-clock']]},
        {title:'Administration',items:[['admin.html','Admin Panel','fa-shield-halved']]},
        {title:'Session',items:[['login.html','Logout','fa-sign-out-alt']]}
    ];
    var ADMIN_ROLES = ['admin', 'administrator', 'owner', 'super_admin', 'superadmin'];
    var PHARMACY_ONLY_PAGES = ['prescriptions.html', 'expiry-alerts.html', 'drug-categories.html'];
    function defaultGroups() {
        var type = '';
        try { type = (API.getBusinessType ? API.getBusinessType() : '') || ''; } catch (e) { type = ''; }
        if (!type || type === 'pharmacy') return DEFAULT_GROUPS;
        return DEFAULT_GROUPS.map(function(g) {
            return {
                title: g.title,
                items: g.items.filter(function(it) { return PHARMACY_ONLY_PAGES.indexOf(it[0]) === -1; })
            };
        }).filter(function(g) { return g.items.length; });
    }
    function isAdminRole() {
        var role = '';
        try { role = (API.getRole ? API.getRole() : '') || ''; } catch (e) { role = ''; }
        return ADMIN_ROLES.indexOf(String(role).trim().toLowerCase()) > -1;
    }
    function currentPageKey() {
        var path = window.location.pathname.split('/').pop();
        return path || 'index.html';
    }
    function buildGroupsFromConfig() {
        if (!pageConfig || !pageConfig.length) return null;
        var order = [];
        var map = {};
        pageConfig.forEach(function(p) {
            if (!p.enabled) return;
            if (p.module_enabled === false) return;
            if (p.admin_only && !isAdminRole()) return;
            if (!canAccessPage(p.key)) return;
            var groupName = p.group || 'Other';
            if (!map[groupName]) { map[groupName] = []; order.push(groupName); }
            map[groupName].push(p);
        });
        return order.map(function(title) {
            return {
                title: title,
                items: map[title]
                    .sort(function(a, b) { return (a.sort_order || 0) - (b.sort_order || 0); })
                    .map(function(p) { return [p.key, p.label, p.icon]; })
            };
        }).filter(function(g) { return g.items.length; });
    }
    function canAccessPage(key) {
        if (!userAccess) return true;
        if (userAccess.is_admin) return true;
        if (!userAccess.pages) return true;
        return userAccess.pages.indexOf(key) > -1;
    }
    async function loadUserAccess() {
        try {
            if (!API.isLoggedIn || !API.isLoggedIn()) return userAccess;
            var res = await API.get('/me/access');
            if (res && res.username) {
                userAccess = res;
                try { localStorage.setItem('danzona_user_access', JSON.stringify(res)); } catch (e) {}
                if (res.business && API.setBusiness) {
                    try { API.setBusiness(res.business); } catch (e2) {}
                }
            }
        } catch (e) {
            try {
                var cached = JSON.parse(localStorage.getItem('danzona_user_access') || 'null');
                if (cached && cached.username) userAccess = cached;
            } catch (e2) { userAccess = null; }
        }
        return userAccess;
    }
    function fallbackPage() {
        var allowed = function(p) {
            return p && p.enabled && p.module_enabled !== false && (!p.admin_only || isAdminRole()) && canAccessPage(p.key);
        };
        if (pageConfig && pageConfig.length) {
            for (var i = 0; i < pageConfig.length; i++) {
                if (pageConfig[i].key === 'dashboard.html' && allowed(pageConfig[i])) return 'dashboard.html';
            }
            for (var j = 0; j < pageConfig.length; j++) {
                if (allowed(pageConfig[j])) return pageConfig[j].key;
            }
        }
        return 'login.html';
    }
    async function loadPageConfig() {
        try {
            if (!API.isLoggedIn || !API.isLoggedIn()) return pageConfig;
            var pages = await API.get('/admin/pages');
            if (Array.isArray(pages) && pages.length) {
                pageConfig = pages;
                try { localStorage.setItem('danzona_page_config', JSON.stringify(pages)); } catch (e) {}
            }
        } catch (e) {
            try {
                var cached = JSON.parse(localStorage.getItem('danzona_page_config') || 'null');
                if (cached && cached.length) pageConfig = cached;
            } catch (e2) { pageConfig = null; }
        }
        return pageConfig;
    }
    function checkPageAccess() {
        var current = currentPageKey();
        if (pageConfig && pageConfig.length) {
            var entry = null;
            pageConfig.forEach(function(p) { if (p.key === current) entry = p; });
            if (entry) {
                if (entry.admin_only && !isAdminRole()) {
                    showToast('You do not have access to this page', true);
                    navigateTo(fallbackPage());
                    return false;
                }
                if (entry.module_enabled === false) {
                    showToast('This area is not available for your business type', true);
                    navigateTo(fallbackPage());
                    return false;
                }
                if (!entry.enabled) {
                    showToast('This page has been disabled by the administrator', true);
                    navigateTo(fallbackPage());
                    return false;
                }
            }
        }
        if (!canAccessPage(current)) {
            showToast('You do not have access to this page', true);
            navigateTo(fallbackPage());
            return false;
        }
        return true;
    }
    function renderSidebar() {
        var el = $('sidebar');
        if (!el) return;
        var current = currentPageKey();
        var groups = buildGroupsFromConfig() || defaultGroups();
        el.innerHTML = '<div class="sidebar-header"><div class="sidebar-brand"><img class="brand-logo" src="brand-logo.png" alt="' + esc(StoreConfig.getStoreName()) + ' logo"><div><h1>' + esc(StoreConfig.getStoreName()) + '</h1><p>Point of Sale System</p></div></div></div><div class="sidebar-body">' + groups.map(function(group){return '<div class="sidebar-section"><div class="sidebar-section-title">'+esc(group.title)+'</div>'+group.items.map(function(item){var href = item[0], label = esc(item[1]), icon = item[2], isExternal = href.indexOf('http://') === 0 || href.indexOf('https://') === 0; return '<a class="sidebar-link '+(item[0]===current?'active':'')+'" href="' + esc(href) + '"' + (isExternal ? ' target="_blank" rel="noopener"' : ' onclick="POS.navigateTo(\'' + esc(href).replace(/'/g, "\\'") + '\');return false;"') + '><i class="fas ' + esc(icon) + '"></i><span>' + label + '</span></a>';}).join('')+'</div>';}).join('')+'</div><div class="sidebar-footer"><div><strong>' + esc(StoreConfig.getStoreName()) + '</strong><span>Secure POS Session</span></div><i class="fas fa-shield-alt"></i></div>';
    }
    function setupMobileSidebar() {
        var header = document.querySelector('.header');
        if (header && !$('sidebarToggle')) {
            var btn = document.createElement('button');
            btn.id = 'sidebarToggle';
            btn.className = 'sidebar-toggle';
            btn.setAttribute('aria-label', 'Open menu');
            btn.innerHTML = '<i class="fas fa-bars"></i>';
            btn.addEventListener('click', toggleSidebar);
            header.insertBefore(btn, header.firstChild);
        }
        if (!$('sidebarBackdrop')) {
            var bd = document.createElement('div');
            bd.id = 'sidebarBackdrop';
            bd.className = 'sidebar-backdrop';
            document.body.appendChild(bd);
            bd.addEventListener('click', closeSidebar);
        }
        var sb = $('sidebar');
        if (sb) sb.addEventListener('click', function(e) { if (e.target.closest('a')) closeSidebar(); });
    }
    function toggleSidebar() {
        var s = $('sidebar'), b = $('sidebarBackdrop');
        if (s) s.classList.toggle('open');
        if (b) b.classList.toggle('open');
    }
    function closeSidebar() {
        var s = $('sidebar'), b = $('sidebarBackdrop');
        if (s) s.classList.remove('open');
        if (b) b.classList.remove('open');
    }
    function renderUserMenu() {
        var el = $('userMenu');
        if (!el) return;
        var name = API.getUserName ? API.getUserName() : 'Admin User';
        var role = API.getRole ? API.getRole() : 'admin';
        var pharm = API.getPharmacyName ? API.getPharmacyName() : 'Shanks Shop Management';
        // notification bell
        var bellHtml = '<div class="notif-wrap"><button class="notif-bell" id="notifBell" aria-label="Notifications"><i class="fas fa-bell"></i></button><span class="notif-badge hidden" id="notifBadge">0</span></div>';
        el.innerHTML = '<span class="user-avatar"><i class="fas fa-user"></i></span><div class="user-text"><strong>' + esc(name || 'Admin User') + '</strong><small>' + esc(role || 'Role') + '</small></div><i class="fas fa-chevron-down"></i><div class="user-dropdown"><div class="user-info"><strong>' + esc(name || 'Admin User') + '</strong><small>' + esc(pharm || 'Shanks Shop Management') + '</small></div><hr><a href="#" id="themeToggle" onclick="Theme.toggle();return false;"><i class="fas fa-moon"></i> <span id="themeToggleLabel">Dark Mode</span></a><a href="#" onclick="POS.navigateTo(\'config.html\');return false;"><i class="fas fa-cog"></i> Settings</a><a href="#" onclick="POS.navigateTo(\'payments.html\');return false;"><i class="fas fa-credit-card"></i> Store Payments</a><a href="#" onclick="POS.switchToAdmin();return false;"><i class="fas fa-user-shield"></i> Switch to Admin</a><hr><a href="#" onclick="POS.logout();return false;"><i class="fas fa-sign-out-alt"></i> Logout</a></div>' + bellHtml;
        // attach notification panel once
        if (!$('notifPanel')) {
            var panel = document.createElement('div');
            panel.id = 'notifPanel';
            panel.className = 'notif-panel';
            document.body.appendChild(panel);
        }
        Notifications.setBell($('notifBell'));
        Notifications.setBadge($('notifBadge'));
        $('notifBell').onclick = function(e) { e.stopPropagation(); Notifications.toggle(); };
    }
    function switchToAdmin() {
        if (API.init) API.init('', '', '', { name: 'Admin User', role: 'admin' }, '');
        renderUserMenu();
        showToast('Switched to Admin User');
    }
    function logout() {
        if (!confirm('Are you sure you want to logout?')) return;
        if (API.logout) API.logout();
        navigateTo('login.html');
    }
    function statusBadge(status, extraClass) {
        var s = String(status || '').toLowerCase();
        var cls = 'badge';
        if (extraClass) cls += ' ' + extraClass;
        else if (['active', 'paid', 'completed', 'delivered', 'scheduled', 'read', 'in_stock', 'high', 'confirmed'].indexOf(s) > -1) cls += ' badge-success';
        else if (['inactive', 'cancelled', 'expired', 'used', 'outstanding', 'overdue', 'delayed', 'low', 'out', 'unread', 'pending', 'draft', 'partial'].indexOf(s) > -1) cls += ' badge-warning';
        else cls += ' badge-info';
        return '<span class="' + cls + '">' + esc(status || 'Draft') + '</span>';
    }
    function debounce(fn, delay) {
        var t;
        return function() {
            var args = arguments;
            clearTimeout(t);
            t = setTimeout(function() { fn.apply(null, args); }, delay || 250);
        };
    }
function renderSubWarning(sub) {
        var banner = $('subWarningBanner');
        if (!banner) return;
        if (!sub || !sub.sub_status || sub.sub_status === 'none') {
            banner.style.display = 'none';
            return;
        }
        var status = String(sub.sub_status || '').toLowerCase();
        var planName = sub.plan_name || 'your plan';
        var price = sub.plan_price_yearly ? ' (₦' + parseFloat(sub.plan_price_yearly).toLocaleString('en-NG') + '/yr)' : '';
        var endsAt = sub.current_period_end || sub.trial_ends_at;
        var daysLeft = '';
        if (endsAt) {
            var diffMs = new Date(endsAt) - new Date();
            var days = Math.ceil(diffMs / 86400000);
            if (days > 0) daysLeft = ' - ' + days + ' day(s) left';
            else if (days === 0) daysLeft = ' - expires today';
            else daysLeft = ' - expired ' + Math.abs(days) + ' day(s) ago';
        }
        var cls = 'ok', icon = 'fas fa-circle-check', text = '';
        if (status === 'active') {
            cls = 'ok'; icon = 'fas fa-circle-check';
            text = 'Your subscription to <strong>' + planName + '</strong> is active' + price + daysLeft + '. Enjoy full access.';
        } else if (status === 'trial') {
            cls = 'warn'; icon = 'fas fa-hourglass-half';
            text = 'You are on a <strong>free trial</strong> for ' + planName + daysLeft + '. Upgrade to keep all features after the trial ends.';
        } else if (status === 'expired' || status === 'cancelled') {
            cls = 'expired'; icon = 'fas fa-exclamation-triangle';
            text = 'Your ' + planName + ' subscription has expired or been cancelled. Some features are limited until you renew.';
        } else {
            cls = 'warn'; icon = 'fas fa-exclamation-triangle';
            text = 'Your subscription status is "<strong>' + status + '</strong>". Please renew to avoid service interruption.';
        }
        var renewHref = 'payments.html';
        banner.className = 'sub-warning ' + cls;
        banner.style.display = 'flex';
        banner.innerHTML = '<span class="sw-icon"><i class="' + icon + '"></i></span>' +
            '<span class="sw-text">' + text + '</span>' +
            '<span class="sw-actions">' +
                '<button class="btn" onclick="POS.navigateTo(\'' + renewHref + '\')"><i class="fas fa-credit-card"></i> Renew / Subscribe</button>' +
            '</span>';
    }

    async function loadSubWarning() {
        try {
            if (!API || !API.hasOwnProperty('isLoggedIn') || !API.isLoggedIn()) return;
            var res = await API.get('/me/access');
            if (res && res.subscription !== undefined) {
                renderSubWarning(res.subscription);
            }
        } catch (e) {
            console.warn('Sub warning load failed', e);
        }
    }

    function startClock() {
        var el = $('topClock');
        if (!el) return;
        function update() {
            var now = new Date();
            el.innerHTML = '<i class="fas fa-clock"></i> ' + now.toLocaleString('en-NG', {
                weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
        update();
        setInterval(update, 1000);
    }
    function initCommon() {
        Native.init();
        Theme.init();
        renderSidebar();
        renderUserMenu();
        Theme.apply();
        Notifications.load();
        setupMobileSidebar();
        startClock();
        var name = $('pharmacyName') || $('pharmacyNameDisplay');
        if (name && API.getPharmacyName) name.innerHTML = '<i class="fas fa-clinic-medical"></i> ' + esc(API.getPharmacyName() || 'Shanks Shop Management');
        if (API.isLoggedIn && API.isLoggedIn()) {
            Promise.all([loadPageConfig(), loadUserAccess(), loadSubWarning()]).then(function() {
                renderSidebar();
                checkPageAccess();
            });
        }
}
    function requireAuth() {
        if (API.isLoggedIn && API.isLoggedIn()) return true;
        if (getQueryParameter('demo') === '1') return true;
        navigateTo('login.html');
        return false;
    }
    function getPrinterType(){try{return StoreConfig.get('printerType')||'small';}catch(e){return 'small';}}
    function getReceiptConfig(){try{return{footerText:StoreConfig.get('footerText')||'Thank you for choosing Shanks Shop Management!',storeName:StoreConfig.getPharmacyName(),storeAddress:StoreConfig.get('storeAddress')||'',phone:StoreConfig.get('phoneNumber')||''};}catch(e){return{footerText:'Thank you for choosing Shanks Shop Management!',storeName:'Shanks Shop Management',storeAddress:'',phone:''};}}
    function fmt(v){try{return StoreConfig.formatCurrency(v);}catch(e){return '₦'+(parseFloat(v)||0).toLocaleString('en-NG',{minimumFractionDigits:2});}}
    function toNum(v, f) { var n = parseFloat(v); return isNaN(n) ? (f || 0) : n; }
    function pkgTypesOf(product) {
        if (!product) return [];
        var list = product.packaging_types || product.packagingTypes || [];
        if (typeof list === 'string') { try { list = JSON.parse(list); } catch (e) { list = []; } }
        return Array.isArray(list) ? list : [];
    }
    function pkgTypeOf(product, pkgId) {
        if (pkgId === null || pkgId === undefined || pkgId === '') return null;
        var list = pkgTypesOf(product);
        for (var i = 0; i < list.length; i++) {
            var pkg = list[i];
            if (!pkg) continue;
            if (String(pkg.id) === String(pkgId)) return pkg;
            if (pkg.name && String(pkg.name) === String(pkgId)) return pkg;
        }
        return null;
    }
    // Cost of ONE package (e.g. one carton), not of one base unit.
    // A package that carries no cost of its own falls back to the product's
    // base-unit cost multiplied by the number of base units it holds.
    function pkgCost(product, pkgId, pkgQty) {
        if (!product) return 0;
        var baseCost = toNum(product.cost_price != null ? product.cost_price : product.costPrice);
        var pkg = pkgTypeOf(product, pkgId);
        var units = 1;
        if (pkg) {
            units = Math.max(1, toNum(pkg.qty, 1));
            var own = toNum(pkg.cost_price != null ? pkg.cost_price : pkg.costPrice);
            if (own > 0) return own;
        } else if (pkgQty) {
            units = Math.max(1, toNum(pkgQty, 1));
        }
        return baseCost * units;
    }
    function findProduct(products, id) {
        if (!products || id === null || id === undefined || id === '') return null;
        for (var i = 0; i < products.length; i++) {
            var p = products[i];
            if (!p) continue;
            if (p.id !== undefined && String(p.id) === String(id)) return p;
            if (p.product_id !== undefined && String(p.product_id) === String(id)) return p;
        }
        return null;
    }
    // Cost of a sold line. The cost captured on the sale line wins so historic
    // profit does not change when a product is re-priced later; otherwise the
    // cost price of the package type that was sold is used.
    function lineCost(item, products) {
        if (!item) return 0;
        var qty = toNum(item.qty, 1);
        var unit = null;
        if (item.cost_price !== undefined && item.cost_price !== null) unit = toNum(item.cost_price);
        else if (item.costPrice !== undefined && item.costPrice !== null) unit = toNum(item.costPrice);
        else if (item.cost !== undefined && item.cost !== null) unit = toNum(item.cost);
        if (unit === null || unit <= 0) {
            var product = findProduct(products, item.product_id != null ? item.product_id : item.id);
            unit = pkgCost(product, item.pkg_type != null ? item.pkg_type : item.pkgType, item.pkg_qty);
        }
        return unit * qty;
    }
    function lineRevenue(item) {
        if (!item) return 0;
        var qty = toNum(item.qty, 1);
        var price = item.unit_price !== undefined && item.unit_price !== null ? toNum(item.unit_price) : toNum(item.price);
        var discount = toNum(item.discount);
        var total = item.line_total !== undefined && item.line_total !== null ? toNum(item.line_total) : (price * qty - discount);
        return total;
    }
    // Revenue, cost of goods and profit for a set of sales.
    function profitSummary(sales, products) {
        var revenue = 0, cogs = 0, tax = 0, count = 0;
        (sales || []).forEach(function (s) {
            if (!s) return;
            if (String(s.status || 'completed') === 'void') return;
            count++;
            revenue += toNum(s.total);
            tax += toNum(s.tax);
            var items = s.items;
            if (typeof items === 'string') { try { items = JSON.parse(items); } catch (e) { items = []; } }
            if (!Array.isArray(items)) return;
            items.forEach(function (it) { cogs += lineCost(it, products); });
        });
        var profit = revenue - cogs;
        return {
            revenue: revenue, cogs: cogs, tax: tax, profit: profit, count: count,
            margin: revenue > 0 ? (profit / revenue) * 100 : 0
        };
    }
    function buildSmallReceipt(cart,sub,disc,total,tendered,paymentMethod,accountAmount){accountAmount=accountAmount||0;var pmLabel=paymentMethod==='store_account'?'Store Account':paymentMethod==='card'?'Card':paymentMethod==='pos'?'POS':paymentMethod==='giftcard'?'Gift Card':'Cash';var rc=getReceiptConfig();var logoUrl=new URL('brand-logo.png',document.baseURI).href;var paid=pmLabel==='Store Account'?total:tendered;var change=Math.max(0,paid-total);var now=new Date();var receiptNo='#POS'+Date.now().toString().slice(-6);var html='<html><head><title>Receipt</title><style>@page{size:80mm auto;margin:0}*,::before,::after{box-sizing:border-box}body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-size:12px;color:#111827;margin:0;background:#f3f4f6;-webkit-font-smoothing:antialiased}.receipt{width:80mm;max-width:80mm;margin:10px auto;background:#fff;border-radius:16px;padding:14px 16px;box-shadow:0 20px 60px rgba(0,0,0,.12)}@media print{body{background:#fff}.receipt{margin:0;width:80mm;max-width:80mm;box-shadow:none}}.receipt-header{text-align:center;margin-bottom:14px}.receipt-logo{width:42px;height:42px;border-radius:12px;object-fit:contain;background:#fff;border:1px solid #e5e7eb;margin-bottom:8px;padding:6px}.receipt-store{font-size:17px;font-weight:800;letter-spacing:.04em;color:#111827;margin:0}.receipt-meta{font-size:9px;color:#6b7280;margin-top:4px;line-height:1.5}.receipt-divider{border:none;border-top:1px solid #e5e7eb;margin:12px 0}.receipt-section-title{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#374151;margin:10px 0 6px}.item-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:12px;border-bottom:1px solid #f3f4f6}.item-name{flex:1;font-size:12px;color:#111827}.item-meta{font-size:10px;color:#6b7280;margin-top:2px}.item-qty{font-variant-numeric:tabular-nums;color:#6b7280}.item-price{font-variant-numeric:tabular-nums;font-weight:700;color:#111827;text-align:right}.discount-row{font-size:10px;color:#ef4444;justify-content:space-between;padding:4px 0;display:flex}.totals{margin-top:14px}.total-row{display:flex;justify-content:space-between;padding:5px 0;font-size:12px;color:#374151}.total-row.total{font-size:16px;font-weight:900;color:#111827;border-top:2px solid #111827;border-bottom:2px solid #111827;padding-top:8px;padding-bottom:8px;margin-top:6px}.payment-section{margin-top:14px;padding-top:10px;border-top:1px solid #f3f4f6}.payment-row{display:flex;justify-content:space-between;padding:4px 0;font-size:11.5px;color:#374151}.payment-row strong{color:#111827}.footer-text{margin-top:14px;font-size:9px;color:#6b7280;text-align:center;line-height:1.5;border-top:1px dashed #e5e7eb;padding-top:8px}</style></head><body><div class="receipt"><div class="receipt-header">'+(logoUrl?'<img src="'+logoUrl+'" alt="logo" class="receipt-logo">':'')+'<h1 class="receipt-store">'+esc(rc.storeName)+'</h1><div class="receipt-meta">'+(rc.storeAddress?esc(rc.storeAddress)+'<br>':'')+(rc.phone?esc(rc.phone)+'<br>':'')+'Date: '+now.toLocaleString()+'<br>Receipt: '+receiptNo+'<br>Cashier: '+esc(API.getUserName?API.getUserName():'Staff')+'</div></div><div class="receipt-divider"></div><div class="receipt-section-title">Items Purchased</div>';cart.forEach(function(it){var lt=(parseFloat(it.price)||0)*(parseFloat(it.qty)||0)-(parseFloat(it.discount)||0);html+='<div class="item-row"><div><div class="item-name">'+esc(it.name)+'</div><div class="item-meta">'+esc(it.qty)+' x '+fmt(it.price)+'</div></div><div class="item-price">'+fmt(lt)+'</div></div>';if(it.discount>0){html+='<div class="discount-row"><span>Discount</span><span>-'+fmt(it.discount)+'</span></div>';}});html+='<div class="totals"><div class="total-row"><span>Subtotal</span><span class="item-price">'+fmt(sub)+'</span></div>';if(disc>0){html+='<div class="total-row"><span>Discount</span><span class="item-price">-'+fmt(disc)+'</span></div>';}html+='<div class="total-row total"><span>Total</span><span>'+fmt(total)+'</span></div></div><div class="payment-section"><div class="payment-row"><strong>Payment Method</strong><span>'+esc(pmLabel)+'</span></div><div class="payment-row"><strong>Amount Paid</strong><span class="item-price">'+fmt(paid)+'</span></div><div class="payment-row"><strong>Change Due</strong><span class="item-price">'+fmt(change)+'</span></div>'+(accountAmount>0?'<div class="payment-row"><strong>Store Account</strong><span class="item-price">'+fmt(accountAmount)+'</span></div>':'')+'</div><div class="footer-text">'+esc(rc.footerText||'Thank you for your business!')+'</div></div></body></html>';return html;}function buildLargeReceipt(cart,sub,disc,total,tendered,paymentMethod,accountAmount){accountAmount=accountAmount||0;var pmLabel=paymentMethod==='store_account'?'Store Account':paymentMethod==='card'?'Card':paymentMethod==='pos'?'POS':paymentMethod==='giftcard'?'Gift Card':'Cash';var rc=getReceiptConfig();var logoUrl=new URL('brand-logo.png',document.baseURI).href;var paid=pmLabel==='Store Account'?total:tendered;var change=Math.max(0,paid-total);var now=new Date();var receiptNo='#POS'+Date.now().toString().slice(-6);var totalQty=0;cart.forEach(function(it){totalQty+=parseFloat(it.qty)||0;});var html='<html><head><title>Receipt</title><style>@page{size:A4;margin:10mm}*,::before,::after{box-sizing:border-box}body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-size:13px;color:#111827;margin:0;background:#f3f4f6;-webkit-font-smoothing:antialiased}.receipt{max-width:210mm;margin:0 auto;background:#fff;border-radius:20px;padding:26px 30px;box-shadow:0 24px 80px rgba(0,0,0,.14)}@media print{body{background:#fff;margin:0}.receipt{max-width:none;width:100%;box-shadow:none;border-radius:0;padding:0}}.receipt-header{text-align:center;margin-bottom:22px}.receipt-logo{width:56px;height:56px;border-radius:14px;object-fit:contain;background:#fff;border:1px solid #e5e7eb;margin-bottom:12px;padding:8px}.receipt-store{font-size:24px;font-weight:900;letter-spacing:.03em;color:#111827;margin:0;text-transform:uppercase}.receipt-meta{font-size:12px;color:#4b5563;margin-top:6px;line-height:1.7}.receipt-divider{border:none;border-top:1px solid #e5e7eb;margin:16px 0}.receipt-section-title{font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.12em;color:#374151;margin:16px 0 10px}.receipt-table{width:100%;border-collapse:collapse}.receipt-table th{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;text-align:left;padding:9px 6px;border-bottom:2px solid #e5e7eb}.receipt-table td{padding:9px 6px;font-size:12.5px;color:#111827;border-bottom:1px solid #f3f4f6;vertical-align:middle}.receipt-table td.qty,.receipt-table td.price{text-align:right}.receipt-table td.qty{text-align:center;font-variant-numeric:tabular-nums}.item-name{font-weight:700}.item-meta{font-size:10.5px;color:#6b7280;display:block;margin-top:2px}.totals{margin-top:18px}.total-row{display:flex;justify-content:space-between;padding:6px 0;font-size:13px;color:#374151}.total-row.total{font-size:18px;font-weight:900;color:#111827;border-top:2px solid #111827;border-bottom:2px solid #111827;padding-top:10px;padding-bottom:10px;margin-top:8px}.payment-section{margin-top:20px;padding-top:12px;border-top:1px solid #f3f4f6}.payment-row{display:flex;justify-content:space-between;padding:5px 0;font-size:12.5px;color:#374151}.payment-row strong{color:#111827}.footer-text{margin-top:20px;font-size:11px;color:#6b7280;text-align:center;line-height:1.7;border-top:1px dashed #e5e7eb;padding-top:10px}</style></head><body><div class="receipt"><div class="receipt-header">'+(logoUrl?'<img src="'+logoUrl+'" alt="logo" class="receipt-logo">':'')+'<h1 class="receipt-store">'+esc(rc.storeName)+'</h1><div class="receipt-meta">'+(rc.storeAddress?esc(rc.storeAddress)+'<br>':'')+(rc.phone?esc(rc.phone)+'<br>':'')+'Date: '+now.toLocaleString()+'<br>Receipt: '+receiptNo+'<br>Cashier: '+esc(API.getUserName?API.getUserName():'Staff')+'</div></div><div class="receipt-divider"></div><div class="receipt-section-title">Items Purchased</div><table class="receipt-table"><thead><tr><th style="text-align:left">Item</th><th style="text-align:right">Unit Price</th><th style="text-align:center">Qty</th><th style="text-align:right">Amount</th></tr></thead><tbody>';cart.forEach(function(it){var lt=(parseFloat(it.price)||0)*(parseFloat(it.qty)||0)-(parseFloat(it.discount)||0);html+='<tr><td><span class="item-name">'+esc(it.name)+'</span><span class="item-meta">'+esc(it.qty)+' x '+fmt(it.price)+'</span></td><td class="price">'+fmt(it.price)+'</td><td class="qty">'+esc(it.qty)+'</td><td class="price">'+fmt(lt)+'</td></tr>';if(it.discount>0){html+='<tr><td colspan="4" style="padding:4px 6px;font-size:10.5px;color:#ef4444;font-weight:700;">Discount: -'+fmt(it.discount)+'</td></tr>';}});html+='</tbody></table><div class="totals"><div class="total-row"><span>Subtotal</span><span>'+fmt(sub)+'</span></div>';if(disc>0){html+='<div class="total-row"><span>Discount</span><span>-'+fmt(disc)+'</span></div>';}html+='<div class="total-row total"><span>Total Amount</span><span>'+fmt(total)+'</span></div></div><div class="payment-section"><div class="payment-row"><strong>Payment Method</strong><span>'+esc(pmLabel)+'</span></div><div class="payment-row"><strong>Amount Paid</strong><span>'+fmt(paid)+'</span></div><div class="payment-row"><strong>Change Due</strong><span>'+fmt(change)+'</span></div>'+(accountAmount>0?'<div class="payment-row"><strong>Store Account</strong><span>'+fmt(accountAmount)+'</span></div>':'')+'</div><div class="footer-text">'+esc(rc.footerText||'Thank you for your business!')+'</div></div></body></html>';return html;}function escPosInit() { return [0x1B, 0x40]; }
    function escPosAlign(n) { return [0x1B, 0x61, n]; }
    function escPosBold(on) { return [0x1B, 0x45, on ? 1 : 0]; }
    function escPosDouble(on) { return [0x1B, 0x21, on ? 0x11 : 0x00]; }
    function escPosFeed(n) { return [0x1B, 0x64, n]; }
    function escPosCut() { return [0x1D, 0x56, 0x00]; }
    function escPosText(text) {
        var bytes = [];
        for (var i = 0; i < text.length; i++) {
            var c = text.charCodeAt(i);
            bytes.push(c < 0x80 ? c : 0x3F);
        }
        return bytes;
    }
    function escPosLine(text) { return escPosText(text).concat([0x0A]); }
    function escPosReceipt(lines) {
        var bytes = [];
        bytes = bytes.concat(escPosInit());
        bytes = bytes.concat(escPosAlign(1));
        bytes = bytes.concat(escPosBold(true));
        bytes = bytes.concat(escPosLine(lines[0] || 'SHANKS SHOP MANAGEMENT'));
        bytes = bytes.concat(escPosBold(false));
        bytes = bytes.concat(escPosAlign(0));
        for (var i = 1; i < lines.length; i++) {
            bytes = bytes.concat(escPosLine(lines[i]));
        }
        bytes = bytes.concat(escPosFeed(3));
        bytes = bytes.concat(escPosCut());
        return bytes;
    }
    async function printBluetooth(lines) {
        if (!navigator.bluetooth) {
            showToast('Web Bluetooth not supported on this device', true);
            return false;
        }
        try {
            var device = await navigator.bluetooth.requestDevice({
                filters: [{ services: [0xFF00] }],
                optionalServices: [0xFF00]
            });
            var server = await device.gatt.connect();
            var service = await server.getPrimaryService(0xFF00);
            var chars = await service.getCharacteristics();
            var char = chars[0];
            var bytes = escPosReceipt(lines);
            await char.writeValue(new Uint8Array(bytes));
            showToast('Receipt sent to thermal printer');
            return true;
        } catch (e) {
            showToast('Bluetooth print failed: ' + e.message, true);
            return false;
        }
    }
    return {
        $: $, esc: esc, navigateTo: navigateTo, formatCurrency: formatCurrency, formatNumber: formatNumber, formatDate: formatDate, today: today, getQueryParameter: getQueryParameter, showToast: showToast, openModal: openModal, closeModal: closeModal, exportCSV: exportCSV, printTable: printTable, renderSidebar: renderSidebar, renderUserMenu: renderUserMenu, switchToAdmin: switchToAdmin, logout: logout, statusBadge: statusBadge, debounce: debounce, initCommon: initCommon, requireAuth: requireAuth, getPrinterType: getPrinterType, buildSmallReceipt: buildSmallReceipt, buildLargeReceipt: buildLargeReceipt, fmt: fmt, startClock: startClock, loadPageConfig: loadPageConfig, loadUserAccess: loadUserAccess, checkPageAccess: checkPageAccess, isAdminRole: isAdminRole, canAccessPage: canAccessPage, getPageConfig: function() { return pageConfig; }, getUserAccess: function() { return userAccess; },
        pkgTypesOf: pkgTypesOf, pkgTypeOf: pkgTypeOf, pkgCost: pkgCost, findProduct: findProduct, lineCost: lineCost, lineRevenue: lineRevenue, profitSummary: profitSummary, printBluetooth: printBluetooth, escPosReceipt: escPosReceipt, getReceiptConfig: getReceiptConfig
    };
})();
window.POS = POS;
document.addEventListener('DOMContentLoaded', function() { POS.initCommon(); });
