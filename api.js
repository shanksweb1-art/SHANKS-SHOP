/* SHANKS SHOP MANAGEMENT - API Client
 * Multi-tenant API using X-API-Key authentication.
 * Usage: API.init(apiKey, username); then API.get('/products'), API.post('/sales', data), etc.
 */
var API = (function() {
    var BASE_URL = (typeof window !== 'undefined' && window.__API_BASE_URL) ? window.__API_BASE_URL : '/api';
    var apiKey = localStorage.getItem('danzona_api_key') || '';
    var username = localStorage.getItem('danzona_username') || '';
    var pharmacyName = localStorage.getItem('danzona_pharmacy_name') || '';
    var businessType = localStorage.getItem('danzona_business_type') || '';
    var businessModules = [];
    try {
        var rawModules = localStorage.getItem('danzona_business_modules');
        if (rawModules) businessModules = JSON.parse(rawModules) || [];
    } catch (e) {
        businessModules = [];
    }
    var currentUser = null;
    try {
        var raw = localStorage.getItem('danzona_current_user');
        if (raw) currentUser = JSON.parse(raw);
    } catch (e) {
        currentUser = null;
    }

    function headers() {
        var h = { 'Content-Type': 'application/json' };
        if (apiKey) h['X-API-Key'] = apiKey;
        if (username) h['X-Username'] = username;
        return h;
    }

    function logout() {
        localStorage.removeItem('danzona_api_key');
        localStorage.removeItem('danzona_username');
        localStorage.removeItem('danzona_pharmacy_name');
        localStorage.removeItem('danzona_business_type');
        localStorage.removeItem('danzona_business_modules');
        localStorage.removeItem('danzona_current_user');
        apiKey = '';
        username = '';
        pharmacyName = '';
        businessType = '';
        businessModules = [];
        currentUser = null;
    }

    function request(method, path, data) {
        return fetch(BASE_URL + path, {
            method: method,
            headers: headers(),
            body: data ? JSON.stringify(data) : null
        }).then(function(res) {
            if (res.status === 401) {
                logout();
                window.location.href = 'login.html';
                return Promise.reject(new Error('Session expired'));
            }
            if (!res.ok) {
                return res.text().then(function(text) {
                    var msg = 'Request failed';
                    try { var err = JSON.parse(text); msg = err.error || msg; } catch(e) {}
                    return Promise.reject(new Error(msg + ' (' + res.status + ')'));
                });
            }
            return res.json();
        });
    }

    return {
        init: function(key, uname, pharmName, user, storeId) {
            if (key) localStorage.setItem('danzona_api_key', key);
            if (uname) localStorage.setItem('danzona_username', uname);
            if (pharmName) localStorage.setItem('danzona_pharmacy_name', pharmName);
            if (user) localStorage.setItem('danzona_current_user', JSON.stringify(user));
            if (storeId) localStorage.setItem('danzona_store_id', storeId);
            apiKey = key || apiKey;
            username = uname || username;
            pharmacyName = pharmName || pharmacyName;
            currentUser = user || currentUser;
        },

        isLoggedIn: function() {
            return !!apiKey && !!username;
        },

        getRole: function() {
            if (currentUser && currentUser.role) return currentUser.role;
            return 'staff';
        },

        getUserName: function() {
            if (currentUser && currentUser.name) return currentUser.name;
            return username;
        },

        getPharmacyName: function() {
            return pharmacyName;
        },

        setBusiness: function(business) {
            if (!business) return;
            if (business.name) {
                pharmacyName = business.name;
                localStorage.setItem('danzona_pharmacy_name', business.name);
                localStorage.setItem('danzona_business_name', business.name);
            }
            if (business.business_type) {
                businessType = business.business_type;
                localStorage.setItem('danzona_business_type', business.business_type);
            }
            if (business.modules && business.modules.length) {
                businessModules = business.modules;
                localStorage.setItem('danzona_business_modules', JSON.stringify(business.modules));
            }
        },

        getBusinessType: function() {
            return businessType;
        },

        getBusinessModules: function() {
            return businessModules;
        },

        logout: function() { logout(); },

        get: function(path) { return request('GET', path); },
        post: function(path, data) { return request('POST', path, data); },
        put: function(path, data) { return request('PUT', path, data); },
        delete: function(path) { return request('DELETE', path); },

        // Auth
        platformToken: function() {
            return localStorage.getItem('danzona_platform_token') || '';
        },
        platformUser: function() {
            return localStorage.getItem('danzona_platform_username') || '';
        },
        setPlatformSession: function(token, username) {
            localStorage.setItem('danzona_platform_token', token || '');
            localStorage.setItem('danzona_platform_username', username || '');
        },
        clearPlatformSession: function() {
            localStorage.removeItem('danzona_platform_token');
            localStorage.removeItem('danzona_platform_username');
        },
        platformLogin: function(username, password) {
            return fetch(BASE_URL + '/auth/platform-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, password: password })
            }).then(function(res) {
                return res.json().then(function(body) {
                    if (res.ok && body && body.token) API.setPlatformSession(body.token, body.user && body.user.username);
                    return body;
                });
            });
        },
        registerPharmacy: function(data) {
            var headers = { 'Content-Type': 'application/json' };
            var token = API.platformToken();
            if (token) headers['X-Platform-Token'] = token;
            return fetch(BASE_URL + '/auth/register', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(data)
            }).then(function(res) { return res.json(); });
        },
        login: function(apiKeyVal, uname, pwd) {
            return fetch(BASE_URL + '/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKeyVal, username: uname, password: pwd })
            }).then(function(res) { return res.json(); });
        },
        staffLogin: function(uname, pwd) {
            return fetch(BASE_URL + '/auth/staff-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: uname, password: pwd })
            }).then(function(res) { return res.json(); });
        },
        adminSetupLogin: function(apiKey, adminUser, adminPwd) {
            return fetch(BASE_URL + '/auth/admin-setup-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey, admin_username: adminUser, admin_password: adminPwd })
            }).then(function(res) { return res.json(); });
        },
        // Step 2 of store sign-up: the administrator sets their own login and
        // the store account is activated.
        completeStoreSetup: function(data) {
            return fetch(BASE_URL + '/auth/complete-setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function(res) { return res.json(); });
        },

        // Products
        getProducts: function() { return this.get('/products'); },
        saveProduct: function(data) { return this.post('/products', data); },
        updateProduct: function(id, data) { return this.put('/products/' + id, data); },
        deleteProduct: function(id) { return this.delete('/products/' + id); },

        // Sales
        getSales: function() { return this.get('/sales'); },
        saveSale: function(data) { return this.post('/sales', data); },
        getSale: function(id) { return this.get('/sales/' + id); },

        // Receiving
        getReceiving: function() { return this.get('/receiving'); },
        saveReceiving: function(data) { return this.post('/receiving', data); },

        // Customers
        getCustomers: function() { return this.get('/customers'); },
        saveCustomer: function(data) { return this.post('/customers', data); },
        updateCustomer: function(id, data) { return this.put('/customers/' + id, data); },
        deleteCustomer: function(id) { return this.delete('/customers/' + id); },

        // Employees
        getEmployees: function() { return this.get('/employees'); },
        saveEmployee: function(data) { return this.post('/employees', data); },
        updateEmployee: function(id, data) { return this.put('/employees/' + id, data); },
        deleteEmployee: function(id) { return this.delete('/employees/' + id); },

        // Inventory
        getInventory: function() { return this.get('/inventory'); },
        saveInventory: function(data) { return this.post('/inventory', data); },
        updateInventory: function(id, data) { return this.put('/inventory/' + id, data); },

        // Expenses
        getExpenses: function() { return this.get('/expenses'); },
        saveExpense: function(data) { return this.post('/expenses', data); },
        deleteExpense: function(id) { return this.delete('/expenses/' + id); },

        // Payments
        getPayments: function() { return this.get('/payments'); },
        savePayment: function(data) { return this.post('/payments', data); },
        updatePayment: function(id, data) { return this.put('/payments/' + id, data); },
        deletePayment: function(id) { return this.delete('/payments/' + id); },

        // Locations
        getLocations: function() { return this.get('/locations'); },
        saveLocation: function(data) { return this.post('/locations', data); },
        updateLocation: function(id, data) { return this.put('/locations/' + id, data); },
        deleteLocation: function(id) { return this.delete('/locations/' + id); },

        // Appointments
        getAppointments: function() { return this.get('/appointments'); },
        saveAppointment: function(data) { return this.post('/appointments', data); },
        updateAppointment: function(id, data) { return this.put('/appointments/' + id, data); },
        deleteAppointment: function(id) { return this.delete('/appointments/' + id); },

        // Gift Cards
        getGiftCards: function() { return this.get('/giftcards'); },
        saveGiftCard: function(data) { return this.post('/giftcards', data); },
        updateGiftCard: function(id, data) { return this.put('/giftcards/' + id, data); },
        deleteGiftCard: function(id) { return this.delete('/giftcards/' + id); },

        // Messages
        getMessages: function() { return this.get('/messages'); },
        saveMessage: function(data) { return this.post('/messages', data); },
        deleteMessage: function(id) { return this.delete('/messages/' + id); },

        // Deliveries
        getDeliveries: function() { return this.get('/deliveries'); },
        saveDelivery: function(data) { return this.post('/deliveries', data); },

        // Invoices
        getInvoices: function() { return this.get('/invoices'); },
        saveInvoice: function(data) { return this.post('/invoices', data); },

        // Dashboard
        getDashboard: function() { return this.get('/dashboard'); },

        // Users/Staff
        getUsers: function() { return this.get('/users'); },
        registerStaff: function(data) { return this.post('/users/register', data); },
        updateUser: function(id, data) { return this.put('/users/' + id, data); },
        deleteUser: function(id) { return this.delete('/users/' + id); },

        // Admin Panel
        getAdminOverview: function() { return this.get('/admin/overview'); },
        getAdminUsers: function() { return this.get('/admin/users'); },
        createAdminUser: function(data) { return this.post('/admin/users', data); },
        updateAdminUser: function(id, data) { return this.put('/admin/users/' + id, data); },
        deleteAdminUser: function(id) { return this.delete('/admin/users/' + id); },
        getAdminPages: function() { return this.get('/admin/pages'); },
        updateAdminPage: function(pageKey, data) { return this.put('/admin/pages/' + encodeURIComponent(pageKey), data); },
        resetAdminPages: function() { return this.post('/admin/pages/reset'); },
        getAdminRolePresets: function() { return this.get('/admin/role-presets'); },
        getMyAccess: function() { return this.get('/me/access'); },

        // Business profile (works for any kind of business)
        getBusinessTypes: function() { return this.get('/business-types'); },
        getBusinessProfile: function() { return this.get('/business-profile'); },
        updateBusinessProfile: function(data) { return this.put('/business-profile', data); },

        // Suppliers
        getSuppliers: function() { return this.get('/suppliers'); },
        saveSupplier: function(data) { return this.post('/suppliers', data); },
        updateSupplier: function(id, data) { return this.put('/suppliers/' + id, data); },
        deleteSupplier: function(id) { return this.delete('/suppliers/' + id); },

        // Catalogue
        getCatalogue: function() { return this.get('/catalogue'); },

        // Shifts
        getShifts: function() { return this.get('/shifts'); },
        saveShift: function(data) { return this.post('/shifts', data); },
        updateShift: function(id, data) { return this.put('/shifts/' + id, data); },
        deleteShift: function(id) { return this.delete('/shifts/' + id); },

        // Purchase Orders
        getPurchaseOrders: function() { return this.get('/purchase-orders'); },
        savePurchaseOrder: function(data) { return this.post('/purchase-orders', data); },
        updatePurchaseOrder: function(id, data) { return this.put('/purchase-orders/' + id, data); },
        deletePurchaseOrder: function(id) { return this.delete('/purchase-orders/' + id); },

        // Bank Records
        getBankRecords: function() { return this.get('/bank-records'); },
        saveBankRecord: function(data) { return this.post('/bank-records', data); },
        updateBankRecord: function(id, data) { return this.put('/bank-records/' + id, data); },
        deleteBankRecord: function(id) { return this.delete('/bank-records/' + id); },

        // Stock Transfers
        getStockTransfers: function() { return this.get('/stock-transfers'); },
        saveStockTransfer: function(data) { return this.post('/stock-transfers', data); },
        updateStockTransfer: function(id, data) { return this.put('/stock-transfers/' + id, data); },
        deleteStockTransfer: function(id) { return this.delete('/stock-transfers/' + id); },

        // Stock Counts (stock take)
        getStockCounts: function() { return this.get('/stock-counts'); },
        getStockCount: function(id) { return this.get('/stock-counts/' + id); },
        saveStockCount: function(data) { return this.post('/stock-counts', data); },
        updateStockCount: function(id, data) { return this.put('/stock-counts/' + id, data); },
        applyStockCount: function(id) { return this.post('/stock-counts/' + id + '/apply'); },
        deleteStockCount: function(id) { return this.delete('/stock-counts/' + id); },

        // Tax Rules
        getTaxRules: function() { return this.get('/tax-rules'); },
        saveTaxRule: function(data) { return this.post('/tax-rules', data); },
        updateTaxRule: function(id, data) { return this.put('/tax-rules/' + id, data); },
        deleteTaxRule: function(id) { return this.delete('/tax-rules/' + id); },

        // Expiry Batches
        getExpiryBatches: function() { return this.get('/expiry-batches'); },
        saveExpiryBatch: function(data) { return this.post('/expiry-batches', data); },
        updateExpiryBatch: function(id, data) { return this.put('/expiry-batches/' + id, data); },
        deleteExpiryBatch: function(id) { return this.delete('/expiry-batches/' + id); },

        // Prescriptions
        getPrescriptions: function() { return this.get('/prescriptions'); },
        savePrescription: function(data) { return this.post('/prescriptions', data); },
        updatePrescription: function(id, data) { return this.put('/prescriptions/' + id, data); },
        deletePrescription: function(id) { return this.delete('/prescriptions/' + id); },

        // Audit Log
        getAuditLog: function() { return this.get('/audit-log'); },
        saveAuditLog: function(data) { return this.post('/audit-log', data); },


        // Branches
        getBranches: function() { return this.get('/branches'); },
        saveBranch: function(data) { return this.post('/branches', data); },
        updateBranch: function(id, data) { return this.put('/branches/' + id, data); },
        deleteBranch: function(id) { return this.delete('/branches/' + id); },

        // Platform Admin (tenant and plan management)
        getAdminTenants: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants?platform_token=' + encodeURIComponent(token), {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        updateAdminTenant: function(id, data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '?platform_token=' + encodeURIComponent(token), {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
            }).then(function(res) { return res.json(); });
        },
        deleteAdminTenant: function(id, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '?platform_token=' + encodeURIComponent(token), {
                method: 'DELETE'
            }).then(function(res) { return res.json(); });
        },
        suspendAdminTenant: function(id, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '/suspend?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        reactivateAdminTenant: function(id, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '/reactivate?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        notifySubscription: function(id, data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '/notify-subscription?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        assignPlanToTenant: function(id, data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/' + id + '/plan?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        bulkTenantAction: function(data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/bulk?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        tenantUsageStats: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/stats?platform_token=' + encodeURIComponent(token), {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        listAdminPayments: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/payments?platform_token=' + encodeURIComponent(token), {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        recordAdminPayment: function(data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/payments?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        autoSuspendExpired: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/tenants/auto-suspend?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        // Platform-admin plan management
        platformListPlans: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/platform/admin/plans?platform_token=' + encodeURIComponent(token), {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        platformCreatePlan: function(data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/platform/admin/plans?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        platformUpdatePlan: function(id, data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/platform/admin/plans/' + id + '?platform_token=' + encodeURIComponent(token), {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {})
            }).then(function(res) { return res.json(); });
        },
        getTenantNotes: function(id, token) {
            return fetch('/api/admin/tenants/' + id + '/notes?platform_token=' + encodeURIComponent(token || API.platformToken()), { headers: {'Content-Type': 'application/json'} }).then(r => r.json());
        },
        addTenantNote: function(id, note, token) {
            return fetch('/api/admin/tenants/' + id + '/notes?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({note}) }).then(r => r.json());
        },
        getSubscriptionHistory: function(id, token) {
            return fetch('/api/admin/tenants/' + id + '/subscriptions/history?platform_token=' + encodeURIComponent(token || API.platformToken()), { headers: {'Content-Type': 'application/json'} }).then(r => r.json());
        },
        updateTenantPlan: function(id, planId, token) {
            return fetch('/api/admin/tenants/' + id + '/plan?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({plan_id: planId}) }).then(r => r.json());
        },
        impersonateTenant: function(id, token) {
            return fetch('/api/admin/tenants/' + id + '/impersonate?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'} }).then(r => r.json());
        },
        getActivityLog: function(token) {
            return fetch('/api/admin/activity?platform_token=' + encodeURIComponent(token || API.platformToken()), { headers: {'Content-Type': 'application/json'} }).then(r => r.json());
        },
        generateInvoice: function(id, amount, dueDate, token) {
            return fetch('/api/admin/tenants/' + id + '/invoice?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({amount, due_date: dueDate}) }).then(r => r.json());
        },
        getTenantInvoices: function(id, token) {
            return fetch('/api/admin/tenants/' + id + '/invoices?platform_token=' + encodeURIComponent(token || API.platformToken())).then(r => r.json());
        },
        createTenantInvoice: function(id, data, token) {
            return fetch('/api/admin/tenants/' + id + '/invoices?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(r => r.json());
        },
        markInvoicePaid: function(id, token) {
            return fetch('/api/admin/invoices/' + id + '/mark-paid?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'} }).then(r => r.json());
        },
        getTenantReminders: function(id, token) {
            return fetch('/api/admin/tenants/' + id + '/reminders?platform_token=' + encodeURIComponent(token || API.platformToken())).then(r => r.json());
        },
        sendTenantReminder: function(id, data, token) {
            return fetch('/api/admin/tenants/' + id + '/reminders?platform_token=' + encodeURIComponent(token || API.platformToken()), { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(r => r.json());
        },
        getAdminPlans: function(platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/plans?platform_token=' + encodeURIComponent(token), {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(res) { return res.json(); });
        },
        saveAdminPlan: function(data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/plans?platform_token=' + encodeURIComponent(token), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
            }).then(function(res) { return res.json(); });
        },
        updateAdminPlan: function(id, data, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/plans/' + id + '?platform_token=' + encodeURIComponent(token), {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
            }).then(function(res) { return res.json(); });
        },
        deleteAdminPlan: function(id, platformToken) {
            var token = platformToken || API.platformToken();
            return fetch('/api/admin/plans/' + id + '?platform_token=' + encodeURIComponent(token), {
                method: 'DELETE'
            }).then(function(res) { return res.json(); });
        }
    };
})();
