const syncButton = document.getElementById("syncButton");
const syncState = document.getElementById("syncState");
const feedList = document.getElementById("feedList");
const navItems = document.querySelectorAll(".nav-item");
const actionCards = document.querySelectorAll(".action-card");

syncButton?.addEventListener("click", () => {
  syncState.textContent = "Synchronisation...";
  syncButton.disabled = true;

  window.setTimeout(() => {
    syncState.textContent = "Synchronise";
    syncButton.disabled = false;
    prependFeed("Systeme", "Les donnees du serveur ont ete mises a jour avec succes.");
  }, 1400);
});

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    navItems.forEach((button) => button.classList.remove("active"));
    item.classList.add("active");

    const targetId = item.dataset.panel;
    const target = document.getElementById(targetId);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

actionCards.forEach((card) => {
  card.addEventListener("click", () => {
    const label = card.querySelector("strong")?.textContent ?? "Action";
    prependFeed("Automatisation", `${label} a ete lance depuis le panel.`);
  });
});

function prependFeed(title, message) {
  const entry = document.createElement("div");
  entry.className = "feed-item";
  entry.innerHTML = `<strong>${title}</strong><p>${message}</p>`;
  feedList?.prepend(entry);
}
