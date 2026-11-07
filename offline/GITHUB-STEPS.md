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
When you have a website, open `offline/settings.env` and change this line:
```
WEBSITE_URL=https://YOUR-EASYBOOKS-SITE
```
to your address, for example `WEBSITE_URL=https://books.hannusoft.com`. Then click **Save to GitHub**. The next installer has "Activate online" switched on. Until then, customers activate with the paste-code option.
