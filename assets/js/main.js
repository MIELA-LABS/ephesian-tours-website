/* Ephesian Tours: progressive enhancements (the page works without JS). */
(function () {
  "use strict";

  var doc = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ---------- Mobile navigation ---------- */
  var toggle = $("[data-nav-toggle]");
  var nav = $("[data-nav]");
  function setNav(open) {
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", String(open));
    nav.classList.toggle("is-open", open);
  }
  if (toggle && nav) {
    toggle.addEventListener("click", function () { setNav(toggle.getAttribute("aria-expanded") !== "true"); });
    $$("a", nav).forEach(function (a) { a.addEventListener("click", function () { setNav(false); }); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") { setNav(false); toggle.focus(); }
    });
  }

  /* ---------- Theme toggle (light / dark, remembered per browser) ---------- */
  var themeBtn = $("[data-theme-toggle]");
  function effectiveTheme() {
    if (doc.dataset.theme) return doc.dataset.theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function labelTheme() {
    if (themeBtn) themeBtn.setAttribute("aria-label", effectiveTheme() === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  if (themeBtn) {
    labelTheme();
    themeBtn.addEventListener("click", function () {
      var next = effectiveTheme() === "dark" ? "light" : "dark";
      doc.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* storage unavailable */ }
      labelTheme();
    });
  }

  /* ---------- Scroll reveal + current section in nav ---------- */
  var reveals = $$(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  var navLinks = $$("[data-nav-link]");
  if ("IntersectionObserver" in window && navLinks.length) {
    var byId = {};
    navLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var link = byId[e.target.id];
        if (!link) return;
        if (e.isIntersecting) {
          navLinks.forEach(function (a) { a.removeAttribute("aria-current"); });
          link.setAttribute("aria-current", "true");
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(byId).forEach(function (id) { var s = document.getElementById(id); if (s) spy.observe(s); });
  }

  /* ---------- Mobile "Plan a Trip" button: hidden while the hero (own CTAs) or the form is on screen ---------- */
  var mobileCta = $(".mobile-cta");
  var contact = document.getElementById("contact");
  var hero = document.getElementById("top");
  if (mobileCta && "IntersectionObserver" in window) {
    var onScreen = {};
    var ctaObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { onScreen[e.target.id] = e.isIntersecting; });
      mobileCta.classList.toggle("is-hidden", !!(onScreen.top || onScreen.contact));
    }, { threshold: 0.05 });
    [hero, contact].forEach(function (el) { if (el) ctaObserver.observe(el); });
  }

  /* ---------- Route maps (Leaflet loaded on first itinerary open) ---------- */
  var LEAFLET = {
    css: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
    cssSri: "sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw==",
    js: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
    jsSri: "sha512-puJW3E/qXDqYp9IfhAI54BJEaWIfloJ7JWs7OeD5i6ruC9JZL1gERT1wjtwXFlh7CjE7ZJ+/vcRZRkIYIb6p4g=="
  };
  var routes = {};
  try { routes = JSON.parse($("#route-data").textContent); } catch (e) { /* no maps */ }
  var leafletPromise = null;

  function loadLeaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (leafletPromise) return leafletPromise;
    leafletPromise = new Promise(function (resolve, reject) {
      var link = document.createElement("link");
      link.rel = "stylesheet"; link.href = LEAFLET.css; link.integrity = LEAFLET.cssSri; link.crossOrigin = "anonymous";
      document.head.appendChild(link);
      var s = document.createElement("script");
      s.src = LEAFLET.js; s.integrity = LEAFLET.jsSri; s.crossOrigin = "anonymous";
      s.onload = function () { resolve(window.L); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return leafletPromise;
  }

  function cssVar(name) { return getComputedStyle(doc).getPropertyValue(name).trim(); }

  function drawMap(el) {
    if (el.dataset.ready) return;
    el.dataset.ready = "1";
    var stops = routes[el.dataset.map] || [];
    loadLeaflet().then(function (L) {
      el.textContent = "";
      var map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.25 });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);

      var road = cssVar("--primary") || "#1F4E79";
      var accent = cssVar("--accent") || "#A3471F";
      var bounds = [];
      stops.forEach(function (p, i) {
        var ll = [p.lat, p.lng];
        bounds.push(ll);
        if (i > 0) {
          var prev = stops[i - 1];
          L.polyline([[prev.lat, prev.lng], ll], {
            color: p.by === "road" ? road : accent,
            weight: 3, opacity: 0.9,
            dashArray: p.by === "road" ? null : "6 8"
          }).addTo(map);
        }
      });
      var seen = {};
      stops.forEach(function (p) {
        if (seen[p.name]) return;
        seen[p.name] = true;
        L.circleMarker([p.lat, p.lng], {
          radius: p.stop ? 4 : 6.5, weight: 2,
          color: p.stop ? road : "#FFFFFF",
          fillColor: p.stop ? "#FFFFFF" : accent, fillOpacity: 1
        }).bindTooltip(p.name, { className: "route-label", direction: "top", offset: [0, -6] }).addTo(map);
      });
      if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
      setTimeout(function () { map.invalidateSize(); }, 50);
    }).catch(function () {
      el.dataset.ready = "";
      var p = $(".route__fallback", el);
      if (p) p.textContent = "The map could not be loaded. Please check your connection and try again.";
    });
  }

  $$("details.itinerary").forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) { var el = $("[data-map]", d); if (el) drawMap(el); }
    });
  });

  /* ---------- Vimeo: click-to-play (nothing loads from Vimeo before the click) ---------- */
  $$("[data-vimeo]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = document.createElement("div");
      wrap.className = "video__frame";
      var iframe = document.createElement("iframe");
      iframe.src = "https://player.vimeo.com/video/" + encodeURIComponent(btn.dataset.vimeo) +
        "?autoplay=1&dnt=1&title=0&byline=0&portrait=0";
      iframe.title = btn.dataset.title || "Video";
      iframe.allow = "autoplay; fullscreen; picture-in-picture";
      iframe.allowFullscreen = true;
      wrap.appendChild(iframe);
      btn.replaceWith(wrap);
      iframe.focus();
    });
  });

  /* ---------- Contact form helpers ---------- */
  var form = $("[data-form]");
  var journeySelect = $("[data-journey-select]");
  var packetCheck = $("[data-packet-check]");

  function goToForm(focusEl) {
    contact.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    setTimeout(function () { (focusEl || $("#f-name")).focus({ preventScroll: true }); }, reduceMotion ? 0 : 500);
  }

  $$("[data-journey-cta]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      if (!journeySelect) return;
      e.preventDefault();
      journeySelect.value = a.dataset.journeyCta;
      goToForm();
    });
  });

  var packetBtn = $("[data-packet]");
  if (packetBtn && packetCheck) {
    packetBtn.addEventListener("click", function () {
      packetCheck.checked = true;
      goToForm();
    });
  }

  if (form) {
    var status = $("[data-form-status]", form);
    function say(text, isError, withEmail) {
      status.textContent = "";
      var p = document.createElement("p");
      if (isError) p.className = "is-error";
      p.appendChild(document.createTextNode(text + (withEmail ? " " : "")));
      if (withEmail) {
        var a = document.createElement("a");
        a.href = "mailto:" + status.dataset.email;
        a.textContent = status.dataset.email;
        p.appendChild(a);
      }
      status.appendChild(p);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var firstBad = null;
      $$("[required]", form).forEach(function (f) {
        var ok = f.value.trim() !== "" && (f.type !== "email" || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.value.trim()));
        f.setAttribute("aria-invalid", ok ? "false" : "true");
        if (!ok && !firstBad) firstBad = f;
      });
      if (firstBad) {
        say("Please add your name and a valid email address so we can reply.", true, false);
        firstBad.focus();
        return;
      }
      if (form.dataset.formLive !== "true") {
        say(status.dataset.fallback, false, true);
        return;
      }
      var btn = $("button[type=submit]", form);
      btn.disabled = true;
      fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } })
        .then(function (r) {
          if (!r.ok) throw new Error(String(r.status));
          form.reset();
          say(status.dataset.success, false, false);
        })
        .catch(function () { say(status.dataset.error, true, true); })
        .then(function () { btn.disabled = false; });
    });
  }
})();
