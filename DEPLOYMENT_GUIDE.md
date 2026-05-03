# GoldVault Ledger - Deployment Guide

## Quick Start

### For End Users (Windows)

1. **Receive the USB Drive** with GoldVault.exe already installed
2. **Insert USB** into any Windows 10/11 computer
3. **Double-click** `GoldVault.exe`
4. **First-time setup** (only once):
   - Create master password (WRITE THIS DOWN SECURELY!)
   - Create admin username and password
5. **Start using** the application

### For IT/Deployment Team

## Pre-Deployment Checklist

- [ ] Python 3.10+ installed on build machine
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Tests passed (`python test_calculations.py`)
- [ ] USB drive formatted (FAT32 or NTFS)
- [ ] USB drive has at least 100 MB free space

## Build Process

### Step 1: Prepare Build Environment

```cmd
# Clone or extract the GoldVault source code
cd GoldVault

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | findstr "eel cryptography pywin32 pyinstaller"
```

### Step 2: Run Tests

```cmd
# Run calculation tests
python test_calculations.py

# Expected output: "✓ ALL TESTS PASSED"
```

### Step 3: Build Executable

**For Windows Command Prompt:**
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

**For PowerShell:**
```powershell
pyinstaller --noconfirm --onefile --windowed `
  --add-data "frontend;frontend" `
  --hidden-import=eel `
  --hidden-import=cryptography `
  --hidden-import=sqlite3 `
  --hidden-import=win32file `
  --hidden-import=win32api `
  --hidden-import=pywintypes `
  --name GoldVault `
  main.py
```

Build time: 2-5 minutes depending on system

### Step 4: Verify Build

```cmd
# Check that the executable was created
dir dist\GoldVault.exe

# Check file size (should be 15-25 MB)
```

### Step 5: Prepare USB Drive

```cmd
# Copy executable to USB root
copy dist\GoldVault.exe E:\

# Create data folder
mkdir E:\GoldVaultData

# Verify structure
dir E:\
```

Expected structure:
```
E:\
├── GoldVault.exe
└── GoldVaultData\
```

### Step 6: Test on Clean Machine

1. Insert USB into a test Windows machine (without Python installed)
2. Double-click GoldVault.exe
3. Complete first-time setup
4. Add a test Smith
5. Add a test entry
6. Generate a test report
7. Create a backup
8. Lock and unlock the vault

## Mass Deployment

### For Multiple USB Drives

1. **Build once** on your development machine
2. **Copy to master USB**:
   ```cmd
   copy dist\GoldVault.exe F:\
   mkdir F:\GoldVaultData
   ```
3. **Clone to other USBs**:
   - Use USB duplicator hardware, OR
   - Copy files manually to each USB

### Important Notes

- Each USB will have its own independent vault
- Master password is set during first run on each USB
- No data is shared between USB drives
- Each deployment is completely isolated

## Security Hardening

### Recommended USB Drive Settings

1. **Use high-quality USB drives**:
   - Industrial-grade preferred
   - SLC or MLC flash (not TLC)
   - Minimum 8 GB capacity

2. **Enable write-protection** (optional):
   - Some USB drives have physical write-protect switches
   - Prevents accidental deletion
   - Disable when adding entries

3. **USB-level encryption** (optional additional layer):
   - BitLocker To Go (Windows Pro/Enterprise)
   - VeraCrypt
   - Hardware-encrypted USB drives

### Application Security

The application already includes:
- ✅ AES-256-GCM database encryption
- ✅ PBKDF2 password hashing (600k iterations)
- ✅ In-memory database (no disk writes except encrypted)
- ✅ Session timeout (10 minutes)
- ✅ USB auto-lock
- ✅ Comprehensive audit logging

## Troubleshooting Deployment

### Build Errors

**Error: "Module not found: eel"**
```cmd
pip install --upgrade eel
```

**Error: "Module not found: cryptography"**
```cmd
pip install --upgrade cryptography
```

**Error: "Module not found: win32file"**
```cmd
pip install --upgrade pywin32
python Scripts/pywin32_postinstall.py -install
```

**Error: "Unable to find frontend folder"**
- Ensure you're running pyinstaller from the GoldVault directory
- Verify frontend/ folder exists with index.html, style.css, script.js

### Runtime Errors

**Error: "Application failed to start"**
- Check if antivirus is blocking the .exe
- Try running as administrator (one time)
- Check Windows Event Viewer for details

**Error: "Vault file not found"**
- Ensure GoldVaultData folder exists next to .exe
- Check USB drive is not write-protected
- Verify USB drive has free space

**Error: "Frontend folder not found"**
- Rebuild with correct --add-data parameter
- Ensure frontend files are included in build

## User Training

### Initial Setup Training (15 minutes)

1. **Master Password Importance**:
   - Cannot be recovered if lost
   - Encrypts entire database
   - Must be strong and memorable
   - Write down and store securely

2. **User Roles**:
   - Admin: Full control
   - Employee: Add entries, request changes

3. **Basic Operations**:
   - Adding a Smith
   - Adding an entry
   - Understanding purity (percentage vs fineness)
   - Viewing ledger
   - Generating reports

### Advanced Training (30 minutes)

1. **Change Request Workflow**
2. **Backup and Restore**
3. **Data Clearing**
4. **Audit Log Review**
5. **User Management**

## Maintenance

### Regular Tasks

**Daily**:
- None required (application is maintenance-free)

**Weekly**:
- Create backup (Admin Panel → Backup/Restore)
- Review audit log for anomalies

**Monthly**:
- Test backup restoration
- Review user access (deactivate former employees)
- Check USB drive health

### Backup Strategy

**3-2-1 Rule**:
- **3** copies of data (original + 2 backups)
- **2** different media types (USB + external HDD)
- **1** off-site backup (secure location)

**Backup Locations**:
1. Automatic: `GoldVaultData/backups/` on USB
2. Manual: Copy to external hard drive weekly
3. Off-site: Copy to secure cloud storage monthly (encrypted)

### USB Drive Lifespan

- **Expected lifespan**: 5-10 years (depends on quality and usage)
- **Warning signs**:
  - Slow read/write speeds
  - File corruption
  - Windows errors when accessing
- **Replacement procedure**:
  1. Create backup from old USB
  2. Copy GoldVault.exe to new USB
  3. Create GoldVaultData folder
  4. Copy backup file to new USB
  5. Restore from backup

## Compliance & Audit

### Audit Trail

Every action is logged with:
- User who performed action
- Timestamp
- Original data (before change)
- New data (after change)
- Reason/remarks

### Data Retention

- Entries: Retained indefinitely (unless manually cleared)
- Audit log: Retained indefinitely
- Backups: Retain per company policy (recommend 7 years)

### Access Control

- Master password: Known only to authorized personnel
- Admin accounts: Limit to 2-3 trusted individuals
- Employee accounts: One per employee
- Deactivate accounts immediately upon termination

## Disaster Recovery

### Scenario 1: Lost Master Password

**Status**: ❌ Unrecoverable  
**Prevention**: 
- Write down master password
- Store in company safe
- Consider password manager for backup

### Scenario 2: Corrupted Database

**Status**: ✅ Recoverable (if backup exists)  
**Recovery**:
1. Insert USB
2. Run GoldVault.exe
3. Admin Panel → Backup/Restore
4. Select most recent backup
5. Enter master password
6. Restore

### Scenario 3: Lost/Stolen USB

**Status**: ⚠️ Data secure (encrypted), but inaccessible  
**Recovery**:
1. Obtain backup from secure location
2. Prepare new USB with GoldVault.exe
3. Restore from backup
4. Change all user passwords
5. Review audit log for suspicious activity

### Scenario 4: USB Drive Failure

**Status**: ✅ Recoverable (if backup exists)  
**Recovery**:
1. Prepare new USB with GoldVault.exe
2. Copy backup file to new USB
3. Restore from backup

## Support & Contact

### Self-Help Resources

1. **README.md**: Complete user guide
2. **build_instructions.txt**: Build process
3. **Log file**: `GoldVaultData/goldvault.log`
4. **Test suite**: `test_calculations.py`

### Getting Help

1. Check log file for error messages
2. Review README troubleshooting section
3. Contact system administrator
4. Contact development team (if available)

## Version History

### Version 1.0.0 (2026-05-03)
- Initial release
- Complete feature set as per specification
- All tests passing
- Production-ready

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-03  
**Next Review**: 2026-08-03
