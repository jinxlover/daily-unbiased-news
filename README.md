# Daily Unbiased News

Daily Unbiased News is a simple, static news aggregator designed to pull the
latest headlines from multiple reputable sources and surface them in a clean,
mobile‑friendly interface. The site is automatically refreshed every day via
a GitHub Action, ensuring you always see up‑to‑date stories without any
manual intervention.

## Features

- **Multiple sources:** The aggregator pulls RSS feeds from a selection of
  sources such as Reuters, BBC, Al Jazeera, NPR and AP (via Google News).
  The feed URLs are defined in `feeds.json` and can easily be extended or
  modified.
- **Category sections:** News items are grouped into major categories
  (World, Politics, Tech, Science, Business, Culture). Each section
  displays up to 50 of the most recent unique headlines across all sources.
- **Duplicate filtering:** Articles are deduplicated by title across all
  categories to avoid repeating the same story from multiple outlets.
- **Live ticker:** A horizontal ticker bar shows the latest headlines from
  across all categories. Links open in a new tab.
- **Search:** A client‑side search bar lets you filter articles by
  keyword across titles and descriptions.
- **Daily refresh:** A GitHub Action defined in `.github/workflows/update.yml`
  runs the `fetch_news.py` script every 24 hours. This script fetches
  the RSS feeds, deduplicates and sorts the results, then writes them to
  `data/news.json`. If the data changes, the action commits and pushes the
  updated JSON back to your repository.
- **Easy deployment:** Because the site is entirely static, it can be
  deployed to GitHub Pages, Netlify, Vercel or any other static hosting
  platform. Simply point the host to the `news_site` directory and ensure
  that the GitHub Action has permission to push updates.

## Getting Started

1. **Clone this repository** and navigate into the `news_site` directory.

   ```sh
   git clone https://github.com/yourusername/daily-unbiased-news.git
   cd daily-unbiased-news/news_site
   ```

2. **Install Python dependencies** (no external packages required; the
   script uses only the standard library).

3. **Test locally.** You can run a simple HTTP server to preview the
   site:

   ```sh
   python -m http.server 8000
   ```

   Then open `http://localhost:8000/news_site/` in your browser. (Some
   browsers block `fetch()` of local JSON over `file://`; serving via
   HTTP avoids this.)

4. **Configure and deploy.** Push your repository to GitHub and enable
   GitHub Pages or link it to a static hosting service like Netlify or
   Vercel. Ensure that GitHub Actions are enabled so the daily refresh can
   commit new data. You may wish to set the deployment branch to
   `main` or `gh-pages` depending on your chosen hosting platform.

5. **Customize.** Edit `feeds.json` to add, remove or modify feed URLs.
   Each key in the JSON corresponds to a category on the site. When adding
   new feeds, ensure they provide RSS or Atom content. The `fetch_news.py`
   script will automatically pick up the changes on the next run.

## Notes

- Some providers, such as AP, no longer offer official RSS feeds. This
  repository defaults to using Google News queries scoped to AP (via
  `site:apnews.com`) to surface AP stories. If you have access to
  official feeds, update `feeds.json` accordingly.
- The automation workflow commits only changes to `data/news.json`. If you
  edit the HTML, CSS or JavaScript files you should commit those changes
  manually.
- If a feed cannot be fetched or parsed, the script skips it and
  continues. Transient errors therefore do not block the update
  altogether.

## License

This project is provided under the MIT License. See the [LICENSE](../LICENSE)
file for details.