(function () {
  "use strict";

  function replaceChartPanel(canvasId, text) {
    var canvas = document.getElementById(canvasId);
    var panel = canvas && canvas.closest(".db-panel-body");
    if (panel) panel.innerHTML = '<p class="text-muted small text-center py-3 mb-0">' + escapeHtml(text) + "</p>";
  }

  function initDashboardCharts() {
    if (!window.Chart || !document.getElementById("revenueChart")) return;

    var months = parseJsonScript("chart-months", []);
    var invoiced = parseJsonScript("chart-invoiced", []);
    var collected = parseJsonScript("chart-collected", []);
    var stLabels = parseJsonScript("chart-status-labels", []);
    var stCounts = parseJsonScript("chart-status-counts", []);
    var stColors = parseJsonScript("chart-status-colors", []);
    var custDatasets = parseJsonScript("chart-customer-datasets", []);

    new Chart(document.getElementById("revenueChart"), {
      type: "bar",
      data: {
        labels: months,
        datasets: [
          { label: getConfig("chartInvoicedLabel", "Facturado"), data: invoiced, backgroundColor: "rgba(13,110,253,0.75)", borderRadius: 4 },
          { label: getConfig("chartCollectedLabel", "Cobrado"), data: collected, backgroundColor: "rgba(25,135,84,0.75)", borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
      },
    });

    if (stCounts.length) {
      new Chart(document.getElementById("statusChart"), {
        type: "doughnut",
        data: { labels: stLabels, datasets: [{ data: stCounts, backgroundColor: stColors, borderWidth: 2 }] },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } } },
      });
    } else {
      replaceChartPanel("statusChart", getConfig("chartNoInvoicesText", "Sin facturas registradas."));
    }

    if (custDatasets.length) {
      new Chart(document.getElementById("customerChart"), {
        type: "bar",
        data: { labels: months, datasets: custDatasets },
        options: {
          responsive: true,
          plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
        },
      });
    } else {
      replaceChartPanel("customerChart", getConfig("chartNoCustomerDataText", "Sin datos de clientes."));
    }
  }

  window.initDashboardCharts = initDashboardCharts;
})();
