(() => {
  "use strict";

  const navIcons = {
    overview: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h6v6H4zM14 5.5h6v6h-6zM4 15.5h6M14 15.5h6M4 19h6M14 19h6"/></svg>',
    problem: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="18" cy="17" r="2.5"/><path d="m8.3 10.9 7.4-2.8M8.3 13.1l7.4 2.8"/></svg>',
    method: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h8M5 12h14M11 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg>',
    evidence: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19V9M10 19V5M15 19v-7M20 19V3"/></svg>',
    reproduce: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 8-4 4 4 4M17 8l4 4-4 4M14 4l-4 16"/></svg>',
    demo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 7 8 5-8 5z"/></svg>'
  };
  const githubIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.72 1.27 3.39.97.1-.75.4-1.27.74-1.56-2.57-.29-5.28-1.29-5.28-5.69 0-1.26.45-2.28 1.2-3.09-.12-.29-.52-1.47.11-3.05 0 0 .97-.31 3.16 1.18A10.9 10.9 0 0 1 12 6.1c.98 0 1.96.13 2.87.39 2.2-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.76.11 3.05.75.81 1.2 1.83 1.2 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.25c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg>';

  document.querySelectorAll("[data-nav-icon]").forEach((node) => {
    const icon = navIcons[node.getAttribute("data-nav-icon")];
    if (icon) node.innerHTML = icon;
  });
  document.querySelectorAll(".github-icon").forEach((node) => {
    node.innerHTML = githubIcon;
  });
})();
