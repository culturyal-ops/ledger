# GoldVault Ledger - Quick Start Guide

## 🚀 For First-Time Users

### Step 1: Launch the Application
1. Insert your USB drive into any Windows 10/11 computer
2. Open the USB drive (usually appears as E:\ or F:\)
3. Double-click **GoldVault.exe**

### Step 2: First-Time Setup (Only Once)
1. **Create Master Password**
   - This encrypts your entire database
   - ⚠️ **CRITICAL**: Write this down and store securely!
   - Cannot be recovered if lost
   - Minimum 4 characters (recommend 12+)

2. **Confirm Master Password**
   - Re-enter the same password

3. **Create Admin Account**
   - Username: Minimum 3 characters
   - Password: Minimum 4 characters (recommend 8+)
   - This is your daily login account

4. Click **"Create Vault"**

### Step 3: Login
1. Enter your **admin username**
2. Enter your **admin password**
3. Click **"Login"**

### Step 4: Add Your First Smith
1. Click **"Add Entry"** button
2. Click **"+ New"** next to the Smith dropdown
3. Enter Smith name (e.g., "John Smith")
4. Click **"Add Smith"**

### Step 5: Add Your First Entry
1. **Date**: Today's date (pre-filled)
2. **Time**: Current time (pre-filled)
3. **Smith**: Select from dropdown
4. **Entry Type**: Choose one:
   - **Smith to Moozhayil**: Smith gives gold to you
   - **Moozhayil to Smith**: You give gold to Smith
5. **Weight**: Enter weight in grams (e.g., 10.5)
6. **Purity**: Enter as:
   - Percentage: 99.5 (for 99.5%)
   - Fineness: 995 (for 995/1000)
7. **Remarks**: Optional notes
8. Click **"Add Entry"**

✅ **Done!** Your first entry is recorded.

---

## 📖 Common Tasks

### View All Entries
1. Click **"View Ledger"** button
2. Use filters to narrow down:
   - Select specific Smith
   - Choose date range
3. Click **"Apply Filters"**

### Generate a Report
1. Click **"Reports"** button
2. Select report type from dropdown
3. Choose filters (date range, Smith, etc.)
4. Click **"Generate Report"**
5. Report opens in new window
6. Click **"Print"** button to print

### Create a Backup
1. Click **"Admin Panel"** button (admin only)
2. Click **"Backup/Restore"** tab
3. Click **"Create Backup"**
4. Backup saved to `GoldVaultData/backups/` folder

### Add a New User (Admin Only)
1. Click **"Admin Panel"**
2. Click **"User Management"** tab
3. Click **"Add User"**
4. Fill in username, password, and role
5. Click **"Add User"**

---

## 🔒 Security Tips

### DO:
- ✅ Write down master password and store in safe
- ✅ Create regular backups (weekly recommended)
- ✅ Lock computer when stepping away
- ✅ Store USB in secure location
- ✅ Use strong passwords (12+ characters)

### DON'T:
- ❌ Share master password with anyone
- ❌ Leave USB plugged in unattended
- ❌ Forget to create backups
- ❌ Use simple passwords like "1234"
- ❌ Store password in plain text file

---

## ⚠️ Important Notes

### About Master Password
- **Encrypts entire database**
- **Cannot be recovered** if lost
- **No backdoor** or reset option
- **Write it down** immediately

### About Purity
- **≤ 100**: Treated as percentage
  - Example: 99.5 = 99.5%
- **> 100**: Treated as fineness
  - Example: 995 = 995/1000

### About Rounding
- **Smith to Moozhayil**: Rounds DOWN (floor)
- **Moozhayil to Smith**: Rounds UP (ceil)
- Always to 3 decimal places

### About Balance
- Shown in **995 basis** (standard purity)
- Automatically recalculated after every change
- Positive = You owe Smith
- Negative = Smith owes you

---

## 🆘 Troubleshooting

### "Vault Locked" Message
**Cause**: USB was removed or session timed out  
**Solution**: Re-insert USB, enter master password

### "Incorrect Master Password"
**Cause**: Wrong password entered  
**Solution**: Try again (3 attempts allowed)  
**If forgotten**: Data is unrecoverable (restore from backup)

### "Session Timed Out"
**Cause**: 10 minutes of inactivity  
**Solution**: Log in again with your user password

### Application Won't Start
**Cause**: Antivirus blocking or USB issue  
**Solution**: 
1. Check if antivirus is blocking
2. Try different USB port
3. Check `GoldVaultData/goldvault.log` for errors

### Entry Balance Looks Wrong
**Cause**: Possible data corruption  
**Solution**: Admin can trigger balance recalculation

---

## 📞 Getting Help

### Self-Help Resources
1. **README.md**: Complete user manual
2. **Log File**: `GoldVaultData/goldvault.log`
3. **This Guide**: Quick reference

### Contact Support
- Check log file first
- Note exact error message
- Contact your system administrator

---

## 🎯 Quick Reference

### Keyboard Shortcuts
- **Tab**: Move to next field
- **Enter**: Submit form
- **Esc**: Close modal (when implemented)

### User Roles
| Permission | Admin | Employee |
|------------|-------|----------|
| Add entry | ✅ | ✅ |
| Edit entry | ✅ | ❌ (request only) |
| Delete entry | ✅ | ❌ |
| Approve requests | ✅ | ❌ |
| Manage users | ✅ | ❌ |
| Clear data | ✅ | ❌ |
| View reports | ✅ | ✅ |

### File Locations
- **Application**: `E:\GoldVault.exe`
- **Database**: `E:\GoldVaultData\ledger.enc`
- **Backups**: `E:\GoldVaultData\backups\`
- **Log File**: `E:\GoldVaultData\goldvault.log`

(Replace E:\ with your USB drive letter)

---

## ✨ Tips & Tricks

### Faster Entry Addition
1. Keep Smith dropdown open
2. Use Tab key to move between fields
3. Purity usually stays same - just change weight

### Better Remarks
- Include job/order number
- Note any special conditions
- Reference customer name if applicable

### Backup Strategy
- **Daily**: If high transaction volume
- **Weekly**: For normal usage
- **Before clearing**: Automatic (built-in)
- **Monthly**: Copy backup to external drive

### Report Tips
- Use date ranges to focus on specific periods
- Smith-wise Ledger shows complete history
- Balance Report gives quick overview
- Print reports for physical records

---

**Need more details?** See **README.md** for complete documentation.

**Ready to build?** See **build_instructions.txt** for deployment.

**Questions?** Check **GoldVaultData/goldvault.log** for error details.
