/* FreeEgg Radar 前端：读取 data/eggs.json 渲染榜单（原生 JS，无依赖） */
(function () {
  "use strict";

  var TIER_LABEL = { gold: "金蛋", silver: "银蛋", copper: "铜蛋" };
  var CAT_LABEL = { token: "Token", credits: "积分", "api-quota": "API 额度", other: "其他" };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function tierOf(score) {
    if (score > 80) return "gold";
    if (score >= 60) return "silver";
    return "copper";
  }

  function countdownText(expiryDate) {
    if (!expiryDate) return null;
    var t = new Date(expiryDate).getTime() - Date.now();
    if (isNaN(t) || t <= 0) return null;
    var day = Math.floor(t / 86400000);
    var hour = Math.floor((t % 86400000) / 3600000);
    if (day > 0) return "剩 " + day + " 天 " + hour + " 小时";
    return "剩 " + Math.max(1, Math.floor(t / 3600000)) + " 小时";
  }

  function eggIcon(tier, size) {
    var colors = {
      gold: { outer: "#e0b64e", inner: "#f5d78e" },
      silver: { outer: "#aab4be", inner: "#d4dae0" },
      copper: { outer: "#d98e63", inner: "#ecc0a0" }
    }[tier] || { outer: "#d98e63", inner: "#ecc0a0" };
    var w = size || 36, h = Math.round(w * 1.375);
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 32 44" aria-hidden="true" style="flex-shrink:0">' +
      '<ellipse cx="16" cy="27" rx="14" ry="16" fill="' + colors.outer + '"/>' +
      '<ellipse cx="16" cy="17" rx="12" ry="14" fill="' + colors.inner + '"/>' +
      '<ellipse cx="12" cy="13" rx="3" ry="4" fill="rgba(255,255,255,0.55)"/></svg>';
  }

  function tagHtml(egg) {
    var d = egg.tags && egg.tags.duration;
    var cls = d === "limited" ? "tag tag-limit" : "tag tag-longterm";
    var label = d === "limited" ? "限时" : "长期";
    var isAuto = egg.source !== "seed" && egg.source !== "manual";
    return '<div class="egg-tags"><span class="' + cls + '">' + label + "</span>" +
      '<span class="tag">' + (CAT_LABEL[egg.category] || "其他") + "</span>" +
      (isAuto ? '<span class="tag tag-auto">自动</span>' : "") + "</div>";
  }

  function cardHtml(egg) {
    var tier = tierOf(egg.score);
    var cd = countdownText(egg.expiry_date);
    return '<article class="egg-card tier-' + tier + '" data-id="' + esc(egg.id) + '" tabindex="0" role="button">' +
      '<div class="egg-head">' + eggIcon(tier, 26) +
      '<span class="egg-vendor">' + esc(egg.vendor) + "</span>" +
      '<span class="egg-tier tier-' + tier + '">' + TIER_LABEL[tier] + "</span></div>" +
      '<h3 class="egg-title">' + esc(egg.title) + "</h3>" +
      '<p class="egg-summary">' + esc(egg.summary) + "</p>" +
      tagHtml(egg) +
      '<div class="egg-meta">' +
      (cd ? '<span class="egg-countdown">' + cd + "</span>" : '<span>长期有效</span>') +
      '<span class="egg-score">' + esc(egg.score) + " 分</span></div>" +
      "</article>";
  }

  function renderCard(egg) {
    return cardHtml(egg);
  }

  function markdown(html) {
    // 轻量安全渲染：先转义，再还原受控语法
    var out = esc(html);
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, label, href) {
      if (!/^(https?:|mailto:)/i.test(href)) return label;
      return '<a href="' + href + '" target="_blank" rel="noopener noreferrer">' + label + "</a>";
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/\n/g, "<br>");
    return out;
  }

  function openDetail(egg) {
    var ov = document.createElement("div");
    ov.className = "modal-overlay";
    ov.setAttribute("role", "dialog");
    ov.innerHTML =
      '<div class="modal">' +
      '<div class="modal-head">' + eggIcon(tierOf(egg.score), 30) +
      '<span class="egg-tier tier-' + tierOf(egg.score) + '">' + TIER_LABEL[tierOf(egg.score)] + "</span>" +
      '<span style="font-size:16px;font-weight:700;color:var(--gold-bright);margin-left:auto">' + esc(egg.score) + " 分</span></div>" +
      '<h2 class="modal-title">' + esc(egg.title) + "</h2>" +
      '<div class="modal-meta">' + esc(egg.vendor) + " · " + (CAT_LABEL[egg.category] || "") +
      " · " + (egg.tags && egg.tags.duration === "limited" ? "限时" : "长期") +
      (egg.expiry_date ? " · 截止 " + esc(String(egg.expiry_date).slice(0, 10)) : "") +
      (egg.published_at ? " · 发布 " + esc(egg.published_at) : "") + "</div>" +
      '<div class="modal-content">' + markdown(egg.content || egg.summary || "") + "</div>" +
      '<div class="modal-actions">' +
      (egg.link ? '<a class="btn" href="' + esc(egg.link) + '" target="_blank" rel="noopener noreferrer">去领取</a>' : "") +
      '<button class="btn btn-ghost" data-close>关闭</button></div>' +
      "</div>";
    ov.addEventListener("click", function (e) {
      if (e.target === ov || (e.target.getAttribute && e.target.getAttribute("data-close") !== null)) ov.remove();
    });
    document.body.appendChild(ov);
  }

  function init() {
    var grid = document.getElementById("egg-grid");
    var ranking = document.getElementById("ranking-list");
    var recycle = document.getElementById("recycle-list");
    var recycleCount = document.getElementById("recycle-count");
    var updatedAt = document.getElementById("updated-at");
    if (!grid || !ranking) return;

    fetch("data/eggs.json")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var eggs = data.eggs || [];
        var expired = data.expired || [];
        var stats = data.stats || {};

        ["gold", "silver", "copper"].forEach(function (k) {
          var el = document.getElementById("stat-" + k);
          if (el) el.textContent = stats[k] || 0;
        });
        if (updatedAt && data.version) {
          updatedAt.textContent = "数据更新：" + String(data.version).slice(0, 16) +
            " · 自动抓取 + 初始种子 · 以官方页面为准";
        }
        if (recycleCount) recycleCount.textContent = expired.length;

        var state = { tier: null, duration: null, category: null, q: "" };

        function applyFilter() {
          var list = eggs.filter(function (e) {
            if (state.tier && tierOf(e.score) !== state.tier) return false;
            if (state.duration && e.tags.duration !== state.duration) return false;
            if (state.category && e.category !== state.category) return false;
            if (state.q) {
              var hay = (e.title + " " + e.vendor + " " + (e.summary || "")).toLowerCase();
              if (hay.indexOf(state.q.toLowerCase()) < 0) return false;
            }
            return true;
          });
          grid.innerHTML = list.map(cardHtml).join("") ||
            '<p class="empty">没有符合条件的蛋，换个筛选项试试</p>';
        }

        // 筛选事件
        document.querySelectorAll("#filter-advanced .chip").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var v = btn.getAttribute("data-v");
            var group = btn.parentElement.getAttribute("aria-label");
            var key = group === "等级筛选" ? "tier" : group === "时限筛选" ? "duration" : "category";
            if (state[key] === v) { state[key] = null; btn.classList.remove("active"); }
            else {
              btn.parentElement.querySelectorAll(".chip").forEach(function (b) { b.classList.remove("active"); });
              state[key] = v; btn.classList.add("active");
            }
            applyFilter();
          });
        });
        var filterToggle = document.getElementById("filter-toggle");
        var filterAdvanced = document.getElementById("filter-advanced");
        if (filterToggle && filterAdvanced) {
          filterToggle.addEventListener("click", function () {
            var open = filterAdvanced.hidden;
            filterAdvanced.hidden = !open;
            filterToggle.setAttribute("aria-expanded", String(open));
            filterToggle.classList.toggle("active", open);
          });
        }
        var q = document.getElementById("filter-q");
        if (q) {
          q.addEventListener("input", function () { state.q = q.value.trim(); applyFilter(); });
        }

        // 排行榜 TOP10
        var top = eggs.slice(0, 10);
        ranking.innerHTML = top.map(function (e, i) {
          var noCls = i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
          return '<div class="rank-item" data-id="' + esc(e.id) + '" tabindex="0" role="button">' +
            '<span class="rank-no ' + noCls + '">' + (i + 1) + "</span>" +
            eggIcon(tierOf(e.score), 22) +
            '<div class="rank-info"><div class="rank-title">' + esc(e.title) + "</div>" +
            '<div class="rank-sub">' + esc(e.vendor) + " · " + TIER_LABEL[tierOf(e.score)] + "</div></div>" +
            '<span class="rank-score">' + esc(e.score) + " 分</span></div>";
        }).join("");

        // 过期蛋
        recycle.innerHTML = expired.map(function (e) {
          return '<article class="egg-card rotten" data-id="' + esc(e.id) + '" tabindex="0" role="button">' +
            '<div class="egg-head">' + eggIcon("copper", 24) +
            '<span class="egg-vendor">' + esc(e.vendor) + "</span>" +
            '<span class="egg-tier tier-copper">过期</span></div>' +
            '<h3 class="egg-title">' + esc(e.title) + "</h3>" +
            '<p class="egg-summary">' + esc(e.summary) + "</p>" +
            '<div class="egg-meta"><span class="egg-rotate">' +
            (e.expiry_date ? "已于 " + esc(String(e.expiry_date).slice(0, 10)) + " 过期" : "已过期") + "</span></div></article>";
        }).join("") || '<p class="empty">暂无过期蛋</p>';

        // 详情点击（事件委托）
        var byId = {};
        eggs.concat(expired).forEach(function (e) { byId[e.id] = e; });
        function onCardClick(target) {
          var card = target.closest ? target.closest("[data-id]") : null;
          if (!card) return;
          var egg = byId[card.getAttribute("data-id")];
          if (egg) openDetail(egg);
        }
        grid.addEventListener("click", function (e) { onCardClick(e.target); });
        ranking.addEventListener("click", function (e) { onCardClick(e.target); });
        recycle.addEventListener("click", function (e) { onCardClick(e.target); });
        [grid, ranking, recycle].forEach(function (box) {
          box.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onCardClick(e.target); }
          });
        });

        applyFilter();
      })
      .catch(function (err) {
        grid.innerHTML = '<p class="empty">数据加载失败：' + esc(err.message) + "。<br>请先在 site 目录运行 <strong>python -m http.server 8899</strong>，再访问 http://127.0.0.1:8899（直接双击打开会受浏览器安全限制）。</p>";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
