(() => {
  const diagram = document.querySelector("#loads-diagram");
  const board = document.querySelector("#season-board");
  const svg = document.querySelector("#flow-edges");
  const panel = document.querySelector("#board-panel");
  if (!board || !panel) return;

  const lines = [...document.querySelectorAll(".flow-line")];
  const jobOverlays = [...document.querySelectorAll(".flow-job-overlay")];
  const edgeGroups = svg ? [...svg.querySelectorAll(".flow-edge-group")] : [];
  const filter = document.querySelector("#board-filter");
  const panelTitle = document.querySelector("#board-panel-title");

  let yardStock = {};
  if (diagram && diagram.dataset.yardStock) {
    try {
      yardStock = JSON.parse(diagram.dataset.yardStock);
    } catch (_err) {
      yardStock = {};
    }
  }

  function loadIdsOf(el) {
    const raw = el.dataset.loads || el.dataset.load || "";
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  if (filter) {
    filter.addEventListener("input", () => {
      const term = filter.value.trim().toLowerCase();
      lines.forEach((line) => {
        const hay = (line.dataset.search || line.textContent || "").toLowerCase();
        line.hidden = Boolean(term) && !hay.includes(term);
      });
      jobOverlays.forEach((block) => {
        const hay = (block.dataset.search || "").toLowerCase();
        const childMatch = [...block.querySelectorAll(".flow-line")].some(
          (el) => !el.hidden
        );
        block.style.opacity =
          !term || hay.includes(term) || childMatch ? "1" : "0.18";
      });
      edgeGroups.forEach((group) => {
        const label = (group.dataset.label || "").toLowerCase();
        const full = (group.dataset.full || "").toLowerCase();
        const origin = (group.dataset.origin || "").toLowerCase();
        const dest = (group.dataset.dest || "").toLowerCase();
        const match =
          !term ||
          label.includes(term) ||
          full.includes(term) ||
          origin.includes(term) ||
          dest.includes(term);
        group.style.opacity = match ? "" : "0.12";
      });
    });
  }

  function clearHighlight() {
    lines.forEach((el) => el.classList.remove("highlighted", "dimmed"));
    edgeGroups.forEach((el) => el.classList.remove("highlighted"));
  }

  function highlightLoads(ids) {
    clearHighlight();
    if (!ids || !ids.length) return;
    const set = new Set(ids.map(String));
    lines.forEach((line) => {
      const idsLine = loadIdsOf(line);
      const match = idsLine.some((id) => set.has(id));
      line.classList.toggle("highlighted", match);
      line.classList.toggle("dimmed", !match && idsLine.length > 0);
    });
    edgeGroups.forEach((group) => {
      const idsEdge = loadIdsOf(group);
      group.classList.toggle(
        "highlighted",
        idsEdge.some((id) => set.has(id))
      );
    });
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showPanel(title, bodyHtml) {
    panel.hidden = false;
    if (panelTitle) panelTitle.textContent = title;
    const copy = panel.querySelector(".panel-copy");
    copy.innerHTML = bodyHtml;
  }

  function loadDetailHtml(ds, fallbackLabel) {
    const label = ds.label || fallbackLabel || "Load";
    const rows = [
      ["From", ds.origin],
      ["To", ds.dest],
      ["Depart", ds.depart],
      ["Arrive", ds.arrive],
      ["Vehicle type", ds.vehicle],
      ["Haulier", ds.haulier],
    ];
    const table = rows
      .map(
        ([k, v]) =>
          `<tr><th class="text-start pe-3">${escapeHtml(k)}</th><td>${escapeHtml(v || "—")}</td></tr>`,
      )
      .join("");
    const href = ds.href || "";
    const multi = (ds.loads || "").split(",").filter(Boolean).length > 1;
    return `
      <p class="mb-2"><strong>${escapeHtml(label)}</strong>${multi ? ' <span class="badge text-bg-secondary">convoy</span>' : ""}</p>
      <table class="table table-sm table-borderless mb-3"><tbody>${table}</tbody></table>
      <h3 class="h6">Contents (incl. linked kit)</h3>
      <p class="small mb-3">${escapeHtml(ds.full || ds.codes || "(empty)")}</p>
      ${href ? `<a class="btn btn-primary" href="${escapeHtml(href)}">Open load sheet</a>` : ""}
    `;
  }

  function showLoadFromDataset(ds, fallbackLabel) {
    highlightLoads(loadIdsOf({ dataset: ds }));
    // datasetFromEl returns plain object — highlight via loads string
    const ids = (ds.loads || ds.load || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    highlightLoads(ids);
    showPanel(ds.label || fallbackLabel || "Load", loadDetailHtml(ds, fallbackLabel));
  }

  function datasetFromEl(el) {
    return {
      load: el.dataset.load || "",
      loads: el.dataset.loads || el.dataset.load || "",
      label: el.dataset.label || el.textContent.trim(),
      full: el.dataset.full || "",
      codes: el.dataset.codes || "",
      origin: el.dataset.origin || "",
      dest: el.dataset.dest || "",
      depart: el.dataset.depart || "",
      arrive: el.dataset.arrive || "",
      vehicle: el.dataset.vehicle || "",
      haulier: el.dataset.haulier || "",
      href: el.dataset.href || el.getAttribute("href") || "",
    };
  }

  lines.forEach((line) => {
    line.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey) return;
      event.preventDefault();
      event.stopPropagation();
      showLoadFromDataset(datasetFromEl(line), line.textContent.trim());
    });
  });

  edgeGroups.forEach((group) => {
    group.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey) return;
      event.preventDefault();
      showLoadFromDataset(datasetFromEl(group), group.dataset.label || "Load");
    });
  });

  board.querySelectorAll(".yard-day-cell").forEach((cell) => {
    cell.addEventListener("click", (event) => {
      if (event.target.closest(".flow-line")) return;
      const day = cell.dataset.yardDay;
      if (!day) return;
      clearHighlight();
      const stock = yardStock[day];
      let html = `<p class="small text-muted mb-2">Components expected in the Yard on <strong>${escapeHtml(day)}</strong>.</p>`;
      if (stock && stock.assets && stock.assets.length) {
        html += `<h3 class="h6">Named assets</h3><ul class="small">${stock.assets.map((a) => `<li><code>${escapeHtml(a)}</code></li>`).join("")}</ul>`;
      }
      if (stock && stock.quantities && stock.quantities.length) {
        html += `<h3 class="h6">Quantities on loads</h3><ul class="small">${stock.quantities.map(([c, n]) => `<li><code>${escapeHtml(c)}</code> × ${n}</li>`).join("")}</ul>`;
      }
      if (!stock || ((!stock.assets || !stock.assets.length) && (!stock.quantities || !stock.quantities.length))) {
        html += `<p><em>${escapeHtml((stock && stock.summary) || "(empty / not tracked)")}</em></p>`;
      }
      showPanel(`Yard · ${day}`, html);
    });
  });

  panel.querySelector(".btn-close").addEventListener("click", () => {
    panel.hidden = true;
    clearHighlight();
  });
})();
