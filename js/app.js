(function () {
    "use strict";

    const DATA_URL = "data/news.json";

    const dom = {
        grid: document.getElementById("newsGrid"),
        loading: document.getElementById("loading"),
        errorMsg: document.getElementById("errorMsg"),
        categoryNav: document.getElementById("categoryNav"),
        lastUpdated: document.getElementById("lastUpdated"),
        themeToggle: document.getElementById("themeToggle"),
        modal: document.getElementById("articleModal"),
        modalBody: document.getElementById("modalBody"),
        modalClose: document.getElementById("modalClose"),
    };

    let newsData = null;
    let activeCategory = "all";

    // --- Theme ---
    function initTheme() {
        const saved = localStorage.getItem("theme");
        if (saved) {
            document.documentElement.setAttribute("data-theme", saved);
        } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
            document.documentElement.setAttribute("data-theme", "dark");
        }

        dom.themeToggle.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("theme", next);
        });
    }

    // --- Modal ---
    function openArticle(article) {
        const categoryMeta = newsData.categories[article.category];
        const categoryLabel = categoryMeta ? categoryMeta.label : article.category;

        let imageHtml = "";
        if (article.image) {
            imageHtml = `<img class="modal-image" src="${escapeHtml(article.image)}" alt="" onerror="this.style.display='none'">`;
        }

        const sourceMeta = newsData.sources ? newsData.sources[article.source] : null;
        const sourceLabel = sourceMeta ? sourceMeta.label : (article.source || "");

        let metaItems = "";
        if (sourceLabel) {
            metaItems += `<span class="modal-meta-item source-tag source-${escapeHtml(article.source || '')}">
                ${escapeHtml(sourceLabel)}
            </span>`;
        }
        if (article.author) {
            metaItems += `<span class="modal-meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                ${escapeHtml(article.author)}
            </span>`;
        }
        if (article.date) {
            metaItems += `<span class="modal-meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                ${escapeHtml(article.date)}
            </span>`;
        }

        let contentHtml;
        if (article.content) {
            const paragraphs = article.content.split("\n\n");
            contentHtml = `<div class="modal-content">` +
                paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join("") +
                `</div>`;
        } else {
            contentHtml = `<div class="modal-no-content">
                <p>Full article content is not available in the reader.</p>
            </div>`;
        }

        dom.modalBody.innerHTML = `
            ${imageHtml}
            <span class="modal-category">${escapeHtml(categoryLabel)}</span>
            <h1 class="modal-title">${escapeHtml(article.title)}</h1>
            ${metaItems ? `<div class="modal-meta">${metaItems}</div>` : ""}
            ${contentHtml}
            <a class="modal-source-link" href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                Read on ${escapeHtml(sourceLabel || 'source')}
            </a>
        `;

        dom.modal.classList.add("active");
        document.body.classList.add("modal-open");
        dom.modal.scrollTop = 0;
    }

    function closeModal() {
        dom.modal.classList.remove("active");
        document.body.classList.remove("modal-open");
    }

    function initModal() {
        dom.modalClose.addEventListener("click", closeModal);

        // Close on overlay click (not modal content)
        dom.modal.addEventListener("click", (e) => {
            if (e.target === dom.modal) {
                closeModal();
            }
        });

        // Close on Escape key
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && dom.modal.classList.contains("active")) {
                closeModal();
            }
        });
    }

    // --- Data ---
    async function fetchNews() {
        try {
            const resp = await fetch(DATA_URL);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            newsData = await resp.json();
            return true;
        } catch (err) {
            console.error("Failed to load news:", err);
            return false;
        }
    }

    // --- Render ---
    function buildCategoryNav() {
        if (!newsData) return;

        const counts = {};
        for (const article of newsData.articles) {
            counts[article.category] = (counts[article.category] || 0) + 1;
        }

        dom.categoryNav.innerHTML = "";

        const allBtn = document.createElement("button");
        allBtn.className = "cat-btn active";
        allBtn.dataset.category = "all";
        allBtn.textContent = `All (${newsData.articles.length})`;
        dom.categoryNav.appendChild(allBtn);

        const order = [
            "kerala", "national", "world", "sports",
            "entertainment", "money-business", "technology", "editorial", "trending"
        ];

        for (const key of order) {
            if (!counts[key]) continue;
            const meta = newsData.categories[key];
            if (!meta) continue;

            const btn = document.createElement("button");
            btn.className = "cat-btn";
            btn.dataset.category = key;
            btn.textContent = `${meta.label}`;
            dom.categoryNav.appendChild(btn);
        }

        dom.categoryNav.addEventListener("click", (e) => {
            const btn = e.target.closest(".cat-btn");
            if (!btn) return;

            dom.categoryNav.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            activeCategory = btn.dataset.category;
            renderArticles();
        });
    }

    function renderArticles() {
        if (!newsData) return;

        let articles = newsData.articles;
        if (activeCategory !== "all") {
            articles = articles.filter(a => a.category === activeCategory);
        }

        dom.grid.innerHTML = "";

        if (articles.length === 0) {
            dom.grid.innerHTML = `<p style="grid-column:1/-1;text-align:center;color:var(--text-secondary);padding:40px;">No articles found in this category.</p>`;
            return;
        }

        for (const article of articles) {
            const card = createCard(article);
            dom.grid.appendChild(card);
        }
    }

    function createCard(article) {
        const card = document.createElement("article");
        card.className = "news-card";

        const categoryMeta = newsData.categories[article.category];
        const categoryLabel = categoryMeta ? categoryMeta.label : article.category;
        const hasContent = !!article.content;
        const srcMeta = newsData.sources ? newsData.sources[article.source] : null;
        const srcLabel = srcMeta ? srcMeta.label : (article.source || "");

        let imageHtml;
        if (article.image) {
            imageHtml = `<img class="card-image" src="${escapeHtml(article.image)}" alt="" loading="lazy" onerror="this.outerHTML='<div class=\\'card-placeholder\\'>ദേ</div>'">`;
        } else {
            imageHtml = `<div class="card-placeholder">ദേ</div>`;
        }

        card.innerHTML = `
            ${imageHtml}
            <div class="card-body">
                <div class="card-tags">
                    <span class="card-category">${escapeHtml(categoryLabel)}</span>
                    ${srcLabel ? `<span class="card-source-tag source-${escapeHtml(article.source || '')}">${escapeHtml(srcLabel)}</span>` : ""}
                </div>
                <h2 class="card-title">${escapeHtml(article.title)}</h2>
                <div class="card-meta">
                    <span class="card-source">
                        ${hasContent ? "Tap to read" : ""}
                        ${article.date ? " · " + escapeHtml(article.date) : ""}
                    </span>
                </div>
            </div>
        `;

        card.addEventListener("click", () => openArticle(article));

        return card;
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function showLastUpdated() {
        if (!newsData || !newsData.last_updated) return;
        try {
            const date = new Date(newsData.last_updated);
            const now = new Date();
            const diffMs = now - date;
            const diffMin = Math.floor(diffMs / 60000);
            const diffHr = Math.floor(diffMin / 60);

            let text;
            if (diffMin < 1) text = "Just now";
            else if (diffMin < 60) text = `${diffMin}m ago`;
            else if (diffHr < 24) text = `${diffHr}h ago`;
            else text = date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });

            dom.lastUpdated.textContent = `Updated ${text}`;
        } catch {
            // ignore
        }
    }

    // --- Init ---
    async function init() {
        initTheme();
        initModal();

        const ok = await fetchNews();

        dom.loading.style.display = "none";

        if (!ok || !newsData || !newsData.articles || newsData.articles.length === 0) {
            dom.errorMsg.style.display = "block";
            return;
        }

        buildCategoryNav();
        renderArticles();
        showLastUpdated();
    }

    init();
})();
