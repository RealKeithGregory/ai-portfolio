// Keith Gregory — portfolio scripts.
// Every block checks for its elements first so the same file works on the
// homepage, the blog index, and article pages.

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ─── NEURAL NET BACKGROUND ───────────────────────────────────────
(function neuralBackground() {
  const canvas = document.getElementById('neural-bg');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let nodes = [], W, H;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function initNodes() {
    nodes = [];
    const count = Math.floor((W * H) / 14000);
    for (let i = 0; i < count; i++) {
      nodes.push({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 2 + 1
      });
    }
  }

  function drawFrame(animate) {
    ctx.clearRect(0, 0, W, H);
    nodes.forEach(n => {
      if (animate) {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
      }
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,255,180,0.6)';
      ctx.fill();
    });
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.strokeStyle = `rgba(0,255,180,${0.12 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
    }
  }

  function loop() {
    drawFrame(true);
    requestAnimationFrame(loop);
  }

  resize(); initNodes();
  // With reduced motion the network is drawn once as a static backdrop.
  if (reduceMotion) drawFrame(false); else loop();
  window.addEventListener('resize', () => {
    resize(); initNodes();
    if (reduceMotion) drawFrame(false);
  });
})();

// ─── SCROLL ANIMATIONS ───────────────────────────────────────────
(function scrollReveal() {
  const targets = document.querySelectorAll('.fade-up');
  if (!targets.length) return;
  if (reduceMotion || !('IntersectionObserver' in window)) {
    targets.forEach(el => el.classList.add('visible'));
    return;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
  }, { threshold: 0.1 });
  targets.forEach(el => observer.observe(el));
})();

// ─── MOBILE NAV ──────────────────────────────────────────────────
(function mobileNav() {
  const toggle = document.querySelector('.nav-toggle');
  const links = document.getElementById('nav-links');
  if (!toggle || !links) return;

  function setOpen(open) {
    links.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? 'Close' : 'Menu';
  }

  toggle.addEventListener('click', () => setOpen(!links.classList.contains('open')));
  links.addEventListener('click', e => { if (e.target.tagName === 'A') setOpen(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });
})();

// ─── PORTFOLIO GUIDE (scripted keyword responder, not an LLM) ────
(function portfolioGuide() {
  const win = document.getElementById('chat-window');
  const toggle = document.getElementById('chat-toggle');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const msgs = document.getElementById('chat-messages');
  if (!win || !toggle || !input || !send || !msgs) return;

  let chatOpen = false;

  function toggleChat() {
    chatOpen = !chatOpen;
    win.classList.toggle('open', chatOpen);
    win.hidden = !chatOpen;
    toggle.setAttribute('aria-expanded', String(chatOpen));
    toggle.setAttribute('aria-label', chatOpen ? 'Close portfolio guide' : 'Open portfolio guide');
    toggle.textContent = chatOpen ? '✕' : '💬';
    if (chatOpen) input.focus();
  }

  function addMsg(text, role) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMsg(text, 'user');

    const typing = document.createElement('div');
    typing.className = 'msg bot typing';
    typing.setAttribute('aria-hidden', 'true');
    typing.innerHTML = '<span></span><span></span><span></span>';
    msgs.appendChild(typing);
    msgs.scrollTop = msgs.scrollHeight;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      typing.remove();
      // `detail` is what the server sends when the request is rate limited.
      addMsg(data.reply || data.detail || "I don't have an answer for that. Try the semantic search or the contact links.", 'bot');
    } catch {
      typing.remove();
      addMsg("I couldn't reach the server. The contact links at the bottom of the page still work.", 'bot');
    }
  }

  toggle.addEventListener('click', toggleChat);
  send.addEventListener('click', sendMessage);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });
  document.querySelectorAll('.quick-reply').forEach(btn => {
    btn.addEventListener('click', () => {
      input.value = btn.dataset.message || btn.textContent;
      sendMessage();
    });
  });
})();

// ─── SEMANTIC SEARCH ─────────────────────────────────────────────
(function semanticSearch() {
  const input = document.getElementById('search-input');
  const btn = document.getElementById('search-btn');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  if (!input || !btn || !status || !results) return;

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function runSearch() {
    const query = input.value.trim();
    if (!query) { status.textContent = 'Please enter a search query.'; return; }

    btn.disabled = true;
    btn.textContent = 'Searching...';
    status.textContent = 'Running semantic search...';
    results.innerHTML = '';

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if (res.status === 429) {
        // The endpoint runs a model locally, so it is rate limited. Say so
        // rather than reporting a generic failure.
        const limited = await res.json().catch(() => ({}));
        status.textContent = limited.detail || 'Too many searches. Please wait a moment.';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.results.length) {
        status.textContent = `No results for "${query}"`;
        results.innerHTML = '<p class="search-empty">No results found.</p>';
        return;
      }

      status.textContent = `Top ${data.results.length} results for "${query}", ranked by cosine similarity`;
      data.results.forEach(r => {
        const card = document.createElement('article');
        card.className = 'search-result-card';
        const title = r.url
          ? `<a href="${escapeHtml(r.url)}">${escapeHtml(r.section)}</a>`
          : escapeHtml(r.section);
        card.innerHTML = `
          <div class="result-meta">
            <span class="result-section">${title}</span>
            <span class="result-score">Similarity: ${Number(r.score).toFixed(2)}</span>
          </div>
          <p class="result-text">${escapeHtml(r.snippet || r.text)}</p>
        `;
        results.appendChild(card);
      });
    } catch (err) {
      status.textContent = 'Search unavailable. Please try again.';
      console.error('Search error:', err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Search';
    }
  }

  btn.addEventListener('click', runSearch);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });
  // The input sits in a <form> for assistive technology, but the search is
  // an in-page fetch, so the form must never navigate. Bound here rather
  // than as an inline onsubmit attribute, which the CSP forbids.
  input.form?.addEventListener('submit', e => e.preventDefault());
})();
