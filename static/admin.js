/* Nuôi Em · admin dashboard
 *
 * No inline handlers anywhere: the server sends
 * `script-src 'self'`, so every listener is attached here. That is also why
 * there is no framework — a 12 KB file that runs under a strict CSP is easier
 * to defend than a bundle that needs three relaxations to boot.
 */

(function () {
  "use strict";

  var nf = new Intl.NumberFormat("vi-VN");

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

  // --------------------------------------------------------------- overview

  function renderMetrics(summary, queue) {
    var byKey = {};
    (queue.buckets || []).forEach(function (bucket) { byKey[bucket.key] = bucket; });
    var noCode = byKey.inbound_no_code || { count: 0, amount: 0 };
    var orphan = byKey.code_no_profile || { count: 0, amount: 0 };
    var coverage = summary.coverage || {};
    var balanced = summary.integrity && summary.integrity.balanced;

    var cards = [
      {
        label: "Dòng vào chưa gán mã",
        value: num(noCode.count),
        note: compact(noCode.amount) + " đang bị ảnh hưởng",
        cls: "risk"
      },
      {
        label: "Mã có tiền, chưa có hồ sơ",
        value: num(orphan.count),
        note: compact(orphan.amount) + " đã phân bổ"
      },
      {
        label: "Độ phủ tiền vào",
        value: (coverage.allocated_percent || 0).toFixed(2).replace(".", ",") + "%",
        note: compact(coverage.inbound_unallocated) + " chưa gắn mã"
      },
      {
        label: "Phần chia khớp tổng",
        value: balanced ? "Khớp" : "Lệch",
        note: balanced ? "phân bổ = giao dịch liên kết" : "cần kiểm tra lại",
        cls: balanced ? "ok" : "risk"
      }
    ];

    el("metrics").innerHTML = cards.map(function (card) {
      return '<div class="metric ' + (card.cls || "") + '">' +
        '<p class="label">' + esc(card.label) + "</p>" +
        '<p class="value">' + esc(card.value) + "</p>" +
        '<p class="note">' + esc(card.note) + "</p>" +
        "</div>";
    }).join("");
  }

  function renderQueue(queue) {
    var buckets = queue.buckets || [];
    if (!buckets.length) {
      el("queue").innerHTML = '<p class="empty">Không có việc nào đang mở.</p>';
      return;
    }
    el("queue").innerHTML = buckets.map(function (bucket) {
      return '<div class="bucket">' +
        '<span class="name">' + esc(bucket.label) + "</span>" +
        '<span class="amount">' + esc(compact(bucket.amount)) + "</span>" +
        '<span class="meta">' +
          '<span class="count">' + esc(num(bucket.count)) + " dòng</span>" +
          "<span>" + esc(bucket.action) + "</span>" +
        "</span>" +
        "</div>";
    }).join("");
  }

  function renderYears(rows) {
    if (!rows || !rows.length) {
      el("years").innerHTML = '<p class="empty">Chưa có dòng nào.</p>';
      return;
    }
    var max = rows.reduce(function (best, row) {
      return Math.max(best, row.count);
    }, 1);

    el("years").innerHTML = rows.map(function (row) {
      // Rounded to a 5% step so the width can come from a class instead of a
      // style attribute, which `style-src 'self'` would block.
      var step = Math.max(5, Math.round((row.count / max) * 20) * 5);
      return '<div class="year-row">' +
        '<span class="yr">' + esc(row.year) + "</span>" +
        '<span class="year-track"><span class="year-fill w-' + step + '"></span></span>' +
        '<span class="n">' + esc(num(row.count)) + "</span>" +
        "</div>";
    }).join("");
  }

  function renderStatus(meta, audit, summary) {
    var source = meta.source || {};
    var rows = [
      ["Lần import gần nhất", source.source_name ? esc(source.source_name) : "—"],
      ["Thời điểm", source.imported_at ? esc(date(source.imported_at)) : "—"],
      ["Số dòng đã nạp", source.raw_transaction_rows ? num(source.raw_transaction_rows) + " giao dịch · " +
        num(source.allocation_rows) + " phân bổ" : "—"],
      ["Khoảng dữ liệu", summary.period ? date(summary.period.from) + " → " + date(summary.period.to) : "—"],
      ["Chuỗi audit", audit.chain_intact
        ? '<span class="badge ok">toàn vẹn</span>'
        : '<span class="badge risk">đứt tại #' + esc(audit.first_broken_event_id) + "</span>"]
    ];

    el("status").innerHTML = rows.map(function (row) {
      return '<div class="status-row"><span class="k">' + esc(row[0]) +
        '</span><span class="v">' + row[1] + "</span></div>";
    }).join("");
  }

  // ----------------------------------------------------------------- search

  var STATUS_BADGE = {
    has_profile: ["ok", "đã có hồ sơ"],
    has_money_no_profile: ["warn", "có tiền, chưa có hồ sơ"],
    unknown_code: ["muted", "không có giao dịch nào"]
  };

  // The database stores the policy and match status as identifiers. An admin
  // reading a queue should not have to translate `equal_split_with_remainder`
  // in their head, so the labels live here rather than in the query.
  var POLICY_LABEL = {
    single_code: "một mã",
    equal_split: "chia đều",
    equal_split_with_remainder: "chia đều, dư 1đ"
  };

  var MATCH_LABEL = {
    ambiguous: "chưa xác định",
    matched: "đã khớp",
    unmatched: "chưa khớp"
  };

  function label(map, value) {
    return map[value] || value || "—";
  }

  function renderNeResult(payload, input) {
    var badge = STATUS_BADGE[payload.status] || ["muted", payload.status || "không rõ"];
    var allocations = payload.allocations || [];

    var head = '<div class="result-head">' +
      '<span class="result-code">' + esc(payload.ne_code) + "</span>" +
      '<span class="badge ' + badge[0] + '">' + esc(badge[1]) + "</span>" +
      '<span class="result-meta">' +
        esc(payload.meal_plan || "không rõ") + " · " +
        esc(num(payload.distinct_transactions)) + " giao dịch · " +
        esc(date(payload.first_seen)) + " → " + esc(date(payload.last_seen)) +
      "</span>" +
      "</div>";

    var variants = payload.variants || [];
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
      variantRow +
      "</dl></div>";

    var blockProfile = payload.registry_available
      ? '<div class="block"><h3>Trường và hồ sơ</h3><dl class="kv">' +
          "<dt>Trường</dt><dd>" + esc(payload.registry[0].school_name || "—") + "</dd>" +
          "<dt>Tỉnh</dt><dd>" + esc(payload.registry[0].province || "—") + "</dd>" +
          "<dt>Lớp</dt><dd>" + esc(payload.registry[0].class_name || "—") + "</dd>" +
          "</dl></div>"
      : '<div class="block"><h3>Trường và hồ sơ</h3><div class="empty">' +
          "<strong>Chưa có hồ sơ.</strong> Mã này đã nhận tiền nhưng chưa gắn với học sinh " +
          "hay trường nào. Danh mục học sinh chưa được nhập vào hệ thống, nên đây là trạng thái " +
          "của toàn bộ mã đang có tiền." +
        "</div></div>";

    var blockDonor = '<div class="block"><h3>Nhà tài trợ</h3><div class="empty">' +
      "<strong>Chưa gắn mã ACN.</strong> Mã ACN đến từ chatbot Facebook, không có trong sao kê " +
      "ngân hàng, nên chưa nối được với mã NE." +
      "</div></div>";

    var rows = allocations.slice(0, 8).map(function (row) {
      return "<tr>" +
        '<td class="mono">' + esc(date(row.tx_time)) + "</td>" +
        '<td class="num">' + esc(money(row.allocated_amount_computed)) + "</td>" +
        "<td>" + esc(label(POLICY_LABEL, row.allocation_policy)) + "</td>" +
        "<td>" + esc(label(MATCH_LABEL, row.match_status)) + "</td>" +
        "</tr>";
    }).join("");

    var blockMoney = '<div class="block span"><h3>Dòng tiền nhận được</h3>' +
      (allocations.length
        ? '<table class="tx"><thead><tr><th>Ngày</th><th class="num">Số tiền</th>' +
          "<th>Cách chia</th><th>Trạng thái</th></tr></thead><tbody>" + rows + "</tbody></table>" +
          (allocations.length > 8
            ? '<p class="hint">Hiển thị 8 trong ' + esc(num(allocations.length)) + " dòng.</p>"
            : "")
        : '<div class="empty">Mã này không xuất hiện trong giao dịch nào.</div>') +
      "</div>";

    el("result").innerHTML = head +
      '<div class="result-body">' + blockCode + blockProfile + blockMoney + blockDonor + "</div>";
    el("result").hidden = false;
    el("result").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderMessage(title, detail) {
    el("result").innerHTML = '<div class="result-head">' +
      '<span class="result-code">' + esc(title) + "</span></div>" +
      '<div class="result-body"><div class="block span"><div class="empty">' +
      esc(detail) + "</div></div></div>";
    el("result").hidden = false;
  }

  function doSearch(rawQuery) {
    var query = (rawQuery || "").trim();
    if (!query) return;
    var hint = el("search-hint");
    hint.className = "hint";
    hint.textContent = "Đang tra…";

    getJSON("/api/admin/search?q=" + encodeURIComponent(query))
      .then(function (found) {
        if (found.kind === "ne") {
          hint.textContent = "Nhận dạng: mã NE " + found.code;
          return getJSON("/api/ne?ne=" + encodeURIComponent(found.code))
            .then(function (payload) { renderNeResult(payload, query); });
        }
        if (found.kind === "acn") {
          hint.textContent = "Nhận dạng: mã ACN";
          renderMessage(found.code,
            "Tra cứu theo mã ACN chưa dùng được: bảng nhà tài trợ đang trống, và mã ACN " +
            "không xuất hiện trong sao kê ngân hàng.");
          return;
        }
        if (found.kind === "reference") {
          hint.className = "hint warn";
          hint.textContent = "Nhận dạng: số tham chiếu giao dịch";
          renderMessage(found.code,
            "Số tham chiếu tra theo mã giao dịch ngân hàng. Mở bảng công khai để tìm theo " +
            "số này, hoặc nhập mã NE nếu đã biết.");
          return;
        }
        hint.className = "hint warn";
        hint.textContent = found.hint || "Không nhận dạng được.";
        el("result").hidden = true;
      })
      .catch(function (error) {
        hint.className = "hint warn";
        hint.textContent = "Không tra được: " + error.message;
      });
  }

  // ------------------------------------------------------------------- boot

  function boot() {
    el("search-form").addEventListener("submit", function (event) {
      event.preventDefault();
      doSearch(el("q").value);
    });

    Promise.all([
      getJSON("/api/summary"),
      getJSON("/api/admin/queue"),
      getJSON("/api/metadata"),
      getJSON("/api/audit?limit=1")
    ]).then(function (results) {
      renderMetrics(results[0], results[1]);
      renderQueue(results[1]);
      renderYears(results[1].unmapped_by_year);
      renderStatus(results[2], results[3], results[0]);
    }).catch(function (error) {
      el("metrics").innerHTML =
        '<p class="empty">Không tải được dữ liệu: ' + esc(error.message) + "</p>";
    });

    // Deep link: /admin?q=NE01156 opens straight on that code, so a provincial
    // officer can be sent the result instead of instructions on how to find it.
    var linked = new URLSearchParams(location.search).get("q");
    if (linked) {
      el("q").value = linked;
      doSearch(linked);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
