(() => {
  "use strict";

  const githubIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.72 1.27 3.39.97.1-.75.4-1.27.74-1.56-2.57-.29-5.28-1.29-5.28-5.69 0-1.26.45-2.28 1.2-3.09-.12-.29-.52-1.47.11-3.05 0 0 .97-.31 3.16 1.18A10.9 10.9 0 0 1 12 6.1c.98 0 1.96.13 2.87.39 2.2-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.76.11 3.05.75.81 1.2 1.83 1.2 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.25c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg>';

  document.querySelectorAll(".github-icon").forEach((node) => {
    node.innerHTML = githubIcon;
  });

  const setExpanded = (button, panel, expanded) => {
    button.setAttribute("aria-expanded", String(expanded));
    panel.classList.toggle("is-open", expanded);
  };

  const navToggle = document.querySelector(".nav-toggle");
  const mainNav = document.querySelector(".main-nav");
  if (navToggle && mainNav) {
    navToggle.addEventListener("click", () => {
      setExpanded(navToggle, mainNav, navToggle.getAttribute("aria-expanded") !== "true");
    });
    mainNav.addEventListener("click", (event) => {
      if (event.target.closest("a") && window.matchMedia("(max-width: 680px)").matches) {
        setExpanded(navToggle, mainNav, false);
      }
    });
  }

  const rqToggle = document.querySelector(".rq-toggle");
  const rqNav = document.querySelector(".rq-nav");
  const rqCurrent = document.querySelector("[data-rq-current]");
  if (rqToggle && rqNav && rqCurrent) {
    const links = [...rqNav.querySelectorAll("a[href^='#']")];
    const updateRqCurrent = (hash) => {
      const active = links.find((link) => link.hash === hash) || links[0];
      if (!active) return;
      rqCurrent.textContent = active.textContent.trim();
      links.forEach((link) => link.toggleAttribute("aria-current", link === active));
    };
    rqToggle.addEventListener("click", () => {
      setExpanded(rqToggle, rqNav, rqToggle.getAttribute("aria-expanded") !== "true");
    });
    links.forEach((link) => link.addEventListener("click", () => {
      updateRqCurrent(link.hash);
      setExpanded(rqToggle, rqNav, false);
    }));
    window.addEventListener("hashchange", () => updateRqCurrent(window.location.hash));
    updateRqCurrent(window.location.hash);

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        const visible = entries.find((entry) => entry.isIntersecting);
        if (visible) updateRqCurrent(`#${visible.target.id}`);
      }, { rootMargin: "-28% 0px -62%", threshold: 0 });
      links.forEach((link) => {
        const section = document.querySelector(link.hash);
        if (section) observer.observe(section);
      });
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (navToggle && mainNav) {
      const restoreNavFocus = mainNav.contains(document.activeElement);
      setExpanded(navToggle, mainNav, false);
      if (restoreNavFocus) navToggle.focus();
    }
    if (rqToggle && rqNav) {
      const restoreRqFocus = rqNav.contains(document.activeElement);
      setExpanded(rqToggle, rqNav, false);
      if (restoreRqFocus) rqToggle.focus();
    }
  });

  document.querySelectorAll(".copy-code").forEach((button) => {
    button.addEventListener("click", async () => {
      const shell = button.closest(".code-shell");
      const code = shell?.querySelector("code");
      if (!code) return;
      const value = code.textContent;
      try {
        await navigator.clipboard.writeText(value);
      } catch (_error) {
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.append(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
      }
      button.querySelector("[data-copy-default]")?.toggleAttribute("hidden", true);
      button.querySelector("[data-copy-success]")?.removeAttribute("hidden");
      window.setTimeout(() => {
        button.querySelector("[data-copy-default]")?.removeAttribute("hidden");
        button.querySelector("[data-copy-success]")?.toggleAttribute("hidden", true);
      }, 1600);
    });
  });

  document.querySelectorAll([
    ".table-wrap",
    ".traffic-table-wrap",
    ".formula-block",
    ".code-shell pre",
    ".table-scroll",
    ".canvas-scroll",
    ".beam-grid",
    ".tabs",
    ".raw-grid pre"
  ].join(",")).forEach((node) => {
    if (!node.hasAttribute("tabindex")) node.tabIndex = 0;
    node.dataset.scrollRegion = "true";
  });
})();
