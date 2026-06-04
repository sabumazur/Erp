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
    var purchased = parseJsonScript("chart-purchased", []);
    var agingLabels = parseJsonScript("chart-aging-labels", []);
    var arAging = parseJsonScript("chart-ar-aging", []);
    var apAging = parseJsonScript("chart-ap-aging", []);

    var spCanvas = document.getElementById("salesPurchasesChart");
    if (spCanvas) {
      var spDatasets = [
        { label: getConfig("chartInvoicedLabel", "Facturado"), data: invoiced, backgroundColor: "rgba(13,110,253,0.75)", borderRadius: 4 },
      ];
      if (getConfig("hasPurchasingAccess", false)) {
        spDatasets.push({ label: getConfig("chartPurchasedLabel", "Comprado"), data: purchased, backgroundColor: "rgba(245,158,11,0.78)", borderRadius: 4 });
      }
      new Chart(spCanvas, {
        type: "bar",
        data: { labels: months, datasets: spDatasets },
        options: {
          responsive: true,
          plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
          scales: { y: { beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
        },
      });
    }

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

    var agCanvas = document.getElementById("arApAgingChart");
    if (agCanvas) {
      var agDatasets = [
        { label: getConfig("chartARLabel", "Por cobrar"), data: arAging, backgroundColor: "rgba(63,111,214,0.78)", borderRadius: 4 },
      ];
      if (getConfig("hasPurchasingAccess", false)) {
        agDatasets.push({ label: getConfig("chartAPLabel", "Por pagar"), data: apAging, backgroundColor: "rgba(217,119,6,0.80)", borderRadius: 4 });
      }
      new Chart(agCanvas, {
        type: "bar",
        data: { labels: agingLabels, datasets: agDatasets },
        options: {
          responsive: true,
          plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
          scales: { y: { beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
        },
      });
    }
  }

  window.initDashboardCharts = initDashboardCharts;
})();
