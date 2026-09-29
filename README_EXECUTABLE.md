# KNOT Project - Windows Executable

This is a fully standalone Windows executable of the KNOT platform - a Django-based web application for item booking and campaigns. The executable includes all necessary components and requires no separate Python installation.

## Quick Start (5 Minutes)

### 1. Setup Environment Variables
1. Copy `.env.example` and rename it to `.env` in the **same folder as knot-launcher.exe**
2. Open `.env` in a text editor and fill in your values:
   ```
   DJANGO_SECRET_KEY=your-secret-key-here
   DJANGO_DEBUG=False
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password
   PAYHERO_PUBLIC_KEY=your-public-key
   PAYHERO_PRIVATE_KEY=your-private-key
   PAYHERO_TEST_MODE=True
   ```

### 2. Run the Executable
1. Double-click `knot-launcher.exe`
2. Wait for the message: "Starting development server at http://127.0.0.1:8000/"
3. Open your browser and go to `http://127.0.0.1:8000/`

### 3. Stop the Server
- Press `Ctrl+Break` in the terminal window to stop the server

## What's Included

✅ **Complete Django Project** - All source code and configurations  
✅ **SQLite Database** - Fully configured and ready to use  
✅ **Django 6.0** - Latest stable version  
✅ **REST API** - Django REST Framework enabled  
✅ **Email Support** - Gmail SMTP integration  
✅ **Email Verification** - Built-in user verification system  
✅ **Payment Processing** - PayHero integration ready  
✅ **CORS Support** - Cross-origin requests enabled  
✅ **Static Files** - CSS, JavaScript, and media files bundled  

## Environment Variables Explained

| Variable | Purpose | Example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django encryption key (keep secure!) | `your-super-secret-key` |
| `DJANGO_DEBUG` | Debug mode (use `False` in production) | `False` |
| `DJANGO_ALLOWED_HOSTS` | Allowed hostnames (comma-separated) | `localhost,127.0.0.1` |
| `EMAIL_HOST_USER` | Gmail address for sending emails | `your-email@gmail.com` |
| `EMAIL_HOST_PASSWORD` | Gmail app-specific password | `abcd efgh ijkl mnop` |
| `PAYHERO_PUBLIC_KEY` | PayHero API public key | `pk_test_xxxxx` |
| `PAYHERO_PRIVATE_KEY` | PayHero API private key | `sk_test_xxxxx` |
| `PAYHERO_TEST_MODE` | Use PayHero test environment | `True` |
| `NGROK_URL` | ngrok tunnel URL (optional) | `https://xxxxx.ngrok.io` |

## Troubleshooting

### Problem: "Startup failed. See: knot-launcher-error.log"
- Open `knot-launcher-error.log` in the same folder to see the error
- Most common cause: Missing or incorrect `.env` variables
- Ensure `.env` is in the same folder as `knot-launcher.exe`

### Problem: "Address already in use" or "Port 8000 is already in use"
- Another application is using port 8000
- Wait a minute and try again, or use `netstat -ano | findstr :8000` to identify the process

### Problem: Django system checks show warnings
- Minor warnings like missing assets directories can be ignored
- The application will still function correctly

### Problem: Database doesn't have any data
- The database comes fresh with Django schema but no sample data
- Create test users and data through the Django admin interface

## Features

### For Users
- Browse and book available items
- View campaign details
- Submit feedback and ratings
- Manage user profile
- Email verification for security

### For Administrators
- Admin dashboard for managing users and content
- Booking approval and management
- Campaign creation and monitoring
- Item inventory management
- User and payment reports

### For Developers (if modifying the executable)
- Full Django 6.0 project structure
- DRF (Django REST Framework) for API endpoints
- django-cors-headers for CORS support
- django-verify-email for email verification
- Pillow for image handling

## Security Notes

⚠️ **CRITICAL**: 
- **Never** share or commit the `.env` file
- **Never** set `DJANGO_DEBUG = True` in production
- **Always** use a strong `DJANGO_SECRET_KEY`
- Keep your API keys (`PAYHERO_PRIVATE_KEY`, `EMAIL_HOST_PASSWORD`) confidential

## System Requirements

- **OS**: Windows 10 or later (64-bit)
- **Memory**: 512 MB minimum (1 GB recommended)
- **Disk Space**: 200 MB for the executable + space for media uploads
- **Network**: Internet connection for email and payment processing
- **Ports**: Port 8000 must be available

## First Time Setup Checklist

- [ ] Extracted executable to desired location
- [ ] Created `.env` file from `.env.example`
- [ ] Filled in all required environment variables
- [ ] Verified Gmail app password is correct
- [ ] Verified PayHero API keys are correct
- [ ] Ran `knot-launcher.exe` successfully
- [ ] Accessed `http://127.0.0.1:8000/` in browser

## Database

The application uses SQLite3, which is included and configured by default.

- **Database file**: `db.sqlite3` (in the same folder as exe)
- **Migrations**: Applied automatically on startup
- **Backup**: Simply copy `db.sqlite3` to back up all data

## Default Admin Access

After first run:
1. Go to `http://127.0.0.1:8000/admin/`
2. Create a superuser if prompted
3. Log in with your superuser credentials

## Advanced Usage

### Custom Port
Edit the launcher source code to change from port 8000 to another port.

### Loading Sample Data
Contact the development team for sample data SQL dump to populate the database.

### Production Deployment
This development server should **NOT** be used in production. For production:
1. Use Gunicorn or uWSGI as application server
2. Use Nginx or Apache as reverse proxy
3. Set `DJANGO_DEBUG = False`
4. Use a production database (PostgreSQL recommended)
5. Configure HTTPS/SSL certificates

## Package Contents

```
dist/
├── knot-launcher.exe          # Main executable - double-click to run
├── .env.example               # Template for environment variables
└── README_EXECUTABLE.md       # This file

docs/
├── SDD.md                     # System Design Documentation
├── SRS_Current_Implementation.md  # Requirements Specification
└── User_Manual.md             # User guide
```

## Support & Contact

For issues or questions:
1. Check this README and troubleshooting section first
2. Review Django error logs in `knot-launcher-error.log` (if it appears)
3. Check the `docs/` folder for additional project documentation
4. Contact the development team for technical support

## Important - No Sensitive Data Included

✅ This executable contains **NO hardcoded API keys or credentials**  
✅ All sensitive information is configured via the `.env` file  
✅ The `.env` file is **NOT included** - you must create it yourself  
✅ Safe to share with teams and stakeholders  

---

**Version**: 1.0  
**Built**: May 2026  
**Python Version**: 3.13  
**Django Version**: 6.0.2  
**Architecture**: Windows 64-bit
