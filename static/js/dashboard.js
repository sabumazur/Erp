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
    var statusTotal = stCounts.reduce(function (total, count) {
      return total + Number(count || 0);
    }, 0);

    var statusCenterText = {
      id: "statusCenterText",
      afterDraw: function (chart) {
        if (chart.canvas.id !== "statusChart" || !statusTotal) return;
        var meta = chart.getDatasetMeta(0);
        var arc = meta && meta.data && meta.data[0];
        if (!arc) return;

        var ctx = chart.ctx;
        var centerX = arc.x;
        var centerY = arc.y;

        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#0F172A";
        ctx.font = "700 1.15rem 'IBM Plex Mono', 'Courier New', monospace";
        ctx.fillText(String(statusTotal), centerX, centerY - 6);
        ctx.fillStyle = "#6b7280";
        ctx.font = "700 .58rem Inter, sans-serif";
        ctx.fillText(getConfig("chartStatusTotalLabel", "Facturas").toUpperCase(), centerX, centerY + 15);
        ctx.restore();
      },
    };

    var spCanvas = document.getElementById("salesPurchasesChart");
    if (spCanvas) {
      var spDatasets = [
        { label: getConfig("chartInvoicedLabel", "Facturado"), data: invoiced, backgroundColor: "rgba(37,99,235,0.75)", borderRadius: 4 },
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
          { label: getConfig("chartInvoicedLabel", "Facturado"), data: invoiced, backgroundColor: "rgba(37,99,235,0.75)", borderRadius: 4 },
          { label: getConfig("chartCollectedLabel", "Cobrado"), data: collected, backgroundColor: "rgba(5,150,105,0.75)", borderRadius: 4 },
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
        data: {
          labels: stLabels,
          datasets: [{
            data: stCounts,
            backgroundColor: stColors,
            borderColor: "#fff",
            borderWidth: 3,
            hoverOffset: 5,
          }],
        },
        options: {
          responsive: true,
          cutout: "64%",
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                boxWidth: 8,
                boxHeight: 8,
                padding: 12,
                usePointStyle: true,
                pointStyle: "circle",
              },
            },
          },
        },
        plugins: [statusCenterText],
      });
    } else {
      replaceChartPanel("statusChart", getConfig("chartNoInvoicesText", "Sin facturas registradas."));
    }

    var agCanvas = document.getElementById("arApAgingChart");
    if (agCanvas) {
      var agDatasets = [
        { label: getConfig("chartARLabel", "Por cobrar"), data: arAging, backgroundColor: "rgba(37,99,235,0.78)", borderRadius: 4 },
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
