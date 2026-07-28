/* Murphy Trend — main.js */
'use strict';

// ---- Dark mode toggle ----
(function () {
  const html = document.documentElement;
  const btn = document.getElementById('darkToggle');
  const icon = document.getElementById('darkIcon');

  function setTheme(dark) {
    html.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
    if (icon) {
      icon.className = dark ? 'bi bi-sun' : 'bi bi-moon-stars';
    }
    localStorage.setItem('mt-dark', dark ? '1' : '0');
  }

  // Load saved preference
  const saved = localStorage.getItem('mt-dark');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(saved !== null ? saved === '1' : prefersDark);

  if (btn) {
    btn.addEventListener('click', () => {
      setTheme(html.getAttribute('data-bs-theme') !== 'dark');
    });
  }
})();

// ---- Ticker input — auto-uppercase ----
document.querySelectorAll('input[name="ticker"]').forEach(input => {
  input.addEventListener('input', () => {
    const pos = input.selectionStart;
    input.value = input.value.toUpperCase();
    input.setSelectionRange(pos, pos);
  });
});

// ---- Analyze form submit feedback ----
document.querySelectorAll('form[action="/analyze"]').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button || button.disabled) {
      return;
    }

    const opensNewTab = form.target === '_blank' || form.getAttribute('target') === '_blank';
    button.dataset.originalHtml = button.innerHTML;

    if (opensNewTab) {
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Opening...';
      window.setTimeout(() => {
        if (button.dataset.originalHtml) {
          button.innerHTML = button.dataset.originalHtml;
        }
      }, 1500);
      return;
    }

    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';
  });
});

// ---- Plotly render helper with loading state ----
window.mtPlotWithLoader = function mtPlotWithLoader(target, data, layout, config, loadingText) {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el || typeof Plotly === 'undefined') {
    return Promise.resolve();
  }

  el.classList.add('plotly-loading', 'plotly-loading-target');
  el.setAttribute('data-loading-text', loadingText || 'Rendering chart...');

  return Plotly.newPlot(el, data, layout, config)
    .then(() => {
      el.classList.remove('plotly-loading');
      el.removeAttribute('data-loading-text');
    })
    .catch((err) => {
      el.setAttribute('data-loading-text', 'Chart render failed');
      throw err;
    });
};

// ---- Plotly dark-mode sync ----
(function () {
  const chartEl = document.getElementById('chart');
  if (!chartEl) return;

  function updatePlotlyTheme() {
    const dark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    const bg = dark ? '#1a1d23' : '#ffffff';
    const fontColor = dark ? '#e2e8f0' : '#2b2d42';
    const gridColor = dark ? '#2d3248' : '#f0f0f0';
    if (typeof Plotly !== 'undefined') {
      Plotly.relayout(chartEl, {
        plot_bgcolor: bg,
        paper_bgcolor: bg,
        'font.color': fontColor,
        'xaxis.gridcolor': gridColor,
        'yaxis.gridcolor': gridColor,
        'xaxis2.gridcolor': gridColor,
        'yaxis2.gridcolor': gridColor,
        'xaxis3.gridcolor': gridColor,
        'yaxis3.gridcolor': gridColor,
      });
    }
  }

  // Watch for theme changes
  const observer = new MutationObserver(updatePlotlyTheme);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
})();
