import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
NAME = "EASYTALLY BOOKS"
FILES = [p for d in ("backend", "frontend/src") for p in (root / d).rglob("*") if p.suffix in (".py", ".js", ".jsx") and "tests" not in p.parts]
FILES += [root / f for f in ("offline/desktop/main.js", "offline/server/offline_server.py", "offline/server/build_server.bat", "offline/build-settings.txt")]
FILES += list((root / "offline").glob("*.md"))
for p in FILES:
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    n = s.replace("Easy Books", NAME).replace("`EasyBooks-${r.key}.lic`", "`EASYTALLY-BOOKS-${r.key}.lic`")
    if n != s:
        p.write_text(n, encoding="utf-8")
        print("renamed", p.relative_to(root))

pkg = root / "offline/desktop/package.json"
s = pkg.read_text(encoding="utf-8")
s = re.sub(r'"(productName|shortcutName)": "Easy Books"', rf'"\1": "{NAME}"', s).replace('"description": "Easy Books', f'"description": "{NAME}')
pkg.write_text(s, encoding="utf-8")

main = root / "offline/desktop/main.js"
s = main.read_text(encoding="utf-8")
keep = '// keep data folder of earlier "Easy Books" installs\napp.setPath("userData", path.join(app.getPath("appData"), "Easy Books"));\n'
if keep not in s:
    anchor = re.search(r"^const .*require\(\"path\"\).*\n", s, re.M) or re.search(r"^const .*require\(\"electron\"\).*\n", s, re.M)
    s = s[:anchor.end()] + keep + s[anchor.end():]
    main.write_text(s, encoding="utf-8")

html = root / "frontend/public/index.html"
s = html.read_text(encoding="utf-8")
html.write_text(re.sub(r"<title>.*?</title>", f"<title>{NAME}</title>", s), encoding="utf-8")
