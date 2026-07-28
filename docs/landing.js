"use strict";

const year = document.getElementById("year");
const copyButton = document.getElementById("copy-command");
const setupCommand = document.getElementById("setup-command");

if (year) {
  year.textContent = String(new Date().getFullYear());
}

if (copyButton && setupCommand) {
  copyButton.addEventListener("click", async () => {
    const label = copyButton.querySelector(".copy-label");
    try {
      await navigator.clipboard.writeText(setupCommand.textContent);
      if (label) label.textContent = "Copied";
      window.setTimeout(() => {
        if (label) label.textContent = "Copy";
      }, 1600);
    } catch {
      if (label) label.textContent = "Select text";
    }
  });
}
