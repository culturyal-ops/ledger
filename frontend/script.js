/**
 * GoldVault Ledger - Frontend Application Logic
 * Handles all UI interactions and Eel communication
 */

// Toast Notification System
const Toast = {
  container: null,
  
  init() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },
  
  show(message, type = 'default', duration = 4000) {
    this.init();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
      success: '✓',
      error: '✗',
      warning: '⚠',
      info: 'ℹ',
      default: '🏆'
    };
    
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.default}</span>
      <span class="toast-message">${message}</span>
      <button class="toast-close" onclick="Toast.hide(this.parentElement)">×</button>
    `;
    
    this.container.appendChild(toast);
    
    // Auto-hide after duration
    setTimeout(() => this.hide(toast), duration);
  },
  
  hide(toast) {
    toast.classList.add('toast-hiding');
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, 300);
  },
  
  success(message) {
    this.show(message, 'success');
  },
  
  error(message) {
    this.show(message, 'error', 6000);
  },
  
  warning(message) {
    this.show(message, 'warning', 5000);
  },
  
  info(message) {
    this.show(message, 'info');
  }
};

const app = {
  currentUser: null,
  currentScreen: 'boot-screen',
  ledgerPage: 0,
  ledgerLimit: 50,
  ledgerFilters: {},
  smithsCache: [],

  // Initialize application
  async init() {
    console.log('GoldVault initializing...');
    
    // Set up keep-alive (reset session timer on any interaction)
    document.addEventListener('click', () => eel.keep_alive());
    document.addEventListener('keypress', () => eel.keep_alive());
    
    // Set up form handlers
    this.setupFormHandlers();
    
    // Check if vault exists
    setTimeout(async () => {
      try {
        const exists = await eel.check_vault_exists()();
        if (exists) {
          this.showScreen('unlock-screen');
        } else {
          this.showScreen('setup-screen');
        }
      } catch (err) {
        console.error('Init error:', err);
        Toast.error('Failed to initialize application: ' + err);
      }
    }, 500);
  },

  // Screen management
  showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const screen = document.getElementById(screenId);
    if (screen) {
      screen.classList.add('active');
      this.currentScreen = screenId;
      
      // Update user info in top bars
      if (this.currentUser) {
        const userInfoElements = document.querySelectorAll('.user-info');
        userInfoElements.forEach(el => {
          if (el.id) {
            el.textContent = `${this.currentUser.username} (${this.currentUser.role})`;
          }
        });
      }
      
      // Load screen-specific data
      if (screenId === 'dashboard-screen') {
        this.loadDashboard();
      } else if (screenId === 'ledger-screen') {
        this.loadLedger();
      } else if (screenId === 'requests-screen') {
        this.showRequestsTab('pending');
      } else if (screenId === 'admin-screen') {
        this.showAdminTab('users');
      }
    }
  },

  // Setup form handlers
  setupFormHandlers() {
    // Setup form
    document.getElementById('setup-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const masterPw = document.getElementById('setup-master-pw').value;
      const masterPwConfirm = document.getElementById('setup-master-pw-confirm').value;
      const adminUser = document.getElementById('setup-admin-user').value;
      const adminPw = document.getElementById('setup-admin-pw').value;
      const adminPwConfirm = document.getElementById('setup-admin-pw-confirm').value;

      if (masterPw !== masterPwConfirm) {
        this.showError('setup-error', 'Master passwords do not match.');
        return;
      }
      if (adminPw !== adminPwConfirm) {
        this.showError('setup-error', 'Admin passwords do not match.');
        return;
      }

      const result = await eel.create_vault(masterPw, adminUser, adminPw)();
      if (result.ok) {
        this.showScreen('unlock-screen');
      } else {
        this.showError('setup-error', result.error);
      }
    });

    // Unlock form
    document.getElementById('unlock-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const masterPw = document.getElementById('unlock-master-pw').value;
      const result = await eel.unlock_vault(masterPw)();
      if (result.ok) {
        this.showScreen('login-screen');
        document.getElementById('unlock-master-pw').value = '';
      } else {
        this.showError('unlock-error', result.error);
      }
    });

    // Login form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('login-username').value;
      const password = document.getElementById('login-password').value;
      const result = await eel.login_user(username, password)();
      if (result.ok) {
        this.currentUser = result.data;
        document.getElementById('current-username').textContent = this.currentUser.username;
        document.getElementById('current-role').textContent = this.currentUser.role;
        
        // Show/hide admin button
        if (this.currentUser.role === 'admin') {
          document.getElementById('btn-admin').style.display = 'inline-block';
        }
        
        this.showScreen('dashboard-screen');
        document.getElementById('login-password').value = '';
      } else {
        this.showError('login-error', result.error);
      }
    });

    // Report form
    document.getElementById('report-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const reportType = document.getElementById('report-type').value;
      const filters = this.getReportFilters();
      const result = await eel.generate_report(reportType, filters)();
      if (result.ok) {
        const win = window.open('', '_blank');
        win.document.write(result.data);
        win.document.close();
      } else {
        alert('Error generating report: ' + result.error);
      }
    });
  },

  // Error display helper
  showError(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 5000);
  },

  // Logout
  async logout() {
    await eel.lock_vault()();
    this.currentUser = null;
    this.showScreen('unlock-screen');
  },

  // Dashboard
  async loadDashboard() {
    const result = await eel.get_dashboard_stats()();
    if (result.ok) {
      const stats = result.data;
      document.getElementById('stat-smiths').textContent = stats.total_smiths;
      document.getElementById('stat-entries').textContent = stats.total_entries;
      document.getElementById('stat-pending').textContent = stats.pending_requests;
      
      // Load recent entries
      const tbody = document.getElementById('recent-entries-tbody');
      if (stats.recent_entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No entries yet</td></tr>';
      } else {
        tbody.innerHTML = stats.recent_entries.map(e => `
          <tr>
            <td>${e.entry_number}</td>
            <td>${e.entry_date}</td>
            <td>${e.entry_time}</td>
            <td>${e.smith_name}</td>
            <td><span class="badge ${e.direction === 'Moozhayil to Smith' ? 'badge-mts' : 'badge-stm'}">${e.direction}</span></td>
            <td>${e.converted_weight_fmt}</td>
            <td>${e.balance_after_fmt}</td>
          </tr>
        `).join('');
      }
    }
  },

  // Ledger
  async loadLedger() {
    await this.loadSmiths();
    this.ledgerPage = 0;
    this.applyLedgerFilters();
  },

  async applyLedgerFilters() {
    this.ledgerPage = 0;
    this.ledgerFilters = {
      smith_id: document.getElementById('filter-smith').value || null,
      date_from: document.getElementById('filter-date-from').value || null,
      date_to: document.getElementById('filter-date-to').value || null
    };
    await this.loadLedgerPage();
  },

  async loadLedgerPage(direction) {
    if (direction === 'prev' && this.ledgerPage > 0) {
      this.ledgerPage--;
    } else if (direction === 'next') {
      this.ledgerPage++;
    }

    const offset = this.ledgerPage * this.ledgerLimit;
    const result = await eel.get_ledger_entries(this.ledgerFilters, offset, this.ledgerLimit)();
    
    if (result.ok) {
      const { entries, total } = result.data;
      const tbody = document.getElementById('ledger-tbody');
      
      if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center">No entries found</td></tr>';
      } else {
        tbody.innerHTML = entries.map(e => `
          <tr>
            <td>${e.entry_number}</td>
            <td>${e.entry_date}</td>
            <td>${e.entry_time}</td>
            <td>${e.smith_name}</td>
            <td><span class="badge ${e.direction === 'Moozhayil to Smith' ? 'badge-mts' : 'badge-stm'}">${e.direction}</span></td>
            <td>${e.raw_weight_fmt}</td>
            <td>${e.purity}</td>
            <td>${e.converted_weight_fmt}</td>
            <td>${e.balance_after_fmt}</td>
            <td>${e.entered_by}</td>
            <td>${e.remarks || ''}</td>
            <td class="table-actions">
              ${this.currentUser.role === 'admin' ? 
                `<button class="btn btn-sm btn-secondary" onclick="app.editEntry(${e.id})">Edit</button>
                 <button class="btn btn-sm btn-danger" onclick="app.deleteEntry(${e.id})">Delete</button>` :
                `<button class="btn btn-sm btn-secondary" onclick="app.requestChange(${e.id})">Request Change</button>`
              }
            </td>
          </tr>
        `).join('');
      }
      
      // Update pagination
      const pageInfo = `Page ${this.ledgerPage + 1} (${offset + 1}-${Math.min(offset + this.ledgerLimit, total)} of ${total})`;
      document.getElementById('ledger-page-info').textContent = pageInfo;
      document.getElementById('ledger-prev').disabled = this.ledgerPage === 0;
      document.getElementById('ledger-next').disabled = offset + entries.length >= total;
    }
  },

  // Smiths
  async loadSmiths() {
    const result = await eel.get_smiths()();
    if (result.ok) {
      this.smithsCache = result.data;
      this.updateSmithDropdowns();
    }
  },

  updateSmithDropdowns() {
    const selects = [
      document.getElementById('entry-smith'),
      document.getElementById('filter-smith')
    ];
    
    selects.forEach(select => {
      if (!select) return;
      const currentValue = select.value;
      const isFilter = select.id === 'filter-smith';
      
      select.innerHTML = isFilter ? '<option value="">All Smiths</option>' : '';
      this.smithsCache.forEach(smith => {
        const option = document.createElement('option');
        option.value = smith.id;
        option.textContent = smith.name;
        select.appendChild(option);
      });
      
      if (currentValue) select.value = currentValue;
    });
  },

  // Add Entry Modal
  showAddEntryModal() {
    this.loadSmiths();
    const now = new Date();
    document.getElementById('entry-date').value = now.toISOString().split('T')[0];
    document.getElementById('entry-time').value = now.toTimeString().slice(0, 5);
    document.getElementById('add-entry-form').reset();
    document.getElementById('entry-date').value = now.toISOString().split('T')[0];
    document.getElementById('entry-time').value = now.toTimeString().slice(0, 5);
    this.openModal('add-entry-modal');
  },

  async submitAddEntry() {
    const direction = document.querySelector('input[name="entry-direction"]:checked');
    if (!direction) {
      this.showError('add-entry-error', 'Please select entry type.');
      return;
    }

    const entryData = {
      entry_date: document.getElementById('entry-date').value,
      entry_time: document.getElementById('entry-time').value,
      smith_id: document.getElementById('entry-smith').value,
      direction: direction.value,
      raw_weight: document.getElementById('entry-weight').value,
      purity: document.getElementById('entry-purity').value,
      remarks: document.getElementById('entry-remarks').value
    };

    const result = await eel.add_entry(entryData)();
    if (result.ok) {
      this.closeModal('add-entry-modal');
      if (this.currentScreen === 'ledger-screen') {
        this.loadLedgerPage();
      } else {
        this.loadDashboard();
      }
      Toast.success('Entry added successfully!');
    } else {
      this.showError('add-entry-error', result.error);
    }
  },

  // Add Smith Modal
  showAddSmithModal() {
    document.getElementById('new-smith-name').value = '';
    this.openModal('add-smith-modal');
  },

  async submitAddSmith() {
    const name = document.getElementById('new-smith-name').value.trim();
    if (!name) {
      this.showError('add-smith-error', 'Smith name is required.');
      return;
    }

    const result = await eel.add_smith(name)();
    if (result.ok) {
      this.closeModal('add-smith-modal');
      await this.loadSmiths();
      Toast.success('Smith added successfully!');
    } else {
      this.showError('add-smith-error', result.error);
    }
  },

  // Entry actions
  async editEntry(entryId) {
    const reason = prompt('Enter reason for editing this entry:');
    if (!reason) return;
    
    // For simplicity, we'll just show a basic prompt-based edit
    // In production, you'd want a proper modal with all fields
    Toast.info('Edit functionality: Please use the change request system or implement a full edit modal.');
  },

  async deleteEntry(entryId) {
    const reason = prompt('Enter reason for deleting this entry:');
    if (!reason) return;
    
    if (!confirm('Are you sure you want to delete this entry? This action cannot be undone.')) {
      return;
    }

    const result = await eel.delete_entry(entryId, reason)();
    if (result.ok) {
      Toast.success('Entry deleted successfully.');
      this.loadLedgerPage();
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  async requestChange(entryId) {
    Toast.info('Change request functionality: Implement a modal to request changes to this entry.');
    // TODO: Implement change request modal
  },

  // Change Requests
  async showRequestsTab(status) {
    document.querySelectorAll('#requests-screen .tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    const result = await eel.get_change_requests(status)();
    if (result.ok) {
      const requests = result.data;
      const container = document.getElementById('requests-content');
      
      if (requests.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📝</div><p>No ' + status + ' requests</p></div>';
      } else {
        container.innerHTML = '<div class="table-container"><div class="table-wrapper"><table><thead><tr>' +
          '<th>ID</th><th>Entry #</th><th>Smith</th><th>Requested By</th><th>Date</th><th>Status</th><th>Actions</th>' +
          '</tr></thead><tbody>' +
          requests.map(r => `
            <tr>
              <td>${r.id}</td>
              <td>${r.entry_number}</td>
              <td>${r.smith_name}</td>
              <td>${r.requested_by_name}</td>
              <td>${r.requested_at}</td>
              <td><span class="badge badge-${r.status}">${r.status.toUpperCase()}</span></td>
              <td>
                ${r.status === 'pending' && this.currentUser.role === 'admin' ?
                  `<button class="btn btn-sm btn-success" onclick="app.approveRequest(${r.id})">Approve</button>
                   <button class="btn btn-sm btn-danger" onclick="app.rejectRequest(${r.id})">Reject</button>` :
                  '<span>-</span>'
                }
              </td>
            </tr>
          `).join('') +
          '</tbody></table></div></div>';
      }
    }
  },

  async approveRequest(reqId) {
    const remarks = prompt('Enter admin remarks (optional):');
    if (remarks === null) return;
    
    const result = await eel.approve_request(reqId, remarks)();
    if (result.ok) {
      Toast.success('Request approved successfully.');
      this.showRequestsTab('pending');
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  async rejectRequest(reqId) {
    const remarks = prompt('Enter reason for rejection (required):');
    if (!remarks || !remarks.trim()) {
      Toast.warning('A reason is required to reject a request.');
      return;
    }
    
    const result = await eel.reject_request(reqId, remarks)();
    if (result.ok) {
      Toast.success('Request rejected.');
      this.showRequestsTab('pending');
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  // Reports
  updateReportFilters() {
    const reportType = document.getElementById('report-type').value;
    const container = document.getElementById('report-filters');
    
    let html = '';
    
    // Most reports need date range
    if (['daily', 'smith_ledger', 'gold_given', 'gold_received', 'user_entry', 'audit', 'change_request'].includes(reportType)) {
      html += `
        <div class="form-group">
          <label>Date From</label>
          <input type="date" id="report-date-from">
        </div>
        <div class="form-group">
          <label>Date To</label>
          <input type="date" id="report-date-to">
        </div>
      `;
    }
    
    // Smith filter
    if (['smith_ledger', 'gold_given', 'gold_received'].includes(reportType)) {
      html += `
        <div class="form-group">
          <label>Smith (optional)</label>
          <select id="report-smith">
            <option value="">All Smiths</option>
            ${this.smithsCache.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
          </select>
        </div>
      `;
    }
    
    container.innerHTML = html;
  },

  getReportFilters() {
    const filters = {};
    const dateFrom = document.getElementById('report-date-from');
    const dateTo = document.getElementById('report-date-to');
    const smith = document.getElementById('report-smith');
    
    if (dateFrom) filters.date_from = dateFrom.value;
    if (dateTo) filters.date_to = dateTo.value;
    if (smith) filters.smith_id = smith.value ? parseInt(smith.value) : null;
    
    return filters;
  },

  // Admin Panel
  async showAdminTab(tab) {
    document.querySelectorAll('#admin-screen .tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    
    const container = document.getElementById('admin-content');
    
    if (tab === 'users') {
      await this.loadUsersTab(container);
    } else if (tab === 'smiths') {
      await this.loadSmithsTab(container);
    } else if (tab === 'clear') {
      this.loadClearTab(container);
    } else if (tab === 'backup') {
      this.loadBackupTab(container);
    } else if (tab === 'audit') {
      await this.loadAuditTab(container);
    }
  },

  async loadUsersTab(container) {
    const result = await eel.get_users_list()();
    if (result.ok) {
      const users = result.data;
      container.innerHTML = `
        <div class="table-container">
          <div class="table-header">
            <h2>Users</h2>
            <button class="btn btn-primary btn-sm" onclick="app.showAddUserModal()">Add User</button>
          </div>
          <div class="table-wrapper">
            <table>
              <thead>
                <tr><th>ID</th><th>Username</th><th>Role</th><th>Active</th><th>Created By</th><th>Created At</th><th>Actions</th></tr>
              </thead>
              <tbody>
                ${users.map(u => `
                  <tr>
                    <td>${u.id}</td>
                    <td>${u.username}</td>
                    <td><span class="badge badge-${u.role}">${u.role}</span></td>
                    <td>${u.active ? '✓' : '✗'}</td>
                    <td>${u.created_by_name || '-'}</td>
                    <td>${u.created_at}</td>
                    <td class="table-actions">
                      <button class="btn btn-sm btn-secondary" onclick="alert('Edit user: TODO')">Edit</button>
                      <button class="btn btn-sm ${u.active ? 'btn-danger' : 'btn-success'}" 
                              onclick="app.toggleUser(${u.id}, ${!u.active})">
                        ${u.active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }
  },

  async loadSmithsTab(container) {
    await this.loadSmiths();
    container.innerHTML = `
      <div class="table-container">
        <div class="table-header">
          <h2>Smiths</h2>
          <button class="btn btn-primary btn-sm" onclick="app.showAddSmithModal()">Add Smith</button>
        </div>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Balance (995 basis, g)</th><th>Created At</th><th>Actions</th></tr>
            </thead>
            <tbody>
              ${this.smithsCache.map(s => `
                <tr>
                  <td>${s.id}</td>
                  <td>${s.name}</td>
                  <td>${s.balance_fmt}</td>
                  <td>${s.created_at}</td>
                  <td class="table-actions">
                    <button class="btn btn-sm btn-secondary" onclick="alert('Edit smith: TODO')">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="app.deleteSmithAdmin(${s.id})">Delete</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  loadClearTab(container) {
    container.innerHTML = `
      <div class="card">
        <h3>⚠️ Data Clearing</h3>
        <p style="color: var(--red); margin-bottom: 20px;">
          <strong>Warning:</strong> These actions are irreversible. A backup will be created automatically.
        </p>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <button class="btn btn-danger" onclick="app.clearData('all')">Clear All Entries</button>
          <button class="btn btn-danger" onclick="app.clearData('smith')">Clear Entries for Selected Smith</button>
          <button class="btn btn-danger" onclick="app.clearData('before_date')">Clear Entries Before Date</button>
          <button class="btn btn-danger" onclick="app.clearData('older_than_2weeks')">Clear Entries Older Than 2 Weeks</button>
          <button class="btn btn-danger" onclick="app.clearData('older_than_1month')">Clear Entries Older Than 1 Month</button>
        </div>
      </div>
    `;
  },

  loadBackupTab(container) {
    container.innerHTML = `
      <div class="card">
        <h3>💾 Backup & Restore</h3>
        <div style="display: flex; flex-direction: column; gap: 16px; margin-top: 20px;">
          <div>
            <button class="btn btn-primary" onclick="app.backupDatabase()">Create Backup</button>
            <p style="margin-top: 8px; color: var(--text-medium); font-size: 0.9em;">
              Backup will be saved to GoldVaultData/backups/ folder
            </p>
          </div>
          <div>
            <button class="btn btn-secondary" onclick="alert('Restore: Select backup file (TODO: file picker)')">Restore from Backup</button>
            <p style="margin-top: 8px; color: var(--text-medium); font-size: 0.9em;">
              You will need to enter the master password to restore
            </p>
          </div>
        </div>
      </div>
    `;
  },

  async loadAuditTab(container) {
    const result = await eel.get_audit_log_entries({}, 100, 0)();
    if (result.ok) {
      const logs = result.data;
      container.innerHTML = `
        <div class="table-container">
          <div class="table-header">
            <h2>Audit Log</h2>
          </div>
          <div class="table-wrapper">
            <table>
              <thead>
                <tr><th>ID</th><th>Action</th><th>Timestamp</th><th>Changed By</th><th>Approved By</th><th>Remarks</th></tr>
              </thead>
              <tbody>
                ${logs.map(l => `
                  <tr>
                    <td>${l.id}</td>
                    <td><strong>${l.action}</strong></td>
                    <td>${l.timestamp}</td>
                    <td>${l.changed_by_name || '?'}</td>
                    <td>${l.approved_by_name || '-'}</td>
                    <td>${l.remarks || ''}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }
  },

  async toggleUser(userId, active) {
    const result = await eel.toggle_user(userId, active)();
    if (result.ok) {
      Toast.success(`User ${active ? 'activated' : 'deactivated'} successfully.`);
      this.showAdminTab('users');
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  async deleteSmithAdmin(smithId) {
    if (!confirm('Are you sure you want to delete this Smith? This will fail if they have any entries.')) {
      return;
    }
    const result = await eel.delete_smith(smithId)();
    if (result.ok) {
      Toast.success('Smith deleted successfully.');
      this.showAdminTab('smiths');
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  async clearData(clearType) {
    let target = null;
    if (clearType === 'smith') {
      const smithId = prompt('Enter Smith ID to clear:');
      if (!smithId) return;
      target = parseInt(smithId);
    } else if (clearType === 'before_date') {
      const date = prompt('Enter date (YYYY-MM-DD):');
      if (!date) return;
      target = date;
    }

    const reason = prompt('Enter reason for clearing data (required):');
    if (!reason || !reason.trim()) {
      alert('A reason is required.');
      return;
    }

    const password = prompt('Enter your admin password to confirm:');
    if (!password) return;

    if (!confirm('This will permanently delete entries. A backup will be created. Continue?')) {
      return;
    }

    const result = await eel.clear_data(clearType, target, password, reason)();
    if (result.ok) {
      Toast.success(`Cleared ${result.data.deleted} entries. Backup saved to: ${result.data.backup}`);
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  async backupDatabase() {
    const result = await eel.backup_database()();
    if (result.ok) {
      Toast.success('Backup created successfully at: ' + result.data.path);
    } else {
      Toast.error('Error: ' + result.error);
    }
  },

  // Modal helpers
  openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
  },

  closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
  }
};

// Exposed functions for Python to call
eel.expose(lock_vault_from_python);
function lock_vault_from_python() {
  app.currentUser = null;
  app.showScreen('unlock-screen');
  Toast.warning('Vault locked: USB drive removed or session timed out.');
}

eel.expose(session_timeout_from_python);
function session_timeout_from_python() {
  app.currentUser = null;
  app.showScreen('login-screen');
  Toast.warning('Session timed out. Please log in again.');
}

// Initialize on load
window.addEventListener('DOMContentLoaded', () => {
  app.init();
});
