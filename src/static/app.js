document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-confirm]");
  if (form && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
  }
});

const menuToggle = document.getElementById("menu-toggle");
const menuClose = document.getElementById("menu-close");
const appMenu = document.getElementById("app-menu");
const menuBackdrop = document.getElementById("menu-backdrop");

function setMenuOpen(open) {
  if (!menuToggle || !appMenu || !menuBackdrop) return;
  appMenu.classList.toggle("app-menu--open", open);
  appMenu.setAttribute("aria-hidden", String(!open));
  menuToggle.setAttribute("aria-expanded", String(open));
  menuToggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
  menuBackdrop.hidden = !open;
  document.body.classList.toggle("menu-open", open);
}

menuToggle?.addEventListener("click", () => {
  setMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true");
});
menuClose?.addEventListener("click", () => setMenuOpen(false));
menuBackdrop?.addEventListener("click", () => setMenuOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});
