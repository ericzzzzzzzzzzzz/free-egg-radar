/* FreeEgg Radar 模型榜逻辑 */
(function () {
  'use strict';

  var state = {
    models: [],
    filtered: [],
    activeVendor: 'all',
    search: ''
  };

  var grid = document.getElementById('model-grid');
  var vendorFilters = document.getElementById('vendor-filters');
  var searchInput = document.getElementById('model-filter-q');
  var updatedAt = document.getElementById('model-updated-at');

  function init() {
    loadData();
    bindEvents();
  }

  function loadData() {
    fetch('data/models.json')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        state.models = data.models || [];
        state.filtered = state.models.slice();

        if (updatedAt && data.version) {
          updatedAt.textContent = '数据更新：' + data.version + ' · 共 ' + state.models.length + ' 个模型 · 自动抓取';
        }

        buildVendorFilters();
        render();
      })
      .catch(function (err) {
        console.error('加载模型数据失败:', err);
        if (grid) grid.innerHTML = '<div class="empty">数据加载失败，请稍后重试</div>';
      });
  }

  function buildVendorFilters() {
    if (!vendorFilters) return;

    var vendors = {};
    state.models.forEach(function (m) {
      var v = m.vendor || '未知';
      vendors[v] = (vendors[v] || 0) + 1;
    });

    var vendorList = Object.keys(vendors).sort(function (a, b) {
      return vendors[b] - vendors[a];
    });

    var html = '<span class="flabel">厂商</span>';
    html += '<button class="chip active" data-vendor="all">全部</button>';
    vendorList.slice(0, 10).forEach(function (v) {
      html += '<button class="chip" data-vendor="' + escapeHtml(v) + '">' + escapeHtml(v) + ' (' + vendors[v] + ')</button>';
    });

    vendorFilters.innerHTML = html;
  }

  function bindEvents() {
    if (vendorFilters) {
      vendorFilters.addEventListener('click', function (e) {
        var btn = e.target.closest('.chip');
        if (!btn) return;
        var vendor = btn.getAttribute('data-vendor');
        state.activeVendor = vendor;

        vendorFilters.querySelectorAll('.chip').forEach(function (c) {
          c.classList.toggle('active', c.getAttribute('data-vendor') === vendor);
        });

        applyFilters();
      });
    }

    if (searchInput) {
      var timer;
      searchInput.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          state.search = searchInput.value.trim().toLowerCase();
          applyFilters();
        }, 200);
      });
    }
  }

  function applyFilters() {
    state.filtered = state.models.filter(function (m) {
      if (state.activeVendor !== 'all' && m.vendor !== state.activeVendor) {
        return false;
      }
      if (state.search) {
        var name = (m.name || '').toLowerCase();
        var vendor = (m.vendor || '').toLowerCase();
        if (name.indexOf(state.search) === -1 && vendor.indexOf(state.search) === -1) {
          return false;
        }
      }
      return true;
    });
    render();
  }

  function render() {
    if (!grid) return;

    if (state.filtered.length === 0) {
      grid.innerHTML = '<div class="empty">没有找到匹配的模型</div>';
      return;
    }

    var html = '';
    state.filtered.forEach(function (m, i) {
      var rankClass = '';
      if (i === 0) rankClass = ' top1';
      else if (i === 1) rankClass = ' top2';
      else if (i === 2) rankClass = ' top3';

      var inputCost = m.inputCost != null ? '$' + formatPrice(m.inputCost) : '—';
      var outputCost = m.outputCost != null ? '$' + formatPrice(m.outputCost) : '—';

      // 数据来源标签
      var sourceTags = '';
      if (m.lmsysElo) sourceTags += '<span class="tag" style="color:#34d399;border-color:rgba(52,211,153,0.3);background:rgba(52,211,153,0.06);">LMSYS</span>';
      if (m.priceSource === 'openrouter') sourceTags += '<span class="tag" style="color:#06b6d4;border-color:rgba(6,182,212,0.3);background:rgba(6,182,212,0.06);">OpenRouter</span>';
      if (!m.lmsysElo && m.priceSource !== 'openrouter') sourceTags += '<span class="tag">Seed</span>';

      html += '<article class="model-card' + rankClass + '" style="animation-delay:' + (i * 0.03) + 's">';
      html += '<div class="model-rank">' + (i + 1) + '</div>';
      html += '<div class="model-name">' + escapeHtml(m.name || '未知模型') + '</div>';
      html += '<div class="model-vendor">' + escapeHtml(m.vendor || '未知') + '</div>';
      if (sourceTags) html += '<div class="egg-tags" style="margin-top:-4px;">' + sourceTags + '</div>';
      html += '<div class="model-pricing">';
      html += '<div class="price-item"><div class="price-label">输入</div><div class="price-value">' + inputCost + '</div></div>';
      html += '<div class="price-item"><div class="price-label">输出</div><div class="price-value output">' + outputCost + '</div></div>';
      html += '</div>';
      html += '<div class="model-score-row">';
      html += '<div><div class="model-score-label">综合性能分</div><div class="model-date">' + (m.releasedAt || '') + '</div></div>';
      html += '<div class="model-score">' + (m.score != null ? m.score : '—') + '</div>';
      html += '</div>';
      html += '</article>';
    });

    grid.innerHTML = html;
  }

  function formatPrice(p) {
    if (p >= 1) return p.toFixed(2);
    if (p >= 0.01) return p.toFixed(3);
    return p.toFixed(4);
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
