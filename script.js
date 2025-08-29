/*
 * Client‑side script to power the Daily Unbiased News site. This script
 * dynamically populates the navigation, ticker and content sections based
 * on the data fetched from ``data/news.json``. It also provides a basic
 * search functionality that filters across all articles by headline or
 * description.
 */

  document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const navContainer = document.getElementById('categoryNav');
    const contentContainer = document.getElementById('content');
    const tickerContent = document.getElementById('tickerContent');
    const yearSpan = document.getElementById('year');
    const backToTopBtn = document.getElementById('backToTop');
    yearSpan.textContent = new Date().getFullYear();

    backToTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    function toggleBackToTop() {
      backToTopBtn.style.display = window.scrollY > 100 ? 'block' : 'none';
    }
    window.addEventListener('scroll', toggleBackToTop);
    toggleBackToTop();

  const parseDate = str => new Date(str.endsWith('Z') ? str : `${str}Z`);

  /**
   * Fetch the latest news JSON and rebuild the page.
   * This is invoked on initial load and every 10 minutes thereafter to
   * ensure the content stays fresh without requiring a full page refresh.
   */
  function fetchAndRender() {
    fetch('data/news.json')
      .then(res => res.json())
      .then(data => {
        // Clear existing content before rebuilding
        navContainer.innerHTML = '';
        contentContainer.innerHTML = '';
        tickerContent.innerHTML = '';

        const categories = Object.keys(data.news);
        buildNav(categories);
        buildSections(data.news);
        buildTicker(data.news);
        attachSearch(data.news);
      })
      .catch(err => {
        console.error('Failed to load news data:', err);
      });
  }

  // Initial fetch and subsequent refresh every 10 minutes
  fetchAndRender();
  setInterval(fetchAndRender, 10 * 60 * 1000);

  /**
   * Build the category navigation buttons.
   * Clicking a button scrolls smoothly to its section.
   */
  function buildNav(categories) {
    categories.forEach((cat, index) => {
      const btn = document.createElement('button');
      btn.className = 'tab';
      btn.textContent = cat;
      btn.addEventListener('click', () => {
        const section = document.getElementById(cat.toLowerCase());
        if (section) {
          section.scrollIntoView({ behavior: 'smooth' });
        }
        // Update active state
        [...navContainer.children].forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
      // Set the first button active by default
      if (index === 0) btn.classList.add('active');
      navContainer.appendChild(btn);
    });
  }

  /**
   * Build the main news sections for each category.
   */
  function buildSections(newsData) {
    Object.entries(newsData).forEach(([category, articles]) => {
      const section = document.createElement('section');
      section.id = category.toLowerCase();
      const heading = document.createElement('h2');
      heading.className = 'section-title';
      heading.textContent = category;
      section.appendChild(heading);

      const list = document.createElement('div');
      list.className = 'article-list';

      let displayArticles = articles;
      if (category === 'Gaming') {
        // Prioritize Steam entries
        displayArticles = [...articles].sort((a, b) => {
          return (a.source !== 'store.steampowered.com') - (b.source !== 'store.steampowered.com');
        });
      }

      const elements = [];
      displayArticles.forEach(article => {
        const el = createArticleElement(article);
        if (el) elements.push(el);
      });

      if (elements.length === 0) {
        const p = document.createElement('p');
        p.textContent = 'No articles available.';
        list.appendChild(p);
      } else {
        elements.forEach(el => list.appendChild(el));
      }

      section.appendChild(list);
      contentContainer.appendChild(section);
    });
  }

  /**
   * Create a DOM element for a single news article.
   */
  function createArticleElement(article) {
    if (!article.image) return null;
    const wrapper = document.createElement('article');
    wrapper.className = 'article';

    const textWrap = document.createElement('div');

    const meta = document.createElement('div');
    meta.className = 'article-meta';
    const date = parseDate(article.pubDate);
    const biasValue = typeof article.bias === 'number' ? article.bias : 0;
    const biasMeter = document.createElement('span');
    biasMeter.className = 'bias-meter';
    biasMeter.title = `Bias: ${biasValue} (−1 left, 0 center, +1 right)`;
    if (biasValue < 0) biasMeter.classList.add('bias-left');
    else if (biasValue > 0) biasMeter.classList.add('bias-right');
    meta.appendChild(biasMeter);
    const metaText = document.createElement('span');
    metaText.textContent = `${article.source || ''} • ${date.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    })}`;
    meta.appendChild(metaText);

    const titleEl = document.createElement('h3');
    titleEl.className = 'article-title';
    const link = document.createElement('a');
    link.href = article.link;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = article.title;
    titleEl.appendChild(link);

    const desc = document.createElement('p');
    desc.className = 'article-excerpt';
    const trimmed = article.description.length > 200 ? article.description.slice(0, 197) + '…' : article.description;
    desc.textContent = trimmed;

    textWrap.appendChild(meta);
    textWrap.appendChild(titleEl);
    if (trimmed) textWrap.appendChild(desc);
    wrapper.appendChild(textWrap);

    const img = document.createElement('img');
    img.className = 'article-thumb';
    img.src = article.image;
    img.alt = article.title;
    img.loading = 'lazy';
    wrapper.appendChild(img);

    // Comments functionality has been removed to simplify the interface

    return wrapper;
  }

  /**
   * Build a scrolling ticker with the newest headlines across all categories.
   */
  function buildTicker(newsData) {
    const allItems = [];
    Object.values(newsData).forEach(arr => {
      allItems.push(...arr.filter(a => a.image));
    });
    // Sort globally by pubDate
    allItems.sort((a, b) => parseDate(b.pubDate) - parseDate(a.pubDate));
    const top = allItems.slice(0, 15);
    // Build markup: each item separated by bullet
    const fragments = top.map(
      item => `<span class="ticker-item"><a href="${item.link}" target="_blank" rel="noopener noreferrer">${item.title}</a></span>`
    );
    tickerContent.innerHTML = fragments.join(' • ');
  }

  /**
   * Attach search functionality to the search input.
   */
  function attachSearch(newsData) {
    const originalSections = {}; // Preserve original HTML for reset
    Object.keys(newsData).forEach(cat => {
      const section = document.getElementById(cat.toLowerCase());
      if (section) {
        originalSections[cat] = section.innerHTML;
      }
    });
    searchInput.oninput = () => {
      const query = searchInput.value.trim().toLowerCase();
      if (!query) {
        // Restore original content
        Object.keys(newsData).forEach(cat => {
          const section = document.getElementById(cat.toLowerCase());
          if (section) {
            section.innerHTML = originalSections[cat];
          }
        });
        return;
      }
      // Filter articles
      Object.entries(newsData).forEach(([cat, articles]) => {
        const section = document.getElementById(cat.toLowerCase());
        if (!section) return;
        section.innerHTML = '';
        const heading = document.createElement('h2');
        heading.className = 'section-title';
        heading.textContent = cat;
        section.appendChild(heading);

        const list = document.createElement('div');
        list.className = 'article-list';

        const matches = articles.filter(a => {
          return a.title.toLowerCase().includes(query) || a.description.toLowerCase().includes(query);
        });
        const elements = [];
        matches.forEach(item => {
          const el = createArticleElement(item);
          if (el) elements.push(el);
        });

        if (elements.length === 0) {
          const p = document.createElement('p');
          p.textContent = 'No results.';
          list.appendChild(p);
        } else {
          elements.forEach(el => list.appendChild(el));
        }
        section.appendChild(list);
      });
    };
  }
});
