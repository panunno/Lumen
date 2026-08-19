# Publishing Lumen (free, on Streamlit Community Cloud)

This gives Lumen a public web link you can open from any device and share. It stays fully
editable — you change the code, push the change, and the live site updates in about a minute.

---

## One-time setup

### 1. Make a GitHub account
Go to https://github.com and sign up (free).

### 2. Create a repository and add Lumen's files
- Click **New repository**, name it `lumen`, and create it.
- Upload these files (drag-and-drop on the GitHub website works):
  - `app.py`
  - `requirements.txt`
  - `favicon.png`
  - `README.md`
  - the `.streamlit/config.toml` file (keep it inside a `.streamlit` folder)
- **Do NOT upload** `portfolio.csv`, `watchlist.csv`, or `alerts.csv` — those hold your
  personal data. (The included `.gitignore` skips them automatically if you use Git.)

### 3. Deploy
- Go to https://share.streamlit.io and sign in with GitHub.
- Click **New app**, choose your `lumen` repo, branch `main`, main file `app.py`, and **Deploy**.
- Wait a minute while it installs and builds. You'll get a URL like
  `https://lumen-yourname.streamlit.app`.

### 4. Turn on multi-user mode (important)
So each visitor gets their own private, blank portfolio (not yours):
- In the app's page on Streamlit Cloud, open **Settings → Secrets**.
- Add this line and save:
  ```
  MULTIUSER = "true"
  ```
- The app reboots. Now every visitor's data lives only in their own session, and they use the
  **Download / Upload** buttons to keep their own copy.

That's it — share the link.

---

## Making updates later

Your workflow stays the same:
1. Edit `app.py` on your computer and test locally with `streamlit run app.py`.
2. When it works, update the file on GitHub (re-upload it on the website, or `git push`).
3. The live site **auto-redeploys** in ~1 minute.

You can update as often as you like, and test privately before pushing.

---

## Notes
- **Local vs. published behavior:** With no `MULTIUSER` secret (i.e. on your computer), Lumen
  stays in single-user mode and auto-saves your data to the CSV files like always. The secret
  only changes behavior on the published app.
- **Cost:** Streamlit Community Cloud is free for this kind of app.
- **Data on the cloud is not permanent** by design (it's per-session). Everyone, including you,
  keeps their data with the Download/Upload buttons on the published app.
