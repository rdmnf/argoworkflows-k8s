(function () {
    const panel = document.getElementById("namespace-panel");
    const toggleButton = document.getElementById("toggle-namespaces");
    const statCard = document.getElementById("namespace-stat-card");

    if (!panel) {
        return;
    }

    function setExpanded(expanded) {
        panel.hidden = !expanded;

        if (toggleButton) {
            toggleButton.setAttribute("aria-expanded", String(expanded));
            toggleButton.textContent = expanded ? "Hide namespaces" : "Browse namespaces";
        }

        if (statCard) {
            statCard.setAttribute("aria-expanded", String(expanded));
            statCard.classList.toggle("is-open", expanded);
        }
    }

    function togglePanel() {
        setExpanded(panel.hidden);
    }

    if (toggleButton) {
        toggleButton.addEventListener("click", togglePanel);
    }

    if (statCard) {
        statCard.addEventListener("click", togglePanel);
        statCard.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                togglePanel();
            }
        });
    }

    if (window.location.hash === "#namespaces") {
        setExpanded(true);
    }
})();
