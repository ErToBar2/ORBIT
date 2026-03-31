# compileHTMLmap_static.py
from pathlib import Path
import csv, json

def sniff_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        first = f.readline()
        if ";" in first and "," not in first: return ";"
        if "," in first and ";" not in first: return ","
        sample = first + f.read(8192)
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except Exception:
        return ";"

def read_csv_rows(csv_path: Path):
    delim = sniff_delimiter(csv_path)
    print(f"[INFO] Detected delimiter: {repr(delim)}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        rows = [{k: (v if v is not None else "") for k, v in r.items()} for r in reader]
    print(f"[INFO] Rows read: {len(rows)}")
    return rows

def main():
    here = Path(__file__).resolve().parent
    csv_path = here / "MOW_bridge_information2025.csv"
    out_html = here / "bruggen_interactive_map_dynamic.html"

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows = read_csv_rows(csv_path)
    data_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")

    html = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Interactive Bridge Map (Embedded CSV)</title>

  <!-- Leaflet 1.9.4 with correct SRI -->
  <link rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
        crossorigin="">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
          integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
          crossorigin=""></script>

  <style>
    html, body, #map { height: 100%; margin: 0; }
    * { box-sizing: border-box; }
    .control-panel {
      position: absolute; top: 10px; left: 10px; z-index: 1000;
      background: rgba(255,255,255,.97); padding: 12px; border-radius: 8px;
      box-shadow: 0 2px 12px rgba(0,0,0,.15); max-width: 360px;
      font: 14px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      transform: translateX(0); transition: transform 200ms ease;
    }
    .control-panel.collapsed { transform: translateX(calc(-100% + 28px)); }
    .panel-toggle { position: absolute; top: 8px; right: -12px; width: 28px; height: 28px;
      border-radius: 50%; border: 1px solid #cbd5e1; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.18);
      display: grid; place-items: center; cursor: pointer; font-size: 16px; line-height: 1; }
    .row { margin-bottom: 8px; }
    .row label { display: block; font-weight: 600; margin-bottom: 4px; }
    .row input[type="text"], .row input[type="number"], .row select {
      width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px;
    }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .chips { display: inline-flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .chip { padding: 2px 8px; border-radius: 999px; background: #f3f4f6; border: 1px solid #e5e7eb; font-size: 12px;
      display: inline-flex; gap: 6px; align-items: center; }
    .chip .x { border: none; background: transparent; cursor: pointer; font-weight: 700; }
    .btn { appearance: none; border: 1px solid #ccc; background: #f9fafb; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
    .btn:hover { background: #f3f4f6; }
    .btn.primary { background: #2563eb; color: #fff; border-color: #1d4ed8; }
    .btn.primary:hover { background: #1d4ed8; }
    .divider { height: 1px; background: #e5e7eb; margin: 8px 0; }
    .legend { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,.2); }
    .dot.red { background: #d53e4f; } .dot.orange { background: #fdae61; } .dot.green { background: #66bd63; } .dot.gray { background: #9ca3af; }
    #debugBanner { position: absolute; top: 10px; right: 10px; z-index: 1001; background: #fee2e2; color: #991b1b; border: 1px solid #fecaca;
      border-radius: 6px; padding: 6px 10px; font: 13px/1.3 system-ui; display: none; }
    @media (max-width: 520px) { .control-panel { max-width: 86vw; } }
  </style>
</head>
<body>
  <div id="map"></div>
  <div id="debugBanner">No markers parsed — check your Google Maps URLs.</div>

  <div class="control-panel collapsed" id="panel">
    <button class="panel-toggle" id="panelToggle" title="Collapse/Expand" aria-label="Collapse filters">«</button>

    <h3>Bridges</h3>
    <div class="row">
      <label for="searchName">Search by name</label>
      <input id="searchName" list="nameList" type="text" placeholder="Type a bridge name…" />
      <datalist id="nameList"></datalist>
      <div style="margin-top:6px;"><button class="btn" id="btnZoomTo">Zoom to</button></div>
    </div>

    <div class="divider"></div>

    <div class="row">
      <label>Tag filters</label>
      <div class="grid-2">
        <div>
          <small>Not feasible</small>
          <select id="filterNotFeasible">
            <option value="any">Any</option>
            <option value="only">Only</option>
            <option value="except">Exclude</option>
          </select>
        </div>
        <div>
          <small>Inspected</small>
          <select id="filterInspected">
            <option value="any">Any</option>
            <option value="only">Only</option>
            <option value="except">Exclude</option>
          </select>
        </div>
      </div>
    </div>

    <div class="row" id="customTagFiltersSection" style="display:none;">
      <label>Custom tags</label>
      <div id="customTagFilters" class="grid-2"></div>
    </div>

    <div class="row">
      <label>Condition</label>
      <div id="conditionList" style="max-height:120px; overflow:auto;"></div>
    </div>

    <div class="row">
      <label>Length (m) range</label>
      <div class="grid-2">
        <input id="minLen" type="number" step="0.1" placeholder="min" />
        <input id="maxLen" type="number" step="0.1" placeholder="max" />
      </div>
    </div>

    <div class="row">
      <label>Width (m) range</label>
      <div class="grid-2">
        <input id="minWid" type="number" step="0.1" placeholder="min" />
        <input id="maxWid" type="number" step="0.1" placeholder="max" />
      </div>
    </div>

    <div>
      <button class="btn primary" id="btnApply">Apply filter</button>
      <button class="btn" id="btnReset">Reset</button>
      <button class="btn" id="btnFit">Fit to visible</button>
    </div>

    <div class="divider"></div>

    <div class="legend">
      <span><small>Findings on concrete:</small></span>
      <span class="dot red"></span><small>100+</small>
      <span class="dot orange"></span><small>30–99</small>
      <span class="dot green"></span><small>1–29</small>
      <span class="dot gray"></span><small>0/NA</small>
    </div>

    <div style="margin-top:8px;">
      <button class="btn" id="btnExportAll">Download updated CSV (all)</button>
      <button class="btn" id="btnExportVisible">Download visible as CSV</button>
      <button class="btn" id="btnClearTags">Clear local tags</button>
    </div>
    <div id="counter" style="margin-top:6px; font-size:12px;"></div>
  </div>

  <!-- Embedded CSV as JSON -->
  <script id="bridge-data" type="application/json">__DATA_JSON__</script>

  <script>
    const STORAGE_KEY = "bridgeTags_v4"; // schema version
    const PANEL_KEY = "panelCollapsed_v1";

    // Map setup
    const map = L.map("map", { preferCanvas: true }).setView([50.85, 4.35], 8);
    // Base layers (match flight_map.html behavior, maxZoom 30)
    const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 30,
      attribution: "&copy; OpenStreetMap contributors"
    });
    const satelliteLayer = L.tileLayer("https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", {
      maxZoom: 30,
      subdomains: ["mt0", "mt1", "mt2", "mt3"],
      attribution: "Imagery © Google"
    });
    // Default to OSM to mimic existing simple map default
    osmLayer.addTo(map);
    // Layer control toggle
    L.control.layers({
      "OpenStreetMap": osmLayer,
      "Satellite": satelliteLayer
    }).addTo(map);
    const markerLayer = L.layerGroup().addTo(map);

    // Data & state
    let rows = JSON.parse(document.getElementById("bridge-data").textContent);
    let items = [];
    let tagState = loadTags();
    let unsavedChanges = false;
    let lastVisibleRows = [];

    // Collapsible panel
    const panel = document.getElementById("panel");
    const panelToggle = document.getElementById("panelToggle");
    function setCollapsed(c) {
      panel.classList.toggle("collapsed", !!c);
      panelToggle.textContent = c ? "»" : "«";
      panelToggle.setAttribute("aria-label", c ? "Expand filters" : "Collapse filters");
      try { localStorage.setItem(PANEL_KEY, c ? "1" : "0"); } catch(e) {}
    }
    panelToggle.addEventListener("click", () => setCollapsed(!panel.classList.contains("collapsed")));
    try {
      const savedPanelState = localStorage.getItem(PANEL_KEY);
      setCollapsed(savedPanelState === null ? true : savedPanelState === "1");
    } catch(e) {
      setCollapsed(true);
    }

    // Persistence
    function loadTags() { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch(e) { return {}; } }
    function saveTags() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(tagState)); } catch(e) {} }

    // Helpers
    function parseNumber(v) {
      if (v === null || v === undefined) return NaN;
      const s = String(v).trim().replace(",", ".");
      const n = parseFloat(s);
      return Number.isFinite(n) ? n : NaN;
    }
    // ✅ Safe regex literals + fallback
    function parseLatLonFromGoogle(url) {
      if (!url) return null;
      try {
        let m = url.match(/@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/);
        if (m) return [parseFloat(m[1]), parseFloat(m[2])];
        m = url.match(/[?&](?:q|ll)=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/);
        if (m) return [parseFloat(m[1]), parseFloat(m[2])];
        m = url.match(/\/place\/(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)/);
        if (m) return [parseFloat(m[1]), parseFloat(m[2])];
        const nums = (url.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
        for (let i = 0; i + 1 < nums.length; i++) {
          const a = nums[i], b = nums[i + 1];
          if (Math.abs(a) <= 90 && Math.abs(b) <= 180) return [a, b];
        }
      } catch (e) {}
      return null;
    }
    function colorForFindings(n) {
      if (!Number.isFinite(n) || n <= 0) return "#9ca3af";
      if (n >= 100) return "#d53e4f";
      if (n >= 30)  return "#fdae61";
      return "#66bd63";
    }
    function uniqueKey(row) {
      return (row["Bridge name"] || "") + "||" + (row["Google maps url"] || "");
    }
    function escapeHTML(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({
        "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
      }[c]));
    }
    function sanitizeId(s) { return String(s).replace(/[^A-Za-z0-9_-]/g, "_"); }

    // Popup UI
    function buildPopupHTML(item, idx) {
      const r = item.row;
      const findings = (r["Findings on concrete"] ?? "").toString();
      const len = r["Length (m)"] ?? "—";
      const wid = r["Width (m)"] ?? "—";
      const cond = r["Condition"] ?? "—";
      const url = r["Google maps url"] || "#";

      const key = uniqueKey(r);
      const ts = tagState[key] || { notFeasible:false, inspected:false, custom: [] };
      const idNF = `notfeasible_${idx}`;
      const idIns = `inspected_${idx}`;
      const idCTWrap = `customWrap_${idx}`;
      const idCTInput = `customInput_${idx}`;
      const idCTAdd = `customAdd_${idx}`;

      return `
        <div style="min-width:270px">
          <div style="font-weight:700; margin-bottom:4px;">${escapeHTML(r["Bridge name"] || "—")}</div>
          <div>Condition: ${escapeHTML(cond)}</div>
          <div>Length (m): ${escapeHTML(String(len))}</div>
          <div>Width (m): ${escapeHTML(String(wid))}</div>
          <div>Findings on concrete: ${escapeHTML(findings)}</div>
          <div style="margin-top:4px;">
            <a href="${url}" target="_blank" rel="noopener">Open in Google Maps</a>
          </div>

          <div style="margin:8px 0 4px 0; font-weight:600;">Tags</div>
          <div class="chips" style="margin-bottom:6px;">
            <label class="chip">
              <input type="checkbox" id="${idNF}" ${ts.notFeasible ? "checked" : ""}/> Not feasible
            </label>
            <label class="chip">
              <input type="checkbox" id="${idIns}" ${ts.inspected ? "checked" : ""}/> Inspected
            </label>
          </div>

          <div class="row" style="margin-top:6px;">
            <label style="font-weight:600; margin-bottom:4px;">Custom tags</label>
            <div id="${idCTWrap}" class="chips" style="margin-bottom:6px;"></div>
            <div class="grid-2">
              <input id="${idCTInput}" type="text" placeholder="Add a tag…" />
              <button class="btn" id="${idCTAdd}">Add</button>
            </div>
          </div>
        </div>
      `;
    }

    function renderCustomChips(container, key) {
      container.innerHTML = "";
      const tags = (tagState[key] && Array.isArray(tagState[key].custom)) ? tagState[key].custom : [];
      tags.forEach(t => {
        const chip = document.createElement("span");
        chip.className = "chip";
        const label = document.createElement("span"); label.textContent = t;
        const btn = document.createElement("button"); btn.className = "x"; btn.textContent = "×"; btn.title = "Remove";
        btn.addEventListener("click", () => {
          const arr = tagState[key].custom || [];
          tagState[key].custom = arr.filter(x => x !== t);
          saveTags(); unsavedChanges = true; renderCustomChips(container, key);
          rebuildCustomTagFilters(); applyFilters();
        });
        chip.appendChild(label); chip.appendChild(btn);
        container.appendChild(chip);
      });
    }
    function addCustomTag(key, tag, container, inputEl) {
      const val = (tag || "").trim();
      if (!val) return;
      tagState[key] = tagState[key] || { notFeasible:false, inspected:false, custom: [] };
      const arr = tagState[key].custom || [];
      if (!arr.includes(val)) arr.push(val);
      tagState[key].custom = arr;
      saveTags(); unsavedChanges = true; renderCustomChips(container, key);
      if (inputEl) { inputEl.value = ""; inputEl.focus(); }
      rebuildCustomTagFilters(); applyFilters();
    }

    function wirePopupEvents(idx, item) {
      const key = uniqueKey(item.row);
      tagState[key] = tagState[key] || { notFeasible:false, inspected:false, custom: [] };

      const nf = document.getElementById(`notfeasible_${idx}`);
      const ins = document.getElementById(`inspected_${idx}`);
      if (nf) nf.addEventListener("change", (e) => { tagState[key].notFeasible = !!e.target.checked; saveTags(); unsavedChanges = true; applyFilters(); });
      if (ins) ins.addEventListener("change", (e) => { tagState[key].inspected   = !!e.target.checked; saveTags(); unsavedChanges = true; applyFilters(); });

      const wrap = document.getElementById(`customWrap_${idx}`);
      const inp  = document.getElementById(`customInput_${idx}`);
      const add  = document.getElementById(`customAdd_${idx}`);
      if (wrap) renderCustomChips(wrap, key);
      if (add) add.addEventListener("click", () => addCustomTag(key, inp && inp.value, wrap, inp));
      if (inp) inp.addEventListener("keydown", (e) => { if (e.key === "Enter") addCustomTag(key, inp.value, wrap, inp); });
    }

    // Build markers
    function buildMarkers() {
      markerLayer.clearLayers();
      let ok = 0, fail = 0;
      items.forEach((item, idx) => {
        if (!Array.isArray(item.latlon)) { fail++; return; }
        const marker = L.circleMarker(item.latlon, {
          radius: 7, fillColor: colorForFindings(item.findingsNum), color: "#333", weight: 2, opacity: 1, fillOpacity: 0.8
        });
        marker.bindPopup(() => buildPopupHTML(item, idx));
        marker.on("popupopen", () => wirePopupEvents(idx, item));
        item.marker = marker; ok++;
      });
      if (ok === 0) document.getElementById("debugBanner").style.display = "block";
      applyFilters();
    }

    // Filters
    function populateFilters() {
      const dl = document.getElementById("nameList"); dl.innerHTML = "";
      rows.forEach(r => { if (r["Bridge name"]) { const o = document.createElement("option"); o.value = r["Bridge name"]; dl.appendChild(o); } });

      const conds = Array.from(new Set(rows.map(r => r["Condition"]).filter(Boolean))).sort();
      const condList = document.getElementById("conditionList"); condList.innerHTML = "";
      conds.forEach((c, i) => {
        const id = "cond_" + i;
        const lab = document.createElement("label");
        lab.innerHTML = `<input type="checkbox" id="${id}" data-cond="${escapeHTML(c)}" checked /> ${escapeHTML(c)}`;
        condList.appendChild(lab);
      });

      const lens = rows.map(r => parseNumber(r["Length (m)"])).filter(Number.isFinite);
      const wids = rows.map(r => parseNumber(r["Width (m)"])).filter(Number.isFinite);
      document.getElementById("minLen").value = lens.length ? Math.min(...lens).toFixed(2) : "";
      document.getElementById("maxLen").value = lens.length ? Math.max(...lens).toFixed(2) : "";
      document.getElementById("minWid").value = wids.length ? Math.min(...wids).toFixed(2) : "";
      document.getElementById("maxWid").value = wids.length ? Math.max(...wids).toFixed(2) : "";

      const auto = () => applyFilters();
      document.getElementById("filterNotFeasible").addEventListener("change", auto);
      document.getElementById("filterInspected").addEventListener("change", auto);
      condList.addEventListener("change", auto);
      ["minLen","maxLen","minWid","maxWid"].forEach(id => {
        const el = document.getElementById(id);
        el.addEventListener("input", auto); el.addEventListener("change", auto);
      });

      rebuildCustomTagFilters();
    }

    function activeConditions() {
      return new Set(Array.from(document.querySelectorAll("#conditionList input[type=checkbox]"))
        .filter(b => b.checked).map(b => b.getAttribute("data-cond")));
    }

    // Custom tag filter UI
    function allCustomTags() {
      const s = new Set();
      Object.values(tagState).forEach(v => (v && Array.isArray(v.custom)) && v.custom.forEach(t => s.add(String(t))));
      return Array.from(s).sort((a,b) => a.localeCompare(b, undefined, {sensitivity:"base"}));
    }
    function rebuildCustomTagFilters() {
      const tags = allCustomTags();
      const section = document.getElementById("customTagFiltersSection");
      const wrap = document.getElementById("customTagFilters");
      wrap.innerHTML = "";
      if (!tags.length) { section.style.display = "none"; return; }
      section.style.display = "";
      tags.forEach(t => {
        const id = "ctf_" + sanitizeId(t);
        const box = document.createElement("div");
        box.innerHTML = `
          <div><small>${escapeHTML(t)}</small>
            <select id="${id}">
              <option value="any">Any</option>
              <option value="only">Only</option>
              <option value="except">Exclude</option>
            </select>
          </div>`;
        wrap.appendChild(box);
      });
      wrap.querySelectorAll("select").forEach(sel => sel.addEventListener("change", applyFilters));
    }
    function customTagFilterModes() {
      const res = {};
      document.querySelectorAll("#customTagFilters select").forEach(sel => {
        const small = sel.parentElement?.querySelector("small");
        const tag = small ? small.textContent : "";
        if (tag) res[tag] = sel.value;
      });
      return res;
    }

    function applyFilters() {
      const notFeasibleMode = document.getElementById("filterNotFeasible").value;
      const inspectedMode   = document.getElementById("filterInspected").value;
      const customModes = customTagFilterModes();

      const conds = activeConditions();
      const minLen = parseNumber(document.getElementById("minLen").value);
      const maxLen = parseNumber(document.getElementById("maxLen").value);
      const minWid = parseNumber(document.getElementById("minWid").value);
      const maxWid = parseNumber(document.getElementById("maxWid").value);

      markerLayer.clearLayers();
      lastVisibleRows = [];
      let visible = 0;

      items.forEach(item => {
        const r = item.row;
        const key = uniqueKey(r);
        const tags = tagState[key] || { notFeasible:false, inspected:false, custom: [] };
        const custom = Array.isArray(tags.custom) ? tags.custom : [];

        if (notFeasibleMode === "only"   && !tags.notFeasible) return;
        if (notFeasibleMode === "except" &&  tags.notFeasible) return;
        if (inspectedMode   === "only"   && !tags.inspected)   return;
        if (inspectedMode   === "except" &&  tags.inspected)   return;

        for (const [ctag, mode] of Object.entries(customModes)) {
          if (mode === "only"   && !custom.includes(ctag)) return;
          if (mode === "except" &&  custom.includes(ctag)) return;
        }

        const cond = r["Condition"];
        if (conds.size > 0 && cond && !conds.has(cond)) return;

        const Lm = item.lengthNum, Wm = item.widthNum;
        if (Number.isFinite(minLen) && Number.isFinite(Lm) && Lm < minLen) return;
        if (Number.isFinite(maxLen) && Number.isFinite(Lm) && Lm > maxLen) return;
        if (Number.isFinite(minWid) && Number.isFinite(Wm) && Wm < minWid) return;
        if (Number.isFinite(maxWid) && Number.isFinite(Wm) && Wm > maxWid) return;

        item.marker.addTo(markerLayer);
        visible++;
        lastVisibleRows.push(r);
      });

      document.getElementById("counter").textContent = `${visible} / ${items.length} visible`;
    }

    // Search/map commands
    function zoomToName() {
      const name = (document.getElementById("searchName").value || "").trim().toLowerCase();
      if (!name) return;
      let match = items.find(it => (it.row["Bridge name"] || "").toLowerCase() === name)
              || items.find(it => (it.row["Bridge name"] || "").toLowerCase().includes(name));
      if (!match) return;
      map.setView(match.latlon, 16);
      if (match.marker) match.marker.openPopup();
    }
    function fitToVisible() {
      const group = L.featureGroup(markerLayer.getLayers());
      if (group.getLayers().length > 0) map.fitBounds(group.getBounds().pad(0.2));
    }
    
    function mergeRowsWithTags(rowList) {
      const TAGS_COL = "Tags";
      if (!rowList || !rowList.length) return { order: [], data: [] };

      // Strip any legacy tag columns from the source rows.
      const dropCols = new Set(["Tags", "Tags: Custom", "Tag: Not feasible", "Tag: Inspected"]);
      const baseOrder = Object.keys(rowList[0]).filter(k => !dropCols.has(k) && !/^Tag:/i.test(k));
      const finalOrder = baseOrder.concat([TAGS_COL]);

      const out = rowList.map(r => {
        const copy = {};
        baseOrder.forEach(k => { copy[k] = r[k]; });

        const t = tagState[uniqueKey(r)] || { notFeasible:false, inspected:false, custom: [] };
        const parts = [];
        if (t.notFeasible) parts.push("Not feasible");
        if (t.inspected)   parts.push("Inspected");

        // Clean custom tags (no tabs/newlines)
        if (Array.isArray(t.custom)) {
          t.custom.forEach(s => {
            const clean = String(s || "").replace(/[\t\r\n]/g, " ").trim();
            if (clean) parts.push(clean);
          });
        }

        // Deduplicate, then join with semicolons
        copy[TAGS_COL] = Array.from(new Set(parts)).join(";");
        return copy;
      });

      return { order: finalOrder, data: out };
    }

    function toCSV(objects, order) {
      const DELIM = ",";                 // file delimiter
      const NEEDS_QUOTE = /[",;\t\n]/;   // quote if contains any of these
      const BOM = "\uFEFF";              // UTF-8 BOM for Excel
      const SEP = "sep=,\r\n";           // tell Excel to use comma as delimiter

      const esc = (v, force) => {
        if (v == null) v = "";
        v = String(v);
        if (force || NEEDS_QUOTE.test(v)) {
          v = '"' + v.replace(/"/g, '""') + '"';
        }
        return v;
      };

      // header
      const header = order.map(h => esc(h, false)).join(DELIM);

      // rows — force-quote Tags column always
      const lines = objects.map(o =>
        order.map(k => esc(o[k], k === "Tags")).join(DELIM)
      );

      // BOM + sep=, + CRLF
      return BOM + SEP + header + "\r\n" + lines.join("\r\n");
    }

    function downloadCSV(rowList, filename) {
      const {order, data} = mergeRowsWithTags(rowList);
      if (!data.length) { alert("Nothing to export."); return; }
      const csv = toCSV(data, order);
      const url = URL.createObjectURL(new Blob([csv], {type:"text/csv;charset=utf-8"}));
      const a = Object.assign(document.createElement("a"), { href: url, download: filename });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      unsavedChanges = false;
    }

    // Wire controls
    document.getElementById("btnApply").addEventListener("click", applyFilters);
    document.getElementById("btnReset").addEventListener("click", () => {
      document.getElementById("filterNotFeasible").value = "any";
      document.getElementById("filterInspected").value = "any";
      document.querySelectorAll("#conditionList input[type=checkbox]").forEach(cb => cb.checked = true);
      populateFilters(); applyFilters();
    });
    document.getElementById("btnFit").addEventListener("click", fitToVisible);
    document.getElementById("btnZoomTo").addEventListener("click", zoomToName);
    document.getElementById("btnExportAll").addEventListener("click", () => downloadCSV(rows, "MOW_bridge_information2025_with_tags.csv"));
    document.getElementById("btnExportVisible").addEventListener("click", () => downloadCSV(lastVisibleRows, "MOW_bridge_information2025_visible_with_tags.csv"));
    document.getElementById("btnClearTags").addEventListener("click", () => {
      if (confirm("Clear all saved tag states on this device?")) {
        tagState = {}; saveTags(); unsavedChanges = false; rebuildCustomTagFilters(); applyFilters(); alert("Local tag states cleared.");
      }
    });
    document.getElementById("searchName").addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("btnZoomTo").click(); });
    window.addEventListener("beforeunload", (e) => { if (unsavedChanges) { e.preventDefault(); e.returnValue = ""; } });

    // Build items and render
    items = rows.map((r) => {
      const latlon = parseLatLonFromGoogle(r["Google maps url"]);
      const findingsNum = parseNumber(r["Findings on concrete"]);
      const lengthNum = parseNumber(r["Length (m)"]);
      const widthNum  = parseNumber(r["Width (m)"]);
      return { row: r, latlon, findingsNum, lengthNum, widthNum, marker: null };
    });
    buildMarkers();
    populateFilters();
    applyFilters();
  </script>
</body>
</html>
"""
    out_html.write_text(html.replace("__DATA_JSON__", data_json), encoding="utf-8")
    print(f"✅ Wrote: {out_html}")
    print("Open the HTML directly (data is embedded).")

if __name__ == "__main__":
    main()
