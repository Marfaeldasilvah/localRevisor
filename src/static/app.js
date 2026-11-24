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

document.querySelectorAll("[data-model-field]").forEach((field) => {
  const select = field.querySelector("[data-model-select]");
  const customInput = field.querySelector("[data-model-custom]");
  if (!select || !customInput) return;

  const sync = (focusCustom) => {
    const isCustom = select.value === "__custom__";
    customInput.hidden = !isCustom;
    customInput.required = isCustom && select.required;
    if (isCustom && focusCustom) {
      customInput.focus();
    } else if (!isCustom) {
      customInput.value = "";
    }
  };

  sync(false);
  select.addEventListener("change", () => sync(true));
});
