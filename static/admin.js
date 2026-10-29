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
    renderYears(state.queue.unmapped_by_year);
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

  function renderYears(rows) {
    if (!rows || !rows.length) {
      el("years").innerHTML = '<p class="empty">Chưa có dòng nào.</p>';
      return;
    }
    var max = rows.reduce(function (best, row) { return Math.max(best, row.count); }, 1);
    el("years").innerHTML = rows.map(function (row) {
      // Rounded to a 5% step so the width comes from a class, not a style
      // attribute — `style-src 'self'` would drop the attribute.
      var step = Math.max(5, Math.round((row.count / max) * 20) * 5);
      return '<div class="year-row"><span class="yr">' + esc(row.year) + "</span>" +
        '<span class="year-track"><span class="year-fill w-' + step + '"></span></span>' +
        '<span class="n">' + esc(num(row.count)) + "</span></div>";
    }).join("");
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
    el("queue-count").textContent = num(state.total) + " dòng · " +
      (BUCKET_HINT[state.bucket] || "");
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
    ["overview", "queue", "lookup"].forEach(function (name) {
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
      el("page-sub").textContent = BUCKET_HINT[bucket] || "";
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

    el("page-title").textContent = "Tổng quan";
    el("page-sub").textContent = "Việc đang chờ xử lý và tình trạng dữ liệu.";
  }

  function bucketTitle(key) {
    var found = (state.queue && state.queue.buckets || []).filter(function (bucket) {
      return bucket.key === key;
    })[0];
    return found ? found.label : "Hàng đợi";
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
