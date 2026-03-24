# Deshabhimani News Reader

A static news reader webapp that aggregates top news from [deshabhimani.com](https://www.deshabhimani.com) — a leading Malayalam newspaper from Kerala, India.

**Live site:** _Deploy to GitHub Pages to get your URL_

## Features

- **Category tags**: Kerala, National, International, Sports, Entertainment, Business, Technology, Editorial
- **Auto-refresh**: GitHub Actions scrapes fresh news every hour
- **Dark mode**: Respects system preference with manual toggle
- **Responsive**: Works on mobile, tablet, and desktop
- **Fast**: Static site with no runtime dependencies

## How it works

```
GitHub Actions (hourly cron)
    → Python scraper fetches deshabhimani.com
    → Generates data/news.json
    → Commits to repo
    → GitHub Pages serves updated static site
```

## Setup

### 1. Create a GitHub repo

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/newsreader.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to **Settings → Pages**
2. Set source to **GitHub Actions** (or `main` branch, root `/`)
3. Save

### 3. Run the scraper for the first time

Either push to trigger the Action, or run manually:
- Go to **Actions → Update News → Run workflow**

### 4. (Optional) Run locally

```bash
pip install -r requirements.txt
python scripts/scrape.py
python -m http.server 8080
# Open http://localhost:8080
```

## Project Structure

```
├── index.html                  # Main page
├── css/style.css               # Styles
├── js/app.js                   # Frontend logic
├── data/news.json              # Generated news data (auto-updated)
├── scripts/scrape.py           # Python news scraper
├── requirements.txt            # Python dependencies
└── .github/workflows/
    └── update-news.yml         # Hourly GitHub Actions workflow
```

## License

News content is sourced from [deshabhimani.com](https://www.deshabhimani.com) which is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
