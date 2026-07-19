async function loadData() {
  const res = await fetch("data/history.json", { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

function formatDate(isoBrt) {
  const d = new Date(isoBrt);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function fillCards(prefix, queueData) {
  document.getElementById(`${prefix}-chall-lp`).textContent =
    queueData.challenger.cutoff_lp !== null ? `${queueData.challenger.cutoff_lp} LP` : "—";
  document.getElementById(`${prefix}-chall-meta`).textContent =
    `${queueData.challenger.player_count} jogadores`;

  document.getElementById(`${prefix}-gm-lp`).textContent =
    queueData.grandmaster.cutoff_lp !== null ? `${queueData.grandmaster.cutoff_lp} LP` : "—";
  document.getElementById(`${prefix}-gm-meta`).textContent =
    `${queueData.grandmaster.player_count} jogadores`;

  document.getElementById(`${prefix}-master-lp`).textContent =
    queueData.master.cutoff_lp !== null ? `${queueData.master.cutoff_lp} LP` : "—";
  document.getElementById(`${prefix}-master-meta`).textContent =
    `${queueData.master.player_count} jogadores`;
}

function drawChart(canvasId, history, queueKey, titleSuffix) {
  const labels = history.map((h) => formatDate(h.timestamp_brt));

  const ctx = document.getElementById(canvasId).getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Challenger (linha de corte)",
          data: history.map((h) => h.queues[queueKey].challenger.cutoff_lp),
          borderColor: "#f5a623",
          backgroundColor: "#f5a62333",
          tension: 0.25,
        },
        {
          label: "Grão-Mestre (linha de corte)",
          data: history.map((h) => h.queues[queueKey].grandmaster.cutoff_lp),
          borderColor: "#e5484d",
          backgroundColor: "#e5484d33",
          tension: 0.25,
        },
        {
          label: "Mestre (linha de corte)",
          data: history.map((h) => h.queues[queueKey].master.cutoff_lp),
          borderColor: "#a855f7",
          backgroundColor: "#a855f733",
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#e6edf3" } },
        title: {
          display: true,
          text: `Evolução da linha de corte (LP) — ${titleSuffix}`,
          color: "#e6edf3",
        },
      },
      scales: {
        x: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" } },
        y: { ticks: { color: "#8b949e" }, grid: { color: "#30363d" } },
      },
    },
  });
}

(async function init() {
  const history = await loadData();

  if (!history.length) {
    document.getElementById("empty-state").hidden = false;
    document.getElementById("last-update").textContent = "Sem dados ainda.";
    return;
  }

  const latest = history[history.length - 1];

  fillCards("solo", latest.queues.solo);
  fillCards("flex", latest.queues.flex);

  document.getElementById("last-update").textContent =
    `Última atualização: ${new Date(latest.timestamp_brt).toLocaleString("pt-BR")} (horário de Brasília)`;

  drawChart("soloChart", history, "solo", "Solo/Duo BR");
  drawChart("flexChart", history, "flex", "Flex BR");
})();
