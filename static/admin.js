/* Nuôi Em · admin dashboard
 *
 * No inline handlers and no inline styles: the server sends
 * `script-src 'self'; style-src 'self'`, so every listener is attached here and
 * bar widths come from prebuilt classes.
 *
 * Routing is hash-based (`#/queue/inbound_no_code?year=2023`) so the whole app
 * stays one file and a filtered view can be pasted into a chat as a link.
 */

(function () {
  "use strict";

  var nf = new Intl.NumberFormat("vi-VN");

  var state = {
    summary: null,
    queue: null,
    meta: null,
    audit: null,
    bucket: "inbound_no_code",
    year: "",
    rows: [],
    cursor: null,
    total: 0,
    hasMore: false,
    loading: false
  };

  var BUCKET_ORDER = ["inbound_no_code", "code_no_profile", "outbound_unclassified"];

  var BUCKET_HINT = {
    inbound_no_code: "Tiền vào mà nội dung chuyển khoản không chứa mã NE nào.",
    code_no_profile: "Mã đã nhận tiền nhưng chưa gắn với học sinh hoặc trường.",
    outbound_unclassified: "Tiền ra chưa nối với đề nghị thanh toán của trường."
  };

  var SEVERITY_ORDER = ["high", "medium", "low", "info"];
  var SEVERITY_LABEL = { high: "Nghiêm trọng", medium: "Trung bình", low: "Thấp", info: "Thông tin" };

  // ------------------------------------------------------------- formatting

  function money(value) {
    if (value === null || value === undefined) return "—";
    return nf.format(Math.round(value)) + " đ";
  }

  function compact(value) {
    if (!value) return "0 đ";
    if (value >= 1e9) return (value / 1e9).toFixed(1).replace(".", ",") + " tỷ";
    if (value >= 1e6) return (value / 1e6).toFixed(0) + " tr";
    return nf.format(Math.round(value)) + " đ";
  }

  function num(value) {
    return value === null || value === undefined ? "—" : nf.format(value);
  }

  function pct(value) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return value.toFixed(1).replace(".", ",") + "%";
  }

  // Rounded to a 5% step so the fill's width comes from a prebuilt `.w-NN`
  // class, never a `style=""` attribute — `style-src 'self'` drops those.
  function widthStep(value, max) {
    if (!value || value <= 0 || !max) return 0;
    return Math.max(5, Math.round((value / max) * 20) * 5);
  }

  function date(value) {
    if (!value) return "—";
    return String(value).slice(0, 10).split("-").reverse().join("/");
  }

  function esc(text) {
    return String(text === null || text === undefined ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function el(id) { return document.getElementById(id); }

  function getJSON(url) {
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      });
  }

  var POLICY_LABEL = {
    single_code: "một mã",
    equal_split: "chia đều",
    equal_split_with_remainder: "chia đều, dư 1đ"
  };
  var MATCH_LABEL = { ambiguous: "chưa xác định", matched: "đã khớp", unmatched: "chưa khớp" };
  var STATUS_LABEL = {
    needs_review: "chờ xem lại",
    parsed: "đã tách mã",
    matched: "đã khớp",
    unclassified: "chưa phân loại"
  };

  function label(map, value) { return map[value] || value || "—"; }

  // ------------------------------------------------------------------ boot

  function loadCore() {
    return Promise.all([
      getJSON("/api/summary"),
      getJSON("/api/admin/queue"),
      getJSON("/api/metadata"),
      getJSON("/api/audit?limit=1")
    ]).then(function (results) {
      state.summary = results[0];
      state.queue = results[1];
      state.meta = results[2];
      state.audit = results[3];
      renderOverview();
      fillSelectors();
    });
  }

  // -------------------------------------------------------------- overview

  function renderOverview() {
    var byKey = {};
    (state.queue.buckets || []).forEach(function (bucket) { byKey[bucket.key] = bucket; });
    var noCode = byKey.inbound_no_code || { count: 0, amount: 0 };
    var orphan = byKey.code_no_profile || { count: 0, amount: 0 };
    var coverage = state.summary.coverage || {};
    var balanced = state.summary.integrity && state.summary.integrity.balanced;

    var cards = [
      { label: "Dòng vào chưa gán mã", value: num(noCode.count),
        note: compact(noCode.amount) + " đang bị ảnh hưởng", cls: "risk" },
      { label: "Mã có tiền, chưa có hồ sơ", value: num(orphan.count),
        note: compact(orphan.amount) + " đã phân bổ" },
      { label: "Độ phủ tiền vào",
        value: (coverage.allocated_percent || 0).toFixed(2).replace(".", ",") + "%",
        note: "trên tổng " + compact(coverage.inbound_total) + " tiền vào" },
      { label: "Phần chia khớp tổng", value: balanced ? "Khớp" : "Lệch",
        note: balanced ? "phân bổ = giao dịch liên kết" : "cần kiểm tra lại",
        cls: balanced ? "ok" : "risk" }
    ];

    el("metrics").innerHTML = cards.map(function (card) {
      return '<div class="metric ' + (card.cls || "") + '">' +
        '<p class="label">' + esc(card.label) + "</p>" +
        '<p class="value">' + esc(card.value) + "</p>" +
        '<p class="note">' + esc(card.note) + "</p></div>";
    }).join("");

    // Sorted by row count, not by money: the queue is a list of work to get
    // through, and "most rows first" is the order a person would work in.
    el("queue-list").innerHTML = (state.queue.buckets || []).slice()
      .sort(function (a, b) { return b.count - a.count; })
      .map(function (bucket) {
      return '<button type="button" class="bucket" data-bucket="' + esc(bucket.key) + '">' +
        '<span class="name">' + esc(bucket.label) + "</span>" +
        '<span class="amount">' + esc(compact(bucket.amount)) + "</span>" +
        '<span class="meta"><span class="count">' + esc(num(bucket.count)) + " dòng</span>" +
        "<span>" + esc(bucket.action) + "</span></span>" +
        "</button>";
    }).join("");

    renderStatus();
    renderFlow();
    renderSeverity();
    renderYears(state.queue.unmapped_by_year);
  }

  // One row = one ratio against `total` (the SAME total for every row in a
  // group), aligned bars: a Meter list, not an independent chart per row.
  function meterRow(label, amount, total) {
    var ratio = total > 0 ? amount / total : 0;
    return '<div class="meter-row">' +
      '<div class="meter-top"><span class="label">' + esc(label) + "</span>" +
      '<span class="pct">' + esc(pct(ratio * 100)) + "</span></div>" +
      '<span class="year-track"><span class="year-fill w-' +
        widthStep(amount, total) + '"></span></span>' +
      '<p class="meter-note">' + esc(compact(amount)) + " / " + esc(compact(total)) + "</p>" +
      "</div>";
  }

  function renderFlow() {
    var byKey = {};
    (state.queue.buckets || []).forEach(function (bucket) { byKey[bucket.key] = bucket; });
    var coverage = state.summary.coverage || {};
    var noProfileAmount = (byKey.code_no_profile || {}).amount || 0;
    var unclassifiedAmount = (byKey.outbound_unclassified || {}).amount || 0;

    var inboundTotal = coverage.inbound_total || 0;
    // Same unit as `noProfileAmount` (both sum `allocated_amount_computed`),
    // so the subtraction below is apples-to-apples — see the comment on
    // `allocated_total` in admin_queue_payload.
    var allocatedTotal = state.queue.allocated_total || 0;
    var hasProfileAmount = Math.max(0, allocatedTotal - noProfileAmount);

    var outbound = (state.summary.transactions || {}).outbound || {};
    var outboundTotal = outbound.total || 0;
    var classifiedAmount = Math.max(0, outboundTotal - unclassifiedAmount);

    el("flow-in").innerHTML =
      '<p class="meter-note heading">Tiền vào · tổng ' + esc(compact(inboundTotal)) + "</p>" +
      meterRow("Đã gán mã NE", allocatedTotal, inboundTotal) +
      meterRow("— trong đó, mã có hồ sơ học sinh", hasProfileAmount, inboundTotal);

    el("flow-out").innerHTML =
      '<p class="meter-note heading">Tiền ra · tổng ' + esc(compact(outboundTotal)) + "</p>" +
      meterRow("Đã phân loại kế toán", classifiedAmount, outboundTotal);
  }

  function renderSeverity() {
    var rows = state.queue.exceptions_by_severity || [];
    var byKey = {};
    rows.forEach(function (row) { byKey[row.severity] = row.count; });
    var max = SEVERITY_ORDER.reduce(function (best, key) {
      return Math.max(best, byKey[key] || 0);
    }, 1);

    el("severity").innerHTML = SEVERITY_ORDER.map(function (key) {
      var count = byKey[key] || 0;
      return '<div class="sev-row"><span class="sev-name"><span class="sev-dot ' + key +
        '"></span>' + esc(SEVERITY_LABEL[key]) + "</span>" +
        '<span class="sev-track"><span class="sev-fill ' + key + " w-" +
          widthStep(count, max) + '"></span></span>' +
        '<span class="n">' + esc(num(count)) + "</span></div>";
    }).join("");
  }

  function renderStatus() {
    var source = state.meta.source || {};
    var period = state.summary.period || {};
    var rows = [
      ["Lần import gần nhất", source.source_name ? esc(source.source_name) : "—"],
      ["Thời điểm nạp", source.imported_at ? esc(date(source.imported_at)) : "—"],
      ["Đã nạp", source.raw_transaction_rows
        ? num(source.raw_transaction_rows) + " giao dịch · " + num(source.allocation_rows) + " phân bổ"
        : "—"],
      ["Khoảng dữ liệu", period.from ? date(period.from) + " → " + date(period.to) : "—"],
      ["Chuỗi audit", state.audit.chain_intact
        ? '<span class="badge ok">toàn vẹn</span>'
        : '<span class="badge risk">đứt tại #' + esc(state.audit.first_broken_event_id) + "</span>"]
    ];

    el("status").innerHTML = rows.map(function (row) {
      return '<div class="status-row"><span class="k">' + esc(row[0]) +
        '</span><span class="v">' + row[1] + "</span></div>";
    }).join("");
  }

  // ------------------------------------------------------------ years chart
  //
  // A real bar chart (gridlines, axis ticks, hover/focus tooltip) instead of
  // the old plain bar list. Every number it draws comes from SVG geometry
  // attributes (x/y/width/height/d), set directly — never a `style=""`
  // attribute, which `style-src 'self'` silently drops.

  function niceMax(value) {
    if (value <= 0) return 1;
    var mag = Math.pow(10, Math.floor(Math.log(value) / Math.LN10));
    var steps = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < steps.length; i++) {
      var candidate = steps[i] * mag;
      if (candidate >= value) return candidate;
    }
    return 10 * mag;
  }

  // A rect with only its top two corners rounded (a plain `rx` rounds all
  // four, which would un-square the baseline — see marks-and-anatomy.md).
  function roundedTopRectPath(x, y, w, h, r) {
    if (h <= 0 || w <= 0) return "";
    r = Math.min(r, w / 2, h);
    return "M" + x + "," + (y + r) +
      " Q" + x + "," + y + " " + (x + r) + "," + y +
      " H" + (x + w - r) +
      " Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) +
      " V" + (y + h) +
      " H" + x + " Z";
  }

  var YEARS_MARGIN = { top: 14, right: 16, bottom: 24, left: 50 };
  var YEARS_PLOT_H = 130;

  // Bars stay <= 24px thick (never fill the slot — marks-and-anatomy.md) no
  // matter how wide the card is; leftover room becomes air between bars
  // (more gap), not fatter bars. Few bars in a wide card centers instead of
  // stretching corner to corner.
  function yearsBarLayout(n, availableW) {
    var maxBarW = 24, minBarW = 6, minGap = 10, maxGap = 56;
    var barW = maxBarW;
    var gap = n > 1 ? (availableW - n * barW) / (n - 1) : 0;
    if (gap < minGap) {
      gap = minGap;
      barW = Math.max(minBarW, (availableW - (n - 1) * gap) / n);
    } else if (gap > maxGap) {
      gap = maxGap;
    }
    var innerW = n * barW + (n - 1) * gap;
    var offset = Math.max(0, (availableW - innerW) / 2);
    return { barW: barW, gap: gap, innerW: innerW, offset: offset };
  }

  function renderYears(rows) {
    if (!rows || !rows.length) {
      el("years").innerHTML = '<p class="empty">Chưa có dòng nào.</p>';
      return;
    }
    var m = YEARS_MARGIN;
    var plotH = YEARS_PLOT_H;
    var containerW = el("years").clientWidth || 600;
    var availableW = Math.max(120, containerW - m.left - m.right);
    var layout = yearsBarLayout(rows.length, availableW);
    var barW = layout.barW, gap = layout.gap;
    var startX = m.left + layout.offset;
    var width = containerW;
    var height = m.top + plotH + m.bottom;
    var gridEndX = startX + layout.innerW;

    var maxCount = rows.reduce(function (best, row) { return Math.max(best, row.count); }, 0);
    var top = niceMax(maxCount || 1);
    var ticks = [0, top / 2, top];

    var grid = ticks.map(function (tick) {
      var y = m.top + plotH - (tick / top) * plotH;
      return '<line class="chart-grid" x1="' + m.left + '" x2="' + gridEndX.toFixed(1) +
        '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" />' +
        '<text class="chart-axis-y" x="' + (m.left - 8) + '" y="' + (y + 3.5).toFixed(1) +
        '" text-anchor="end">' + esc(num(Math.round(tick))) + "</text>";
    }).join("");

    var bars = rows.map(function (row, i) {
      var x = startX + i * (barW + gap);
      var h = top > 0 ? (row.count / top) * plotH : 0;
      var y = m.top + plotH - h;
      var cx = x + barW / 2;
      var hitX = x - gap / 2;
      var hitW = barW + gap;
      var label = "Năm " + row.year + ": " + num(row.count) + " dòng, " + compact(row.amount);
      return '<g class="chart-bar-hit" tabindex="0" role="img" aria-label="' + esc(label) + '"' +
        ' data-year="' + esc(row.year) + '" data-count="' + esc(num(row.count)) +
        '" data-amount="' + esc(compact(row.amount)) + '" data-cx="' + cx.toFixed(1) +
        '" data-top="' + y.toFixed(1) + '">' +
        '<rect class="chart-bar-hitarea" x="' + hitX.toFixed(1) + '" y="' + m.top +
          '" width="' + hitW.toFixed(1) + '" height="' + plotH + '" />' +
        '<path class="chart-bar" d="' + roundedTopRectPath(x, y, barW, h, 4) + '" />' +
        "<title>" + esc(label) + "</title>" +
        '<text class="chart-axis-x" x="' + cx.toFixed(1) + '" y="' + (m.top + plotH + 17) +
          '" text-anchor="middle">' + esc(row.year) + "</text>" +
        "</g>";
    }).join("");

    el("years").innerHTML =
      '<svg viewBox="0 0 ' + width + " " + height + '" width="' + width + '" height="' + height +
      '" role="group" aria-label="Tiền vào chưa gán mã, theo năm">' +
      grid + bars +
      '<g class="chart-tooltip" id="years-tip" aria-hidden="true">' +
        '<rect x="0" y="0" width="90" height="38" rx="6"></rect>' +
        '<text class="tt-value" id="years-tip-value" x="9" y="16"></text>' +
        '<text class="tt-sub" id="years-tip-sub" x="9" y="30"></text>' +
      "</g>" +
      "</svg>";
  }

  function showYearsTooltip(group) {
    var svg = group.closest("svg");
    var tip = el("years-tip");
    if (!svg || !tip) return;
    var valueText = el("years-tip-value");
    var subText = el("years-tip-sub");
    valueText.textContent = group.getAttribute("data-amount");
    subText.textContent = group.getAttribute("data-year") + " · " + group.getAttribute("data-count") + " dòng";

    // Size the chip to the text actually rendered (accurate, no guessing at
    // character widths) rather than a fixed box that either clips or floats.
    var padX = 9, padTop = 11, padBottom = 9, lineGap = 14;
    var w = Math.max(valueText.getBBox().width, subText.getBBox().width) + padX * 2;
    var h = padTop + lineGap + padBottom;
    var rect = tip.querySelector("rect");
    rect.setAttribute("width", w.toFixed(1));
    rect.setAttribute("height", h.toFixed(1));
    valueText.setAttribute("x", padX);
    subText.setAttribute("x", padX);

    var cx = parseFloat(group.getAttribute("data-cx"));
    var top = parseFloat(group.getAttribute("data-top"));
    var svgWidth = parseFloat(svg.getAttribute("viewBox").split(" ")[2]);
    var tx = Math.min(Math.max(cx - w / 2, 2), svgWidth - w - 2);
    var ty = Math.max(top - h - 8, 2);
    tip.setAttribute("transform", "translate(" + tx.toFixed(1) + "," + ty.toFixed(1) + ")");
    tip.classList.add("show");
  }

  function hideYearsTooltip() {
    var tip = el("years-tip");
    if (tip) tip.classList.remove("show");
  }

  // --------------------------------------------------------------- filters

  function fillSelectors() {
    var buckets = (state.queue.buckets || []).slice().sort(function (a, b) {
      return BUCKET_ORDER.indexOf(a.key) - BUCKET_ORDER.indexOf(b.key);
    });
    el("bucket-select").innerHTML = buckets.map(function (bucket) {
      return '<option value="' + esc(bucket.key) + '">' + esc(bucket.label) +
        " (" + esc(num(bucket.count)) + ")</option>";
    }).join("");

    var years = (state.queue.unmapped_by_year || []).map(function (row) { return row.year; });
    el("year-select").innerHTML = '<option value="">Tất cả</option>' +
      years.map(function (year) {
        return '<option value="' + esc(year) + '">' + esc(year) + "</option>";
      }).join("");
  }

  // ----------------------------------------------------------------- queue

  function renderQueueRoute(bucket, year, append) {
    if (!append) {
      state.bucket = bucket;
      state.year = year || "";
      state.rows = [];
      state.cursor = null;
    }
    el("bucket-select").value = state.bucket;
    el("year-select").value = state.year;
    // A code spans several years, so a year filter would silently mean
    // "codes that had activity in that year" — a different question.
    el("year-field").hidden = state.bucket === "code_no_profile";

    var params = ["bucket=" + encodeURIComponent(state.bucket), "limit=25"];
    if (state.year) params.push("year=" + encodeURIComponent(state.year));
    if (append && state.cursor) params.push("cursor=" + encodeURIComponent(state.cursor));

    el("more-btn").disabled = true;
    getJSON("/api/admin/rows?" + params.join("&"))
      .then(function (payload) {
        state.total = payload.total;
        state.hasMore = payload.has_more;
        state.cursor = payload.next_cursor;
        state.rows = append ? state.rows.concat(payload.items) : payload.items;
        state.kind = payload.kind;
        paintQueue();
      })
      .catch(function (error) {
        el("queue-body").innerHTML = '<tr><td colspan="4" class="muted">Không tải được: ' +
          esc(error.message) + "</td></tr>";
      })
      .then(function () { el("more-btn").disabled = false; });
  }

  function paintQueue() {
    var isCodes = state.kind === "codes";
    // Tagged so the stylesheet can drop the column that carries no information
    // at phone width instead of making the table scroll sideways.
    el("queue-table").dataset.mode = isCodes ? "codes" : "tx";

    el("queue-head").innerHTML = isCodes
      ? "<tr><th>Mã NE</th><th class=\"num\">Số dòng</th><th class=\"num\">Tổng đã nhận</th><th></th></tr>"
      : "<tr><th>Ngày</th><th class=\"num\">Số tiền</th><th>Mã giao dịch</th><th>Trạng thái</th></tr>";

    el("queue-body").innerHTML = state.rows.map(function (row) {
      if (isCodes) {
        return '<tr class="clickable" data-code="' + esc(row.ne_code) + '">' +
          '<td class="mono">' + esc(row.ne_code) + "</td>" +
          '<td class="num">' + esc(num(row.rows)) + "</td>" +
          '<td class="num">' + esc(money(row.total)) + "</td>" +
          '<td class="muted">xem →</td></tr>';
      }
      // A transaction row is deliberately not clickable. There is no write API
      // and no code-issuing table, so the only thing a click could reveal is
      // that nothing can be done — which is worse than no affordance at all.
      return "<tr>" +
        '<td class="mono">' + esc(date(row.tx_time)) + "</td>" +
        '<td class="num">' + esc(money(row.amount)) + "</td>" +
        '<td class="mono muted">' + esc(row.provider_tx_id) + "</td>" +
        "<td>" + esc(label(STATUS_LABEL, row.processing_status)) + "</td></tr>";
    }).join("");

    var shown = state.rows.length;
    // Count only. The sentence explaining the bucket now lives in the page
    // header, and printing it twice made the two lines look like a duplicate.
    el("queue-count").textContent = num(state.total) + " dòng";
    el("queue-range").textContent = shown
      ? "Hiển thị " + num(shown) + " / " + num(state.total)
      : "Không có dòng nào.";
    el("more-btn").hidden = !state.hasMore;
  }

  // ---------------------------------------------------------------- lookup

  function doSearch(rawQuery, silent) {
    var query = (rawQuery || "").trim();
    if (!query) return;
    var hint = el("search-hint");
    hint.className = "hint";
    hint.textContent = "Đang tra…";

    getJSON("/api/admin/search?q=" + encodeURIComponent(query))
      .then(function (found) {
        if (found.kind === "ne") {
          hint.textContent = "Nhận dạng: mã NE";
          return getJSON("/api/ne?ne=" + encodeURIComponent(found.code))
            .then(function (payload) { renderNeResult(payload); });
        }
        if (found.kind === "acn") {
          hint.textContent = "Nhận dạng: mã ACN";
          return renderMessage(found.code,
            "Tra cứu theo mã ACN chưa dùng được: bảng nhà tài trợ đang trống, và mã ACN " +
            "không xuất hiện trong sao kê ngân hàng.");
        }
        if (found.kind === "reference") {
          hint.className = "hint warn";
          hint.textContent = "Số tham chiếu giao dịch";
          return renderMessage(found.code,
            "Số tham chiếu tra theo mã giao dịch ngân hàng, không phải mã NE. " +
            "Dùng bảng công khai để tìm theo số này.");
        }
        hint.className = "hint warn";
        hint.textContent = found.hint || "Không nhận dạng được.";
        el("result").hidden = true;
        return null;
      })
      .catch(function (error) {
        hint.className = "hint warn";
        hint.textContent = "Không tra được: " + error.message;
      });
  }

  var STATUS_BADGE = {
    has_profile: ["ok", "đã có hồ sơ"],
    has_money_no_profile: ["warn", "có tiền, chưa có hồ sơ"],
    unknown_code: ["muted", "không có giao dịch nào"]
  };

  function renderNeResult(payload) {
    var badge = STATUS_BADGE[payload.status] || ["muted", payload.status || "không rõ"];
    var allocations = payload.allocations || [];
    var variants = payload.variants || [];

    var head = '<div class="result-head">' +
      '<span class="result-code">' + esc(payload.ne_code) + "</span>" +
      '<span class="badge ' + badge[0] + '">' + esc(badge[1]) + "</span>" +
      '<span class="result-meta">' + esc(payload.meal_plan || "không rõ") + " · " +
        esc(num(payload.distinct_transactions)) + " giao dịch · " +
        esc(date(payload.first_seen)) + " → " + esc(date(payload.last_seen)) + "</span></div>";

    var variantRow = variants.length
      ? "<dt>Biến thể S/T</dt><dd>" + variants.map(function (variant) {
          return esc(variant.ne_code) + " (" + esc(num(variant.rows)) + " dòng)";
        }).join(", ") + "</dd>"
      : "";

    var blockCode = '<div class="block"><h3>Mã và tình trạng</h3><dl class="kv">' +
      "<dt>Mã</dt><dd>" + esc(payload.ne_code) + "</dd>" +
      "<dt>Suất ăn</dt><dd>" + esc(payload.meal_plan || "không rõ") + "</dd>" +
      "<dt>Số dòng phân bổ</dt><dd>" + esc(num(payload.allocation_count)) + "</dd>" +
      "<dt>Tổng đã nhận</dt><dd>" + esc(money(payload.total_allocated)) + "</dd>" +
      variantRow + "</dl></div>";

    var blockProfile = payload.registry_available
      ? '<div class="block"><h3>Trường và hồ sơ</h3><dl class="kv">' +
          "<dt>Trường</dt><dd>" + esc(payload.registry[0].school_name || "—") + "</dd>" +
          "<dt>Tỉnh</dt><dd>" + esc(payload.registry[0].province || "—") + "</dd>" +
          "<dt>Lớp</dt><dd>" + esc(payload.registry[0].class_name || "—") + "</dd></dl></div>"
      : '<div class="block"><h3>Trường và hồ sơ</h3><div class="empty">' +
          "<strong>Chưa có hồ sơ.</strong> Mã này đã nhận tiền nhưng chưa gắn với học sinh hay " +
          "trường nào. Danh mục học sinh chưa được nhập vào hệ thống, nên đây là trạng thái của " +
          "toàn bộ mã đang có tiền.</div></div>";

    var rows = allocations.slice(0, 8).map(function (row) {
      return "<tr>" +
        '<td class="mono">' + esc(date(row.tx_time)) + "</td>" +
        '<td class="num">' + esc(money(row.allocated_amount_computed)) + "</td>" +
        "<td>" + esc(label(POLICY_LABEL, row.allocation_policy)) + "</td>" +
        "<td>" + esc(label(MATCH_LABEL, row.match_status)) + "</td></tr>";
    }).join("");

    var blockMoney = '<div class="block span"><h3>Dòng tiền nhận được</h3>' +
      (allocations.length
        ? '<table class="data result-table"><thead><tr><th>Ngày</th><th class="num">Số tiền</th>' +
          "<th>Cách chia</th><th>Trạng thái</th></tr></thead><tbody>" + rows + "</tbody></table>" +
          (allocations.length > 8
            ? '<p class="hint">Hiển thị 8 trong ' + esc(num(allocations.length)) + " dòng.</p>"
            : "")
        : '<div class="empty">Mã này không xuất hiện trong giao dịch nào.</div>') + "</div>";

    var blockDonor = '<div class="block"><h3>Nhà tài trợ</h3><div class="empty">' +
      "<strong>Chưa gắn mã ACN.</strong> Mã ACN đến từ chatbot Facebook, không có trong sao kê " +
      "ngân hàng, nên chưa nối được với mã NE.</div></div>";

    el("result").innerHTML = head + '<div class="result-body">' + blockCode + blockProfile +
      blockMoney + blockDonor + "</div>";
    el("result").hidden = false;
  }

  function renderMessage(title, detail) {
    el("result").innerHTML = '<div class="result-head"><span class="result-code">' +
      esc(title) + "</span></div>" +
      '<div class="result-body"><div class="block span"><div class="empty">' +
      esc(detail) + "</div></div></div>";
    el("result").hidden = false;
  }

  // ----------------------------------------------------------------- route

  function parseHash() {
    var raw = (location.hash || "#/overview").replace(/^#\/?/, "");
    var split = raw.split("?");
    var parts = split[0].split("/").filter(Boolean);
    var query = {};
    (split[1] || "").split("&").forEach(function (pair) {
      if (!pair) return;
      var kv = pair.split("=");
      query[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || "");
    });
    return { view: parts[0] || "overview", param: parts[1] || "", query: query };
  }

  function show(view) {
    ["overview", "queue", "lookup", "schema"].forEach(function (name) {
      el("view-" + name).hidden = name !== view;
    });
    Array.prototype.forEach.call(document.querySelectorAll("#nav a"), function (link) {
      link.classList.toggle("active", link.dataset.view === view);
    });
  }

  function route() {
    var current = parseHash();
    show(current.view);

    if (current.view === "queue") {
      var bucket = current.param || state.bucket || "inbound_no_code";
      el("page-title").textContent = bucketTitle(bucket);
      // The action is the reason this page exists, so it belongs in the header
      // and not only on the overview button that got you here.
      el("page-sub").textContent = (BUCKET_HINT[bucket] || "") +
        (bucketField(bucket, "action") ? " · Việc phải làm: " + bucketField(bucket, "action") + "." : "");
      renderQueueRoute(bucket, current.query.year || "", false);
      return;
    }

    if (current.view === "lookup") {
      el("page-title").textContent = "Tra cứu";
      el("page-sub").textContent = "Một mã, mọi thứ hệ thống biết về nó.";
      if (current.query.q) {
        el("q").value = current.query.q;
        doSearch(current.query.q);
      }
      return;
    }

    if (current.view === "schema") {
      el("page-title").textContent = "Sơ đồ CSDL";
      el("page-sub").textContent = "Cấu trúc bảng và luồng dữ liệu, để hiểu hệ thống chạy thế nào.";
      return;
    }

    el("page-title").textContent = "Tổng quan";
    el("page-sub").textContent = "Việc đang chờ xử lý và tình trạng dữ liệu.";
  }

  function bucketField(key, field) {
    var found = (state.queue && state.queue.buckets || []).filter(function (bucket) {
      return bucket.key === key;
    })[0];
    return found ? found[field] : "";
  }

  function bucketTitle(key) {
    return bucketField(key, "label") || "Hàng đợi";
  }

  // ---------------------------------------------------------------- wiring

  function boot() {
    el("search-form").addEventListener("submit", function (event) {
      event.preventDefault();
      var value = el("q").value.trim();
      if (!value) return;
      location.hash = "#/lookup?q=" + encodeURIComponent(value);
    });

    el("queue-list").addEventListener("click", function (event) {
      var button = event.target.closest(".bucket");
      if (button) location.hash = "#/queue/" + button.dataset.bucket;
    });

    el("bucket-select").addEventListener("change", function (event) {
      location.hash = "#/queue/" + event.target.value;
    });

    el("year-select").addEventListener("change", function (event) {
      var suffix = event.target.value ? "?year=" + event.target.value : "";
      location.hash = "#/queue/" + state.bucket + suffix;
    });

    // Only code rows navigate. See the note in renderQueue about why a
    // transaction row is not clickable.
    el("queue-body").addEventListener("click", function (event) {
      var codeCell = event.target.closest("tr[data-code]");
      if (codeCell) {
        location.hash = "#/lookup?q=" + encodeURIComponent(codeCell.dataset.code);
      }
    });

    el("more-btn").addEventListener("click", function () {
      renderQueueRoute(state.bucket, state.year, true);
    });

    // Delegated so the chart can be rebuilt on every render without
    // re-attaching listeners (same pattern as queue-body above). pointerover/
    // pointerout bubble (pointerenter/pointerleave don't), which is what
    // makes delegation possible here.
    el("years").addEventListener("pointerover", function (event) {
      var bar = event.target.closest(".chart-bar-hit");
      if (bar) showYearsTooltip(bar);
    });
    el("years").addEventListener("pointerout", function (event) {
      var bar = event.target.closest(".chart-bar-hit");
      var to = event.relatedTarget && event.relatedTarget.closest
        ? event.relatedTarget.closest(".chart-bar-hit") : null;
      if (bar && to !== bar) hideYearsTooltip();
    });
    el("years").addEventListener("focusin", function (event) {
      var bar = event.target.closest(".chart-bar-hit");
      if (bar) showYearsTooltip(bar);
    });
    el("years").addEventListener("focusout", function (event) {
      var bar = event.target.closest(".chart-bar-hit");
      if (bar) hideYearsTooltip();
    });

    // The chart is laid out to the container's pixel width (see
    // yearsBarLayout), so a width change — the sidebar's 820px breakpoint,
    // a rotated phone — needs a real re-layout, not just CSS scaling.
    var yearsResizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(yearsResizeTimer);
      yearsResizeTimer = setTimeout(function () {
        if (state.queue && state.queue.unmapped_by_year) renderYears(state.queue.unmapped_by_year);
      }, 150);
    });

    window.addEventListener("hashchange", route);

    loadCore().then(function () {
      if (!location.hash) location.hash = "#/overview";
      route();
    }).catch(function (error) {
      el("metrics").innerHTML =
        '<p class="empty">Không tải được dữ liệu: ' + esc(error.message) + "</p>";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
