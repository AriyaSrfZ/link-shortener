# Uploading to GitHub

This repo is already git-initialized locally with commit history (tags
`v0.1` through `v0.5`), authored by Ariya Sarrafzadeh. These steps push
it to a new repository under your account, **AriyaSrfZ**.

## 1. Create the empty repository on GitHub
Go to https://github.com/new and create a repository named:
```
link-shortener
```
Leave it empty — do **not** check "Add a README", "Add .gitignore", or
"Choose a license". This repo already has those; checking them on
GitHub's side creates conflicting history.

Set it to Private or Public, your choice.

## 2. Connect your local repo to GitHub and push
Open a terminal in the project folder and run these exact commands:

```
git remote add origin https://github.com/AriyaSrfZ/link-shortener.git
git branch -M main
git push -u origin main
git push origin --tags
```

If VS Code or your terminal prompts for credentials, use a GitHub
Personal Access Token as the password (GitHub stopped accepting account
passwords for git operations). Create one at:
https://github.com/settings/tokens → "Generate new token (classic)" →
check the `repo` scope.

## 3. Verify
Refresh your GitHub repo page. You should see:
- 5 commits, all authored by Ariya Sarrafzadeh
- 5 tags: `v0.1`, `v0.2`, `v0.3`, `v0.4`, `v0.5`
- The full file tree (`app/`, `tests/`, `docs/`, `README.md`, etc.)

## 4. Ongoing workflow
Every time you make changes going forward:
```
git add -A
git commit -m "Describe what changed"
git push
```
Tag meaningful milestones as you go:
```
git tag v0.6
git push origin --tags
```

## Common push errors and fixes

**"remote origin already exists"**
You ran `git remote add origin ...` twice. Fix:
```
git remote set-url origin https://github.com/AriyaSrfZ/link-shortener.git
```

**"failed to push some refs" / "fetch first"**
Your GitHub repo has commits your local copy doesn't (this shouldn't
happen if you created it empty in step 1, but if it does):
```
git pull origin main --allow-unrelated-histories
git push -u origin main
```

**Authentication failed**
You're using your GitHub password instead of a token. Generate a
Personal Access Token as described in step 2 and use that instead.

**"src refspec main does not match any"**
Your local branch is still named `master`. Fix:
```
git branch -M main
git push -u origin main
```
