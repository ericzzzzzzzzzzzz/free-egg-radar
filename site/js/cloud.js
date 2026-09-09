/* FreeEgg Radar 云主机榜逻辑 */
(function () {
  'use strict';

  var state = {
    data: null,
    plans: [],
    filtered: [],
    activeType: 'all',
    activeRegion: 'all',
    sortBy: 'score',
    search: ''
  };

  var grid = document.getElementById('cloud-grid');
  var typeFilters = document.getElementById('type-filters');
  var regionFilters = document.getElementById('region-filters');
  var searchInput = document.getElementById('cloud-filter-q');
  var updatedAt = document.getElementById('cloud-updated-at');

  function init() {
    loadData();
    bindEvents();
  }

  function loadData() {
    fetch('data/clouds.json')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        state.data = data;
        state.plans = flattenPlans(data);
        state.filtered = state.plans.slice();
        sortPlans();  // 初始按综合分排序

        if (updatedAt && data.version) {
          updatedAt.textContent = '数据更新：' + data.version + ' · ' + data.vendorCount + ' 家厂商 · ' + data.planCount + ' 个套餐 · 每日自动更新';
        }

        render();
      })
      .catch(function (err) {
        console.error('加载云主机数据失败:', err);
        if (grid) grid.innerHTML = '<div class="empty">数据加载失败，请稍后重试</div>';
      });
  }

  function flattenPlans(data) {
    var plans = [];
    (data.clouds || []).forEach(function (cloud) {
      var vendor = cloud.vendor || '未知';
      var vendorEn = cloud.vendor_en || '';
      var region = cloud.region || '';
      var isOverseas = /全球|香港|东南亚|欧美|亚太|海外/i.test(region) && !/中国大陆/.test(region);
      (cloud.plans || []).forEach(function (plan) {
        var p = plan || {};
        p.vendor = vendor;
        p.vendor_en = vendorEn;
        p.region = region;
        p.regionGroup = isOverseas ? '海外' : '国内';
        p.isFree = p.category === 'free_forever' || p.category === 'free_tier' || p.category === 'free_trial';
        plans.push(p);
      });
    });
    return plans;
  }

  function bindEvents() {
    if (typeFilters) {
      typeFilters.addEventListener('click', function (e) {
        var btn = e.target.closest('.chip');
        if (!btn) return;
        state.activeType = btn.getAttribute('data-type');
        typeFilters.querySelectorAll('.chip').forEach(function (c) {
          c.classList.toggle('active', c.getAttribute('data-type') === state.activeType);
        });
        applyFilters();
      });
    }

    if (regionFilters) {
      regionFilters.addEventListener('click', function (e) {
        var btn = e.target.closest('.chip');
        if (!btn) return;
        state.activeRegion = btn.getAttribute('data-region');
        regionFilters.querySelectorAll('.chip').forEach(function (c) {
          c.classList.toggle('active', c.getAttribute('data-region') === state.activeRegion);
        });
        applyFilters();
      });
    }

    var sortButtons = document.querySelectorAll('[data-sort]');
    sortButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.sortBy = btn.getAttribute('data-sort');
        sortButtons.forEach(function (c) {
          c.classList.toggle('active', c.getAttribute('data-sort') === state.sortBy);
        });
        applyFilters();
      });
    });

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
    var type = state.activeType;
    var region = state.activeRegion;
    var q = state.search;

    state.filtered = state.plans.filter(function (p) {
      if (type === 'free' && !p.isFree) return false;
      if (type === 'deal' && p.category !== 'deal') return false;
      if (region !== 'all' && p.regionGroup !== region) return false;
      if (q) {
        var haystack = ((p.vendor || '') + ' ' + (p.name || '') + ' ' + (p.config || '') + ' ' + (p.trial || '')).toLowerCase();
        if (haystack.indexOf(q) === -1) return false;
      }
      return true;
    });

    sortPlans();
    render();
  }

  function sortPlans() {
    var by = state.sortBy;
    state.filtered.sort(function (a, b) {
      if (by === 'price') {
        var pa = a.price_year != null ? a.price_year : 99999;
        var pb = b.price_year != null ? b.price_year : 99999;
        return pa - pb;
      }
      if (by === 'free') {
        var fb = scoreFreeWeight(b) - scoreFreeWeight(a);
        if (fb !== 0) return fb;
        return (b.score || 0) - (a.score || 0);
      }
      return (b.score || 0) - (a.score || 0);
    });
  }

  function scoreFreeWeight(p) {
    if (p.category === 'free_forever') return 100;
    if (p.category === 'free_tier') return 90;
    if (p.category === 'free_trial') return 70;
    return 20;
  }

  function render() {
    if (!grid) return;

    if (state.filtered.length === 0) {
      grid.innerHTML = '<div class="empty">没有找到匹配的云主机</div>';
      return;
    }

    var html = '';
    state.filtered.forEach(function (p, i) {
      var rankClass = '';
      if (i === 0) rankClass = ' top1';
      else if (i === 1) rankClass = ' top2';
      else if (i === 2) rankClass = ' top3';

      // 价格显示
      var priceHtml;
      if (p.category === 'free_forever' || p.category === 'free_tier' || (p.price_year === 0)) {
        priceHtml = '<div class="cloud-price-item"><div class="cloud-price-label">年付</div><div class="cloud-price-value free">免费</div></div>';
      } else if (p.price_year != null) {
        priceHtml = '<div class="cloud-price-item"><div class="cloud-price-label">年付</div><div class="cloud-price-value">' + p.price_year + ' 元</div></div>';
      } else {
        priceHtml = '<div class="cloud-price-item"><div class="cloud-price-label">年付</div><div class="cloud-price-value na">待查</div></div>';
      }

      // 月付（有价格时折算）
      if (p.price_year != null && p.price_year > 0) {
        priceHtml += '<div class="cloud-price-item"><div class="cloud-price-label">月均</div><div class="cloud-price-value">' + (p.price_year / 12).toFixed(1) + ' 元</div></div>';
      } else {
        priceHtml += '<div class="cloud-price-item"><div class="cloud-price-label">月均</div><div class="cloud-price-value na">—</div></div>';
      }

      // 标签
      var tags = '<span class="cloud-tag ' + tagClass(p.category) + '">' + escapeHtml(p.freeTag || '') + '</span>';
      if (p.regionGroup) {
        tags += '<span class="cloud-tag info">' + escapeHtml(p.regionGroup) + '</span>';
      }

      // 详情行
      var details = '';
      if (p.trial) details += '<div><strong>赠送/试用：</strong>' + escapeHtml(p.trial) + '</div>';
      if (p.verify) details += '<div><strong>门槛：</strong>' + escapeHtml(p.verify) + '</div>';
      if (p.renewal) details += '<div><strong>续费：</strong>' + escapeHtml(p.renewal) + '</div>';

      // 评分明细
      var breakdown = p.scoreBreakdown || {};
      var detailHint = '免费' + Math.round(breakdown.free || 0) + ' · 价格' + Math.round(breakdown.price || 0) + ' · 配置' + Math.round(breakdown.config || 0) + ' · 门槛' + Math.round(breakdown.threshold || 0) + ' · 续费' + Math.round(breakdown.renewal || 0);

      html += '<article class="cloud-card' + rankClass + '" style="animation-delay:' + (i * 0.03) + 's">';
      html += '<div class="cloud-rank">' + (i + 1) + '</div>';
      html += '<div class="cloud-vendor">' + escapeHtml(p.vendor) + (p.vendor_en ? ' <span style="color:var(--text-faint);font-weight:400;font-size:11px;">' + escapeHtml(p.vendor_en) + '</span>' : '') + '</div>';
      html += '<div class="cloud-plan">' + escapeHtml(p.name || '') + '</div>';
      if (p.config && p.config !== '待补充') html += '<div class="cloud-config">' + escapeHtml(p.config) + '</div>';
      html += '<div class="cloud-tags">' + tags + '</div>';
      html += '<div class="cloud-price-row">' + priceHtml + '</div>';
      if (details) html += '<div class="cloud-detail">' + details + '</div>';
      html += '<div class="cloud-score-row">';
      html += '<div><div class="cloud-score-label">综合评分</div><div style="font-size:10px;color:var(--text-faint);margin-top:2px;">' + detailHint + '</div></div>';
      html += '<div class="cloud-score">' + (p.score != null ? p.score : '—') + '</div>';
      html += '</div>';
      if (p.url) html += '<a class="cloud-link" href="' + escapeHtml(p.url) + '" target="_blank" rel="noopener noreferrer">查看官方活动 →</a>';
      html += '</article>';
    });

    grid.innerHTML = html;
  }

  function tagClass(cat) {
    if (cat === 'free_forever') return 'free-forever';
    if (cat === 'free_tier') return 'free-tier';
    if (cat === 'free_trial') return 'free-trial';
    if (cat === 'deal') return 'deal';
    return 'info';
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
