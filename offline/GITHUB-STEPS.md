# Get your Windows installer from GitHub: simple steps

You don't need a Windows PC or any software. GitHub builds the installer for you, for free.

## One time: save the code to GitHub
1. In Emergent, click **Save to GitHub** (top right). Pick your GitHub account and create or choose a repository, for example `easybooks`. Click **Save**.
2. That's it. Every time you click **Save to GitHub** again, a new installer is built automatically.

## Watch the build (about 15–25 minutes)
1. Open **github.com**, then your repository.
2. Click the **Actions** tab at the top. You will see **Build Windows installer** with a yellow dot (working).
3. When the dot turns into a **green tick**, the installer is ready. A **red cross** means it failed: click it, then **Re-run all jobs**. If it still fails, send a screenshot of the red step to support.
4. If you see a button saying "I understand my workflows, go ahead and enable them", click it first.

## Find the installer
1. In your repository, click **Releases** on the right side (or open `https://github.com/YOUR-USER/YOUR-REPO/releases`).
2. The newest release, marked **Latest**, has **EasyBooksSetup.exe** under **Assets**.
3. This link always gives the newest installer. Replace the names with yours:
   `https://github.com/YOUR-USER/YOUR-REPO/releases/latest/download/EasyBooksSetup.exe`

## Put it on your Download page
1. Sign in to Easy Books as the platform admin, then open **Platform**, then **Offline licences**.
2. Under **Offline .exe download link**, type your GitHub `user/repo` (for example `ravi/easybooks`) and click **Use latest GitHub release**. Then click **Save**.
3. The `/download` page now has a one-click **Download for Windows** button. You never need to change it again: it always gives the newest build.

**Important:** the repository must be **Public**, or customers can't download the file. To change it: Settings → General → Danger Zone → Change visibility. Your licence signing key is NOT in the code, so making the repository public is safe.

## What customers see
1. Click **Download for Windows** and open **EasyBooksSetup.exe**.
2. Windows may show "Windows protected your PC" because the installer isn't digitally signed yet. Click **More info**, then **Run anyway**.
3. The installer asks no questions. It installs, adds a **desktop shortcut** and opens Easy Books automatically.

## Changing your website address later (one place)
When you have a website, open `offline/build-settings.txt` and change this line:
```
WEBSITE_URL=https://YOUR-EASYBOOKS-SITE
```
to your address, for example `WEBSITE_URL=https://books.hannusoft.com`. Then click **Save to GitHub**. The next installer has "Activate online" switched on. Until then, customers activate with the paste-code option.


## Final offline version (frozen)
The offline Windows version is frozen at the build that includes CA multi-client access.
- The next **Save to GitHub** builds that installer and publishes it as the release `offline-final`, marked latest. The Download page link (`releases/latest/download/EasyBooksSetup.exe`) then serves it.
- Every later push sees that the `offline-final` release exists and skips the whole build. The installer never changes again.
- If the website address must go into the installer, set `WEBSITE_URL` in `offline/build-settings.txt` before that final Save to GitHub.
- To unfreeze on purpose: on GitHub, delete the `offline-final` release (and its tag), then run the workflow again.

## Rebuilding the frozen offline installer with a fix
1. On GitHub open the repository > Releases > "offline-final" > Delete (tick "also delete the tag"; or delete tag `offline-final` under Tags).
2. In Emergent click **Save to GitHub**. The Windows build runs (20-30 min) and publishes a new `offline-final` release (next version number), marked latest.
3. Nothing else is needed: once the new `offline-final` exists, later pushes skip the build again (re-frozen). The Download link stays the same.
