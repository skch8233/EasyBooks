# Easy Books Offline for Windows: packaging guide

The offline version is a standalone product. It uses the same Easy Books code but runs entirely on one Windows PC:

```
Easy Books.exe (Electron window)
 ├── mongodb\mongod.exe            local database (data in %APPDATA%\Easy Books\data)
 ├── server\easybooks-server.exe   the Easy Books API + UI on http://127.0.0.1:8765
 └── frontend\                     the React UI built in offline mode
```

Licences use the keys sold on the website (/buy). **Each licence key works on one PC only.** The buyer gets the key (`EB-XXXX-XXXX-XXXX-XXXX`) and a GST invoice by email right after payment. Activation:

1. The offline app shows this PC's **Machine ID** on the Licence screen.
2. **Activate online:** enter the key and click Activate online. The website locks the key to that Machine ID and sends back a signed **activation code** (`EBOL1....`). Internet is needed only for this one step.
3. **No internet on the PC:** on any phone or PC, open `<your site>/activate`, enter the key and Machine ID, then paste the code (or open the .lic file) on the Licence screen.

The app checks the code offline with the public key in `desktop/main.js`. It refuses codes made for another computer. Without a valid, unexpired code for this PC, the books are read-only. A renewal key (₹6,500 + GST) is needed every year after the first. After renewing, click Activate online again on the same PC.

**Moving to a new PC:** on the website, open Platform Admin → offline licences → **Reset PC**, then activate on the new PC. The old PC keeps working until its current code expires, because offline codes can't be cancelled remotely.

**Codes issued before the one-PC lock (Round 5) no longer work.** Activate those customers again with their key.

## Easiest: automatic build on GitHub (no Windows PC needed)
See **`offline/GITHUB-STEPS.md`**. Every **Save to GitHub** runs `.github/workflows/build-windows.yml` on a Windows machine at GitHub. It builds the UI, the server, adds MongoDB, makes the one-click installer and publishes `EasyBooksSetup.exe` to GitHub Releases. The version is 1.0.<build number>.

The installer is one-click: no questions, per-user install, desktop + Start menu shortcut, and it opens Easy Books when done.

## Before you build: set your website address (one place)
Edit `offline/build-settings.txt` → `WEBSITE_URL=`. Both the GitHub build and `build_frontend.bat` read it. While it is `https://YOUR-EASYBOOKS-SITE`, the "Activate online" button is disabled and customers use the paste-code option (`/activate` page).

## Manual build on your own Windows PC (optional)

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
4. **Icon**: `offline\desktop\icon.ico` is included; replace it with your own 256×256 icon if you like.
5. **Make the installer**:
   ```
   cd offline\desktop
   yarn install
   yarn dist
   ```
   The installer is created at `offline\desktop\dist\EasyBooksSetup.exe`.
6. **Test it**:
   - Install it on a PC, open Easy Books and create the admin login ("Set up your business").
   - Open Licence, enter a licence key and click Activate online. Get a key from Platform Admin → "Issue offline licence" on the website.
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
- **Invoice seller details:** fill `SELLER_GSTIN` and `SELLER_ADDRESS` in `backend/.env`. While they are blank, invoices don't show them and always use CGST + SGST.
- **Backups:** customers should back up from Settings → Backup & Restore.

## Lock files
The platform's Save to GitHub does not upload `yarn.lock` files. Copies are kept in `offline/locks/` (`frontend-yarn-lock.txt`, `desktop-yarn-lock.txt`), and the GitHub build restores them before installing. If you add or upgrade packages, refresh the copies:
```
cp frontend/yarn.lock offline/locks/frontend-yarn-lock.txt
cp offline/desktop/yarn.lock offline/locks/desktop-yarn-lock.txt
```
If a copy is missing, the build still works. It installs the latest versions allowed by package.json.
