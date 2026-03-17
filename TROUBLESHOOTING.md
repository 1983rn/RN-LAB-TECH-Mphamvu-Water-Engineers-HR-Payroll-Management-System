# TROUBLESHOOTING GUIDE - MPHAMVU WATER ENGINEERS SYSTEM

## HOW TO START THE APPLICATION

### Method 1: Double-click the batch file
1. Double-click `RUN_APPLICATION.bat`
2. Wait for the application to start
3. Open browser and go to: http://localhost:5001

### Method 2: Manual start
1. Open Command Prompt
2. Navigate to the application folder:
   ```
   cd "c:\Users\NANJATI CDSS\Downloads\Programs\HR Payroll Management System"
   ```
3. Run:
   ```
   python app.py
   ```
4. Open browser: http://localhost:5001

---

## COMMON PROBLEMS & SOLUTIONS

### Problem 1: "Python is not recognized"
**Solution:**
1. Install Python from https://www.python.org/downloads/
2. During installation, CHECK "Add Python to PATH"
3. Restart computer
4. Try again

### Problem 2: "ModuleNotFoundError"
**Solution:**
```
pip install -r requirements.txt
```

If that fails, install packages individually:
```
pip install Flask
pip install Flask-SQLAlchemy
pip install reportlab
pip install Werkzeug
```

### Problem 3: "Port 5001 is already in use"
**Solution A - Use different port:**
Edit `app.py`, change last line to:
```python
app.run(debug=True, host='0.0.0.0', port=5002)
```

**Solution B - Kill existing process:**
```
netstat -ano | findstr :5001
taskkill /PID [PID_NUMBER] /F
```

### Problem 4: "Database error"
**Solution:**
Delete the database and restart:
```
del instance\system.db
python app.py
```

### Problem 5: "Template not found"
**Solution:**
Make sure you're in the correct directory:
```
cd "c:\Users\NANJATI CDSS\Downloads\Programs\HR Payroll Management System"
python app.py
```

### Problem 6: Application starts but browser shows error
**Solution:**
1. Clear browser cache
2. Try different browser
3. Use incognito/private mode
4. Check if firewall is blocking

---

## SYSTEM REQUIREMENTS

- Windows 7/8/10/11
- Python 3.8 or higher
- 2GB RAM minimum
- 500MB free disk space
- Modern web browser (Chrome, Firefox, Edge)

---

## DEFAULT LOGIN CREDENTIALS

**Username:** Mphamvuwaterengineers
**Password:** .org.ulandaduwe/2026/**?

**IMPORTANT:** You will be required to change the password on first login.

---

## ACCESSING THE APPLICATION

Once started, the application is available at:
- Local: http://localhost:5001
- Network: http://[YOUR_IP]:5001

To find your IP address:
```
ipconfig
```
Look for "IPv4 Address"

---

## STOPPING THE APPLICATION

Press `Ctrl + C` in the command prompt window

---

## CHECKING IF APPLICATION IS RUNNING

Open browser and go to:
http://localhost:5001

If you see the welcome page, it's working!

---

## REINSTALLING DEPENDENCIES

If you have issues, reinstall all dependencies:

```
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

---

## GETTING HELP

If problems persist:

1. Check the error message in the command prompt
2. Take a screenshot of the error
3. Contact IT support:
   - Email: mphamvuwaterengineers@gmail.com
   - Phone: +265 998 039 554

---

## QUICK DIAGNOSTIC

Run this command to check your setup:
```
python --version
pip --version
pip list
```

Expected output:
- Python 3.8 or higher
- pip installed
- Flask and other packages listed

---

## BACKUP INSTRUCTIONS

To backup your data:
1. Copy the `instance` folder
2. Copy the `database` folder (if exists)
3. Store in a safe location

To restore:
1. Copy folders back to application directory
2. Restart application

---

**MPHAMVU WATER ENGINEERS**
*Always Water*
