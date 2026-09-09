/* FreeEgg Radar 云电脑榜逻辑 v20 */
(function () {
  'use strict';

  var state = {
    data: null,
    plans: [],
    filtered: [],
    activeType: 'all',
    activeFree: 'all',
    sortBy: 'score',
    search: ''
  };

  var grid = document.getElementById('cloudpc-grid');
  var typeFilters = document.getElementById('type-filters');
  var freeFilters = document.getElementById('free-filters');
  var searchInput = document.getElementById('cloudpc-filter-q');
  var updatedAt = document.getElementById('cloudpc-updated-at');

  function init() {
    loadData();
    bindEvents();
  }

  function loadData() {
    fetch('data/cloudpcs.json')
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
        console.error('加载云电脑数据失败:', err);
        if (grid) grid.innerHTML = '<div class="empty">数据加载失败，请稍后重试</div>';
      });
  }

  function flattenPlans(data) {
    var plans = [];
    (data.clouds || []).forEach(function (cloud) {
      var vendor = cloud.vendor || '未知';
      var vendorEn = cloud.vendor_en || '';
      var category = cloud.category || '';
      var categoryLabel = cloud.categoryLabel || (category === 'consumer' ? '消费级云电脑' : '企业级云桌面');
      (cloud.plans || []).forEach(function (plan) {
        var p = plan || {};
        p.vendor = vendor;
        p.vendor_en = vendorEn;
        p.categoryGroup = category;
        p.categoryLabel = categoryLabel;
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

    if (freeFilters) {
      freeFilters.addEventListener('click', function (e) {
        var btn = e.target.closest('.chip');
        if (!btn) return;
        state.activeFree = btn.getAttribute('data-free');
        freeFilters.querySelectorAll('.chip').forEach(function (c) {
          c.classList.toggle('active', c.getAttribute('data-free') === state.activeFree);
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
    var free = state.activeFree;
    var q = state.search;

    state.filtered = state.plans.filter(function (p) {
      if (type !== 'all' && p.categoryGroup !== type) return false;
      if (free === 'free' && !p.isFree) return false;
      if (free === 'deal' && p.category !== 'deal') return false;
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
        var pa = a.price_month != null ? a.price_month : 99999;
        var pb = b.price_month != null ? b.price_month : 99999;
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
    var b = p.scoreBreakdown || {};
    return b.free || 0;
  }

  function render() {
    if (!grid) return;

    if (state.filtered.length === 0) {
      grid.innerHTML = '<div class="empty">没有找到匹配的云电脑</div>';
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
      if (p.category === 'free_forever' || p.category === 'free_tier' || p.price_month === 0) {
        priceHtml = '<div class="cloudpc-price-item"><div class="cloudpc-price-label">月费</div><div class="cloudpc-price-value free">免费</div></div>';
      } else if (p.price_month != null) {
        priceHtml = '<div class="cloudpc-price-item"><div class="cloudpc-price-label">月费</div><div class="cloudpc-price-value">' + p.price_month + ' 元</div></div>';
      } else {
        priceHtml = '<div class="cloudpc-price-item"><div class="cloudpc-price-label">月费</div><div class="cloudpc-price-value na">待查</div></div>';
      }

      // 免费时长
      if (p.free_hours != null && p.free_hours > 0) {
        var freeText = p.free_hours % 1 === 0 ? p.free_hours + ' 小时' : (p.free_hours * 60) + ' 分钟';
        if (p.trial_days >= 300) freeText = '每天 ' + (p.free_hours % 1 === 0 ? p.free_hours + ' 小时' : (p.free_hours * 60) + ' 分钟');
        priceHtml += '<div class="cloudpc-price-item"><div class="cloudpc-price-label">免费时长</div><div class="cloudpc-price-value free">' + freeText + '</div></div>';
      } else {
        priceHtml += '<div class="cloudpc-price-item"><div class="cloudpc-price-label">免费时长</div><div class="cloudpc-price-value na">—</div></div>';
      }

      // 标签
      var tags = '<span class="cloudpc-tag ' + tagClass(p.category) + '">' + escapeHtml(p.freeTag || '') + '</span>';
      tags += '<span class="cloudpc-tag info">' + escapeHtml(p.categoryLabel) + '</span>';

      // 详情行
      var details = '';
      if (p.trial) details += '<div><strong>免费/试用：</strong>' + escapeHtml(p.trial) + '</div>';
      if (p.verify) details += '<div><strong>门槛：</strong>' + escapeHtml(p.verify) + '</div>';
      if (p.renewal) details += '<div><strong>续费/长期：</strong>' + escapeHtml(p.renewal) + '</div>';
      if (p.office) details += '<div><strong>办公适配：</strong>' + escapeHtml(p.office) + '</div>';

      // 评分明细
      var breakdown = p.scoreBreakdown || {};
      var detailHint = '免费' + Math.round(breakdown.free || 0) + ' · 价格' + Math.round(breakdown.price || 0) + ' · 配置' + Math.round(breakdown.config || 0) + ' · 门槛' + Math.round(breakdown.threshold || 0) + ' · 办公' + Math.round(breakdown.office || 0);

      html += '<article class="cloudpc-card' + rankClass + '" style="animation-delay:' + (i * 0.03) + 's">';
      html += '<div class="cloudpc-rank">' + (i + 1) + '</div>';
      html += '<div class="cloudpc-vendor">' + escapeHtml(p.vendor) + (p.vendor_en ? ' <span style="color:var(--text-faint);font-weight:400;font-size:11px;">' + escapeHtml(p.vendor_en) + '</span>' : '') + '</div>';
      html += '<div class="cloudpc-plan">' + escapeHtml(p.name || '') + '</div>';
      if (p.config) html += '<div class="cloudpc-config">' + escapeHtml(p.config) + '</div>';
      html += '<div class="cloudpc-tags">' + tags + '</div>';
      html += '<div class="cloudpc-price-row">' + priceHtml + '</div>';
      if (details) html += '<div class="cloudpc-detail">' + details + '</div>';
      html += '<div class="cloudpc-score-row">';
      html += '<div><div class="cloudpc-score-label">综合评分</div><div style="font-size:10px;color:var(--text-faint);margin-top:2px;">' + detailHint + '</div></div>';
      html += '<div class="cloudpc-score">' + (p.score != null ? p.score : '—') + '</div>';
      html += '</div>';
      if (p.url) html += '<a class="cloudpc-link" href="' + escapeHtml(p.url) + '" target="_blank" rel="noopener noreferrer">查看官方页面 →</a>';
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
