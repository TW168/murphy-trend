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
