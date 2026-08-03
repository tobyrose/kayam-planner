(() => {
  const table = document.querySelector(".roster-board");
  if (!table) return;
  const boardStart = table.dataset.boardStart || "";

  table.querySelectorAll(".roster-chip").forEach((chip) => {
    chip.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", chip.dataset.crewMemberId);
      event.dataTransfer.effectAllowed = "move";
    });
  });

  table.querySelectorAll(".roster-drop-cell").forEach((cell) => {
    cell.addEventListener("dragover", (event) => {
      event.preventDefault();
      cell.classList.add("drop-target");
    });
    cell.addEventListener("dragleave", () => {
      cell.classList.remove("drop-target");
    });
    cell.addEventListener("drop", async (event) => {
      event.preventDefault();
      cell.classList.remove("drop-target");
      const crewMemberId = event.dataTransfer.getData("text/plain");
      if (!crewMemberId) return;
      const params = new URLSearchParams({
        board_start: boardStart,
        crew_member_id: crewMemberId,
        to_tentmaster_id: cell.dataset.tentmasterId || "",
        effective_date: cell.dataset.date,
      });
      const response = await fetch("/planning/roster/move", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
      });
      window.location.href = response.url;
    });
  });
})();
