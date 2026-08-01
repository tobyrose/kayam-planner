(() => {
  const board = document.querySelector("#season-board");
  if (!board) return;
  const filter = document.querySelector("#board-filter");
  const panel = document.querySelector("#board-panel");
  const blocks = [...board.querySelectorAll(".season-block")];

  filter.addEventListener("input", () => {
    const term = filter.value.trim().toLowerCase();
    blocks.forEach((block) => {
      block.hidden = Boolean(term) && !block.dataset.search.toLowerCase().includes(term);
    });
  });

  document.querySelectorAll(".board-zoom").forEach((button) => {
    button.addEventListener("click", () => {
      board.dataset.zoom = button.dataset.zoom;
    });
  });

  blocks.forEach((block) => {
    block.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey) return;
      event.preventDefault();
      const key = block.dataset.asset
        ? ["asset", block.dataset.asset]
        : block.dataset.job
          ? ["job", block.dataset.job]
          : block.dataset.load
            ? ["load", block.dataset.load]
            : [null, null];
      blocks.forEach((candidate) => candidate.classList.remove("highlighted", "dimmed"));
      if (key[0]) {
        blocks.forEach((candidate) => {
          const matches = candidate.dataset[key[0]] === key[1]
            || (key[0] === "asset" && (candidate.dataset.assets || "").split(" ").includes(key[1]));
          candidate.classList.toggle("highlighted", matches);
          candidate.classList.toggle("dimmed", !matches);
        });
      }
      panel.hidden = false;
      const copy = panel.querySelector(".panel-copy");
      copy.replaceChildren();
      const summary = document.createElement("p");
      const title = document.createElement("strong");
      title.textContent = block.querySelector("strong").textContent;
      summary.append(title, document.createElement("br"), block.querySelector("small").textContent);
      const link = document.createElement("a");
      link.className = "btn btn-primary";
      link.href = block.href;
      link.textContent = "Open and edit";
      copy.append(summary, link);
    });
  });
  panel.querySelector(".btn-close").addEventListener("click", () => {
    panel.hidden = true;
    blocks.forEach((block) => block.classList.remove("highlighted", "dimmed"));
  });
})();
