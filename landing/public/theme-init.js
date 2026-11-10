// Applies the theme before first paint to avoid a flash. External file: the CSP forbids inline scripts.
(function () {
  var stored = null;
  try {
    stored = window.localStorage.getItem("asitech-landing-theme");
  } catch (e) {
    stored = null;
  }
  var dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (dark) document.documentElement.classList.add("dark");
})();
