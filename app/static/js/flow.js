(() => {
  const svg = document.querySelector("#flow-edges");
  if (!svg) return;
  const panel = document.querySelector("#board-panel");
  if (!panel) return;
  const edges = [...svg.querySelectorAll(".flow-edge")];

  edges.forEach((edge) => {
    edge.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey) return;
      event.preventDefault();
      edges.forEach((candidate) => candidate.classList.remove("highlighted"));
      edge.classList.add("highlighted");
      panel.hidden = false;
      const copy = panel.querySelector(".panel-copy");
      copy.replaceChildren();
      const summary = document.createElement("p");
      const title = document.createElement("strong");
      title.textContent = edge.dataset.label;
      summary.append(title, document.createElement("br"), edge.dataset.subtitle);
      const link = document.createElement("a");
      link.className = "btn btn-primary";
      link.href = edge.getAttribute("href");
      link.textContent = "Open load";
      copy.append(summary, link);
    });
  });
  panel.querySelector(".btn-close").addEventListener("click", () => {
    panel.hidden = true;
    edges.forEach((candidate) => candidate.classList.remove("highlighted"));
  });
})();
