# GoldVault Ledger

**A secure, offline gold transaction ledger system for Windows**

## Overview

GoldVault Ledger is a production-ready, portable application designed to track gold transactions between a central business (Moozhayil) and individual artisans (Smiths). The application runs entirely from a USB stick on Windows 10/11 without requiring installation, internet access, or administrator rights.

## Key Features

### Security
- **AES-256-GCM Encryption**: Entire database encrypted at rest
- **In-Memory Operation**: Database exists only in RAM while running
- **PBKDF2 Password Hashing**: 600,000 iterations for user passwords
- **USB Auto-Lock**: Automatically locks when USB is removed
- **Session Timeout**: 10-minute inactivity timeout

### User Management
- **Two-tier Authentication**: Master password (vault) + User login
- **Role-Based Access**: Admin and Employee roles with distinct permissions
- **Change Request System**: Employees request changes; Admins approve

### Gold Tracking
- **Automatic 995 Basis Conversion**: All weights converted to 995 purity standard
- **Precision Rounding**: Floor for Smith→Moozhayil, Ceil for Moozhayil→Smith
- **Running Balance**: Real-time balance tracking per Smith
- **Purity Auto-Detection**: Handles both percentage (≤100) and fineness (>100)

### Reporting
- Daily Report
- Smith-wise Ledger
- Balance Report
- Gold Given/Received Reports
- User-wise Entry Report
- Edit/Delete Audit Report
- Change Request Report

### Data Management
- **Comprehensive Audit Log**: Every action tracked with before/after snapshots
- **Backup/Restore**: Encrypted backup with validation
- **Data Clearing**: Multiple options with automatic backup
- **Entry Management**: Add, edit, delete with full audit trail

## Technical Specifications

### Architecture
- **Backend**: Python 3.10+ with SQLite (in-memory)
- **Frontend**: HTML/CSS/JavaScript with Eel framework
- **Packaging**: PyInstaller (single .exe file)
- **Database**: AES-256-GCM encrypted SQLite

### System Requirements
- Windows 10 or Windows 11
- 4 GB RAM minimum
- 100 MB free disk space on USB drive
- No internet connection required
- No administrator rights required

## Installation & Deployment

### Building from Source

1. **Install Python 3.10+** on your development machine

2. **Install Dependencies**:
   ```cmd
   cd GoldVault
   pip install -r requirements.txt
   ```

3. **Run Tests**:
   ```cmd
   python test_calculations.py
   ```

4. **Build Executable**:
   ```cmd
   pyinstaller --noconfirm --onefile --windowed ^
     --add-data "frontend;frontend" ^
     --hidden-import=eel ^
     --hidden-import=cryptography ^
     --hidden-import=sqlite3 ^
     --hidden-import=win32file ^
     --hidden-import=win32api ^
     --hidden-import=pywintypes ^
     --name GoldVault ^
     main.py
   ```

5. **Deploy to USB**:
   - Copy `dist/GoldVault.exe` to USB root
   - Create empty `GoldVaultData` folder next to .exe

### First Run

1. Double-click `GoldVault.exe`
2. Complete first-time setup:
   - Create master password (encrypts database)
   - Create admin account
3. Start using the application

## Usage Guide

### User Roles

#### Admin Permissions
- ✅ Add, edit, delete entries directly
- ✅ Approve/reject change requests
- ✅ Create/edit/delete users
- ✅ Manage Smiths
- ✅ Clear data (with password confirmation)
- ✅ Backup/restore database
- ✅ View audit log

#### Employee Permissions
- ✅ Add new entries
- ✅ View all entries
- ✅ Submit change requests
- ✅ Add new Smiths
- ✅ View reports
- ✅ Change own password

### Adding an Entry

1. Click **"Add Entry"** button
2. Fill in the form:
   - **Date**: Defaults to today (editable)
   - **Time**: Defaults to current time (editable)
   - **Smith**: Select from dropdown or add new
   - **Entry Type**: Smith to Moozhayil OR Moozhayil to Smith
   - **Weight**: In grams (up to 3 decimal places)
   - **Purity**: As percentage (e.g., 99.5) or fineness (e.g., 995)
   - **Remarks**: Optional notes
3. Click **"Add Entry"**

### Calculation Rules

#### Purity Detection
- **Value ≤ 100**: Treated as percentage (e.g., 99.5 = 99.5%)
- **Value > 100**: Treated as fineness per 1000 (e.g., 995 = 995/1000)

#### Conversion Formula
```
factor = purity / 100  (if purity ≤ 100)
       = purity / 1000 (if purity > 100)

converted_weight = raw_weight × factor / 0.995
```

#### Rounding Rules
- **Smith to Moozhayil**: Floor to 3 decimals
- **Moozhayil to Smith**: Ceil to 3 decimals

#### Balance Calculation
```
balance = SUM(Moozhayil to Smith) - SUM(Smith to Moozhayil)
```

### Change Request Workflow

1. **Employee** clicks "Request Change" on an entry
2. Edits fields and provides reason
3. **Admin** reviews in Change Requests tab
4. **Admin** approves (with optional remarks) or rejects (with required reason)
5. On approval, entry is updated and balance recalculated

### Data Clearing

All clearing operations:
- Require admin password re-authentication
- Show preview of entries to be deleted
- Create automatic backup before execution
- Log action to audit trail

Options:
- Clear all entries
- Clear entries for specific Smith
- Clear entries before date
- Clear entries older than 2 weeks/1 month

### Backup & Restore

**Backup**:
- Manual: Admin Panel → Backup/Restore → Create Backup
- Automatic: Before all data clearing operations
- Location: `GoldVaultData/backups/backup_YYYYMMDD_HHMMSS.db.enc`

**Restore**:
- Select backup file
- Enter master password
- System validates backup integrity
- Current vault replaced
- User must re-login

## Security Best Practices

1. **Master Password**:
   - Use a strong, unique password
   - Store securely (cannot be recovered if lost)
   - Never share with anyone

2. **Backups**:
   - Create regular backups
   - Store in multiple secure locations
   - Test restoration periodically

3. **USB Drive**:
   - Use a reliable, high-quality USB drive
   - Keep in secure location when not in use
   - Consider encryption at USB level for extra security

4. **Physical Security**:
   - Lock computer when stepping away
   - Store USB in secure location
   - Limit physical access to authorized personnel

## File Structure

```
USB Drive Root/
├── GoldVault.exe           # Main application
└── GoldVaultData/          # Data folder (created on first run)
    ├── ledger.enc          # Encrypted database
    ├── goldvault.log       # Application log
    └── backups/            # Backup files
        └── backup_*.db.enc
```

## Troubleshooting

### Application Won't Start
- Check `GoldVaultData/goldvault.log` for errors
- Ensure USB drive is not write-protected
- Try running on a different computer

### "Vault Locked" Message
- USB drive was removed or became inaccessible
- Re-insert USB drive
- Enter master password to unlock

### Forgot Master Password
- **Cannot be recovered** - encryption is unbreakable
- Restore from backup if available
- Otherwise, data is permanently inaccessible

### Entry Balance Incorrect
- Admin can trigger manual recalculation
- Check audit log for unauthorized changes
- Verify all entries are in chronological order

### USB Auto-Lock Not Working
- Ensure pywin32 is properly installed (development)
- Check Windows permissions
- Verify USB drive letter hasn't changed

## Development

### Project Structure
```
GoldVault/
├── main.py                 # Application entry point
├── backend/
│   ├── __init__.py
│   ├── calculations.py     # Weight conversion & rounding
│   ├── database.py         # Encrypted vault management
│   ├── auth.py             # User authentication
│   ├── entries.py          # Entry CRUD operations
│   ├── change_requests.py  # Change request system
│   ├── audit.py            # Audit logging
│   └── reports.py          # Report generation
├── frontend/
│   ├── index.html          # Main UI
│   ├── style.css           # Styling
│   └── script.js           # Frontend logic
├── requirements.txt        # Python dependencies
├── build_instructions.txt  # Build guide
└── test_calculations.py    # Unit tests
```

### Running Tests
```cmd
python test_calculations.py
python backend/calculations.py
```

### Development Mode
```cmd
python main.py
```

## License

Proprietary - All rights reserved

## Support

For issues or questions:
1. Check `GoldVaultData/goldvault.log`
2. Review this README
3. Contact system administrator

---

**Version**: 1.0.0  
**Last Updated**: 2026-05-03  
**Author**: GoldVault Development Team
