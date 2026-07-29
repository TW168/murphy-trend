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
  // Use the submit event's `submitter` when available and
  // fall back to the first submit button in the form.
  form.addEventListener('submit', (evt) => {
    const button = (evt && evt.submitter) || form.querySelector('button[type="submit"]') || form.querySelector('input[type="submit"]');
    if (!button || button.disabled) return;

    // Determine whether this submission will open a new tab/window.
    const btnTarget = (button.getAttribute && button.getAttribute('formtarget')) || (button.formtarget || '');
    const formTargetAttr = form.getAttribute && form.getAttribute('target');
    const opensNewTab = String(btnTarget).toLowerCase() === '_blank' || String(formTargetAttr).toLowerCase() === '_blank' || String(form.target || '').toLowerCase() === '_blank';

    button.dataset.originalHtml = button.innerHTML;

    if (opensNewTab) {
      // For _blank submissions show a short 'Opening...' state but don't disable
      // the button (some browsers may keep the page active when the new tab opens)
      button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Opening...';
      // Revert after a short timeout in case the new tab is blocked or the
      // opener stays on this page.
      window.setTimeout(() => {
        if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
      }, 2000);
      return;
    }

    // Normal same-window submission: disable and show loading state.
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';

    // Safety: if the submission is prevented by a popup blocker or other
    // script and the page remains active, ensure the button is re-enabled
    // after a reasonable timeout so it doesn't stay stuck forever.
    window.setTimeout(() => {
      if (button && button.disabled) {
        button.disabled = false;
        if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
      }
    }, 10000);
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
