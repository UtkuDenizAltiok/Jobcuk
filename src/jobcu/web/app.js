"use strict";

async function showAbout() {
  const status = document.getElementById("engine-status");
  try {
    const response = await fetch("/api/about");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const about = await response.json();

    document.getElementById("version").textContent = `Jobcu ${about.version}`;
    document.getElementById("copyright").textContent = about.copyright;
    document.getElementById("data-folder-path").textContent = about.data_folder;
    document.getElementById("data-folder").hidden = false;

    status.textContent = "Jobcu's engine is working";
    status.className = "status ok";
  } catch {
    status.textContent =
      "Jobcu's engine isn't answering. Close this page, then double-click Start Jobcu again.";
    status.className = "status problem";
  }
}

showAbout();
