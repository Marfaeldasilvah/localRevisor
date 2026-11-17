(() => {
  const marker = document.querySelector("[data-pending]");
  if (!marker) {
    return;
  }

  let last = Number(marker.dataset.pending || "0");

  async function check() {
    try {
      const response = await fetch("/status", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      if (Number(data.pending) !== last) {
        window.location.reload();
        return;
      }
      last = Number(data.pending);
    } catch {
      // Rede momentaneamente indisponível: tenta de novo no próximo ciclo.
    }
  }

  window.setInterval(check, 3000);
})();
