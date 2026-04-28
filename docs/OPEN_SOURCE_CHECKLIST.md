# Open Source Release Checklist

## Before GitHub Upload

macOS / Linux:

```bash
python -m py_compile $(find src -name '*.py')
python -m unittest discover -s tests
fanqie-lab open-source-check
git add -n .
```

Windows:

```powershell
python -c "import pathlib, py_compile; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('src').rglob('*.py')]"
python -m unittest discover -s tests
fanqie-lab open-source-check
git add -n .
```

Check ignored files:

```bash
git status --ignored
```

Do not upload:

- `.env`
- `.venv/`
- `.npm-cache/`
- `electron-client/node_modules/`
- `data/config/model_profiles.json`
- `data/db/*.sqlite3`
- `outputs/`
- `logs/`

## Recommended GitHub Settings

- Add repository description and topics.
- Enable Issues and Discussions if you want community feedback.
- Enable Dependabot alerts.
- Protect `main` after the first release.
- Add a release tag such as `v0.1.0`.

## First Push

```bash
git init
git add .
git status
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/RrcioElise/fanqie-novel-lab.git
git push -u origin main
```

Pushing sends local files to GitHub. Review `git status` and `git diff --cached` before the final push.


## Community files

- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- Issue / PR templates
- CI and Dependabot config

## UI check

Open the app and visit the Export page. The “开源发布” tab shows the same readiness scan as the CLI.
