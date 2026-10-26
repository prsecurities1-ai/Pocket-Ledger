(() => {
  const themeButtons = document.querySelectorAll(".theme-toggle");
  const themeKey = "pocketledger-theme";

  function setTheme(theme) {
    document.body.dataset.theme = theme;
    const isDark = theme === "dark";
    themeButtons.forEach((button) => {
      const icon = button.querySelector("i");
      if (icon) {
        icon.className = isDark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
      }
      button.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
      button.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");
    });
  }

  const storedTheme = localStorage.getItem(themeKey);
  setTheme(storedTheme === "dark" ? "dark" : "light");
  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = document.body.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(themeKey, nextTheme);
      setTheme(nextTheme);
    });
  });

  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const selectedTab = button.dataset.authTab;
      document.querySelectorAll(".auth-tab").forEach((tab) => {
        const active = tab.dataset.authTab === selectedTab;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", String(active));
      });
      document.querySelectorAll("[data-auth-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.authPanel === selectedTab);
      });
    });
  });

  const transactionModal = document.getElementById("transactionModal");
  const transactionForm = document.getElementById("transactionForm");
  const categorySelect = document.getElementById("transaction-category");
  const transactionTitle = document.getElementById("transactionModalTitle");
  const transactionSubmit = document.getElementById("transactionSubmit");

  function selectedKind() {
    return transactionForm.querySelector('input[name="kind"]:checked')?.value || "expense";
  }

  function updateCategoryOptions() {
    const kind = selectedKind();
    Array.from(categorySelect.options).forEach((option) => {
      if (!option.value) return;
      option.disabled = option.dataset.kind !== kind;
      option.hidden = option.dataset.kind !== kind;
    });
    const selected = categorySelect.selectedOptions[0];
    if (selected && selected.disabled) categorySelect.value = "";
  }

  transactionForm?.querySelectorAll('input[name="kind"]').forEach((radio) => {
    radio.addEventListener("change", updateCategoryOptions);
  });

  transactionModal?.addEventListener("show.bs.modal", (event) => {
    const editButton = event.relatedTarget?.closest(".edit-transaction");
    if (!editButton) {
      transactionForm.reset();
      transactionForm.action = "/transactions/add/";
      transactionTitle.textContent = "Add transaction";
      transactionSubmit.textContent = "Save transaction";
      transactionForm.querySelector('input[name="kind"][value="expense"]').checked = true;
      updateCategoryOptions();
      return;
    }
    transactionForm.action = `/transactions/${editButton.dataset.id}/edit/`;
    transactionTitle.textContent = "Edit transaction";
    transactionSubmit.textContent = "Save changes";
    transactionForm.querySelector(`input[name="kind"][value="${editButton.dataset.kind}"]`).checked = true;
    document.getElementById("transaction-title").value = editButton.dataset.title;
    document.getElementById("transaction-amount").value = editButton.dataset.amount;
    document.getElementById("transaction-date").value = editButton.dataset.date;
    document.getElementById("transaction-note").value = editButton.dataset.note;
    updateCategoryOptions();
    categorySelect.value = editButton.dataset.category;
  });

  transactionModal?.addEventListener("hidden.bs.modal", () => {
    transactionForm.reset();
    transactionForm.action = "/transactions/add/";
    updateCategoryOptions();
  });

  document.querySelectorAll("[data-confirm-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const transactionName = form.dataset.confirmDelete;
      if (!window.confirm(`Delete "${transactionName}"? This action cannot be undone.`)) {
        event.preventDefault();
      }
    });
  });

  const chartElement = document.getElementById("chart-data");
  if (!chartElement) return;
  const chartData = JSON.parse(chartElement.textContent);
  const dark = document.body.dataset.theme === "dark";
  const gridColor = dark ? "rgba(255,255,255,.07)" : "rgba(109,123,147,.10)";
  const tickColor = dark ? "#919bad" : "#99a4b4";
  const currencyLocale = chartData.currency_code === "INR" ? "en-IN" : "en-US";
  const formatCurrency = (amount, fractionDigits = 2) => {
    const formattedAmount = Number(amount).toLocaleString(currencyLocale, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    });
    return `${chartData.currency_symbol}${formattedAmount}`;
  };

  if (window.Chart && document.getElementById("cashflowChart")) {
    new Chart(document.getElementById("cashflowChart"), {
      type: "line",
      data: {
        labels: chartData.months,
        datasets: [
          {
            label: "Income",
            data: chartData.income,
            borderColor: "#28ad7e",
            backgroundColor: "rgba(40,173,126,.10)",
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: "#28ad7e",
            fill: true,
            tension: .38,
          },
          {
            label: "Expenses",
            data: chartData.expenses,
            borderColor: "#e5787d",
            backgroundColor: "rgba(229,120,125,.06)",
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: "#e5787d",
            fill: true,
            tension: .38,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { usePointStyle: true, pointStyle: "circle", boxWidth: 6, boxHeight: 6, color: tickColor, font: { size: 9 }, padding: 13 },
          },
          tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatCurrency(context.parsed.y)}` } },
        },
        scales: {
          x: { grid: { display: false }, border: { display: false }, ticks: { color: tickColor, font: { size: 9 } } },
          y: { beginAtZero: true, grid: { color: gridColor }, border: { display: false }, ticks: { color: tickColor, font: { size: 9 }, maxTicksLimit: 5, callback: (value) => formatCurrency(value, 0) } },
        },
      },
    });
  }

  const categoryCanvas = document.getElementById("categoryChart");
  if (window.Chart && categoryCanvas && chartData.category_labels.length) {
    const colors = ["#655de0", "#36b488", "#e9a74b", "#e7787b", "#62a6d8", "#a584d6"];
    new Chart(categoryCanvas, {
      type: "doughnut",
      data: {
        labels: chartData.category_labels,
        datasets: [{ data: chartData.category_values, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }],
      },
      options: {
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => ` ${formatCurrency(context.parsed)}` } } },
      },
    });
    const legend = document.getElementById("categoryLegend");
    chartData.category_labels.forEach((label, index) => {
      const item = document.createElement("div");
      item.className = "legend-item";
      const dot = document.createElement("span");
      dot.className = "legend-dot";
      dot.style.backgroundColor = colors[index % colors.length];
      const name = document.createElement("span");
      name.className = "legend-label";
      name.textContent = label;
      const amount = document.createElement("span");
      amount.className = "legend-value";
      amount.textContent = formatCurrency(chartData.category_values[index], 0);
      item.append(dot, name, amount);
      legend.append(item);
    });
  }
})();
