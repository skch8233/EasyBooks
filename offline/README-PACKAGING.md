# Easy Books Offline for Windows: packaging guide

The offline version is a standalone product. It uses the same Easy Books code but runs entirely on one Windows PC:

```
Easy Books.exe (Electron window)
 ├── mongodb\mongod.exe            local database (data in %APPDATA%\Easy Books\data)
 ├── server\easybooks-server.exe   the Easy Books API + UI on http://127.0.0.1:8765
 └── frontend\                     the React UI built in offline mode
```

Licences use the keys sold on the website (/buy). Each purchase or renewal gives an **activation code** (`EBOL1....`). The code is signed by the website. The app checks it offline with the public key in `desktop/main.js`, so no internet is needed. Without a valid, unexpired code the books are read-only. A renewal key (₹6,500 + GST) is needed every year after the first.

## Build it (one time, about 30 minutes)

You need a Windows 10/11 64-bit PC with:
- Python 3.11 (python.org; tick "Add to PATH")
- Node.js 20 LTS (nodejs.org), then run `npm install -g yarn`
- Git, to download this project (or download the code ZIP from Emergent → GitHub)

Steps (Command Prompt, in the project folder):

1. **Build the UI**: `offline\build_frontend.bat`
2. **Build the server**: `offline\server\build_server.bat`
3. **Add MongoDB**:
   - Download "MongoDB Community Server", Windows x64, ZIP from mongodb.com/try/download/community.
   - Copy `bin\mongod.exe` into `offline\desktop\mongodb\mongod.exe`. Keep any DLL files from the same folder with it.
4. **Add an icon**: put a 256×256 `icon.ico` (for example the Hannusoft logo) in `offline\desktop\`.
5. **Make the installer**:
   ```
   cd offline\desktop
   yarn install
   yarn dist
   ```
   The installer is created at `offline\desktop\dist\EasyBooksSetup-1.0.0.exe`.
6. **Test it**:
   - Install it on a PC, open Easy Books and create the admin login ("Set up your business").
   - Open Licence and paste an activation code. Get one from Platform Admin → "Issue offline licence" on the website.
7. **Publish it**:
   - Upload the .exe to GitHub Releases, Google Drive (set it to "Anyone with the link") or any file host.
   - On the website, open Platform Admin → "Offline .exe download link", paste the link and save.
   - It now appears on `/download`.

## Updating
Change `version` in `offline/desktop/package.json`, repeat steps 1, 2 and 5, then upload the new .exe and update the link. Customer data in `%APPDATA%\Easy Books\data` is kept when updating.

## Important
- **Keep the signing key secret.** `LICENCE_SIGNING_KEY` lives only on the website server (backend/.env). Never put it in the offline app.
- **If you change the signing key pair,** update `LICENCE_PUBLIC_KEY` in both `backend/.env` and `offline/desktop/main.js`. All earlier activation codes will stop working.
- **Prices** are set in `backend/business.py` (`PLANS` and `OFFLINE_PLANS`).
- **Backups:** customers should back up from Settings → Backup & Restore.
