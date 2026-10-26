/* Runtime compartido: sidebar + busqueda desde LESSONS,
   tema claro/oscuro, menu mobile y notas por leccion.
   Espera BASE_PREFIX ("" en la raiz, "../../" desde lessons/x/) y lessons-data.js
   (SITE, PHASE_ORDER, LESSONS). Sin fetch(): funciona abriendo el archivo con file://. */

(function () {
  const prefix = typeof BASE_PREFIX === "string" ? BASE_PREFIX : "";
  const siteId = SITE.id;

  function lessonHref(l) { return prefix + "lessons/" + l.dir + "/index.html"; }
  function isActive(l) { return !!l.dir && document.location.pathname.indexOf("/lessons/" + l.dir + "/") !== -1; }
  function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

  /* Flag de "finalizada" por leccion. localStorage es la fuente primaria (sincrona,
     disponible de inmediato); si ya hay una carpeta notes/ conectada (ver setupNotes),
     se sincroniza tambien a notes/progress.json en esa misma carpeta. */
  const DONE_PREFIX = siteId + "-done-";
  function isDone(dir) {
    if (!dir) return false;
    try { return localStorage.getItem(DONE_PREFIX + dir) === "1"; } catch (e) { return false; }
  }
  function setDoneLocal(dir, val) {
    try {
      if (val) localStorage.setItem(DONE_PREFIX + dir, "1");
      else localStorage.removeItem(DONE_PREFIX + dir);
    } catch (e) {}
  }
  window.sdIsDone = isDone;

  function buildSidebar() {
    const nav = document.getElementById("sidebar");
    if (!nav) return;

    const brand = document.createElement("div");
    brand.className = "sidebar-brand";
    brand.innerHTML =
      '<a href="' + prefix + 'index.html">' + esc(SITE.title) + '</a>';
    nav.appendChild(brand);
    nav.appendChild(buildThemeSelect());

    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Buscar leccion o tema...";
    search.className = "search-box";
    nav.appendChild(search);

    const list = document.createElement("nav");
    PHASE_ORDER.forEach(function (phase) {
      const inPhase = LESSONS.filter(function (l) { return l.phase === phase; });
      if (!inPhase.length) return;
      const label = document.createElement("div");
      label.className = "sidebar-cat";
      label.textContent = phase;
      list.appendChild(label);

      const ul = document.createElement("ul");
      inPhase.forEach(function (l) {
        const li = document.createElement("li");
        li.dataset.search = (l.num + " " + l.title + " " + l.summaryText).toLowerCase();
        const numHtml = '<span class="num">' + l.num + '</span>';
        if (l.ready) {
          const a = document.createElement("a");
          a.href = lessonHref(l);
          if (isActive(l)) a.className = "active";
          a.innerHTML = numHtml + esc(l.title) +
            (isDone(l.dir) ? '<span class="done-check" title="Finalizada">&check;</span>' : "");
          li.appendChild(a);
        } else {
          const span = document.createElement("span");
          span.className = "pending-item";
          span.title = "Pendiente de armar";
          span.innerHTML = numHtml + esc(l.title);
          li.appendChild(span);
        }
        ul.appendChild(li);
      });
      list.appendChild(ul);
    });
    nav.appendChild(list);

    const noResults = document.createElement("div");
    noResults.className = "no-results";
    noResults.textContent = "Sin resultados.";
    nav.appendChild(noResults);

    search.addEventListener("input", function () {
      const q = search.value.trim().toLowerCase();
      let anyVisible = false;
      list.querySelectorAll("li").forEach(function (li) {
        const match = !q || li.dataset.search.indexOf(q) !== -1;
        li.style.display = match ? "" : "none";
        if (match) anyVisible = true;
      });
      list.querySelectorAll(".sidebar-cat").forEach(function (label) {
        const sib = label.nextElementSibling;
        const visible = sib && Array.from(sib.querySelectorAll("li")).some(function (li) { return li.style.display !== "none"; });
        label.style.display = visible ? "" : "none";
      });
      noResults.style.display = anyVisible ? "none" : "block";
    });
  }

  /* Temas disponibles. "musica-theme" en localStorage persiste la eleccion
     entre paginas y entre cursos (todos comparten origen en file://). */
  const THEMES = [
    { value: "dark", label: "Oscuro (Dracula)" },
    { value: "light", label: "Claro" },
    { value: "dracula", label: "Dracula" },
    { value: "synthwave", label: "Synthwave" },
    { value: "vaporwave", label: "Vaporwave" },
    { value: "nineties", label: "90s" },
    { value: "nightcity", label: "Night City" },
    { value: "acid", label: "Acid" },
  ];
  const THEME_KEY = "musica-theme";

  function getStoredTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
  }
  function setStoredTheme(v) {
    try { localStorage.setItem(THEME_KEY, v); } catch (e) {}
  }
  function applyTheme(v) {
    document.documentElement.setAttribute("data-theme", v);
  }

  function setupTheme() {
    const stored = getStoredTheme();
    if (stored) applyTheme(stored);
  }

  function buildThemeSelect() {
    const wrap = document.createElement("div");
    wrap.className = "theme-select-wrap";
    const select = document.createElement("select");
    select.className = "theme-select";
    select.id = "theme-select";
    select.title = "Cambiar tema";
    THEMES.forEach(function (t) {
      const opt = document.createElement("option");
      opt.value = t.value;
      opt.textContent = t.label;
      select.appendChild(opt);
    });
    const current = getStoredTheme() || document.documentElement.getAttribute("data-theme") || "dark";
    select.value = current;
    select.addEventListener("change", function () {
      applyTheme(select.value);
      setStoredTheme(select.value);
    });
    wrap.appendChild(select);
    return wrap;
  }

  function setupMobileToggle() {
    const btn = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("sidebar");
    if (!btn || !sidebar) return;
    btn.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    document.addEventListener("click", function (e) {
      if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && e.target !== btn) {
        sidebar.classList.remove("open");
      }
    });
  }

  function lessonDirFromPath() {
    const m = document.location.pathname.match(/\/lessons\/([^/]+)\/?/);
    return m ? m[1] : null;
  }

  /* IndexedDB minimo para recordar la carpeta notes/ entre paginas.
     Namespaced por sitio: en file:// todos los archivos comparten origen,
     asi distintos cursos no se pisan la carpeta de notas. */
  const IDB_NAME = "notes-db-" + siteId;
  function idbOpen() {
    return new Promise(function (resolve, reject) {
      const req = indexedDB.open(IDB_NAME, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore("kv"); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }
  function idbGet(key) {
    return idbOpen().then(function (db) {
      return new Promise(function (resolve) {
        const r = db.transaction("kv", "readonly").objectStore("kv").get(key);
        r.onsuccess = function () { resolve(r.result || null); };
        r.onerror = function () { resolve(null); };
      });
    }).catch(function () { return null; });
  }
  function idbSet(key, value) {
    return idbOpen().then(function (db) {
      return new Promise(function (resolve) {
        const r = db.transaction("kv", "readwrite").objectStore("kv").put(value, key);
        r.onsuccess = function () { resolve(true); };
        r.onerror = function () { resolve(false); };
      });
    }).catch(function () { return false; });
  }

  function setupNotes() {
    const dir = lessonDirFromPath();
    if (!dir || !document.querySelector(".chapter-meta")) return;

    const localKey = siteId + "-notes-" + dir;
    let saved = "";
    try { saved = localStorage.getItem(localKey) || ""; } catch (e) {}

    const btn = document.createElement("button");
    btn.className = "notes-toggle";
    btn.title = "Notas de esta leccion";
    btn.setAttribute("aria-label", "Notas de esta leccion");
    btn.textContent = "✎";
    if (saved.trim()) btn.classList.add("has-notes");

    const panel = document.createElement("div");
    panel.className = "notes-panel";
    panel.innerHTML =
      '<div class="notes-panel-head"><span>Mis notas</span><button class="notes-close" aria-label="Cerrar notas">&times;</button></div>' +
      '<div class="notes-file-status"></div>' +
      '<textarea class="notes-textarea" placeholder="Notas, dudas y respuestas a las preguntas de entrevista de esta leccion"></textarea>';
    document.body.appendChild(btn);
    document.body.appendChild(panel);

    const textarea = panel.querySelector(".notes-textarea");
    const closeBtn = panel.querySelector(".notes-close");
    const statusEl = panel.querySelector(".notes-file-status");
    textarea.value = saved;
    if (saved.trim()) panel.classList.add("open");

    const supportsFS = typeof window.showDirectoryPicker === "function";
    const NOTES_FILENAME = "notes.json";
    let fileHandle = null, fileData = null, fileMode = false, writeTimer = null, localTimer = null;

    function renderStatus() {
      if (!supportsFS) { statusEl.textContent = "Guardado en este navegador (localStorage)."; return; }
      if (fileMode) {
        statusEl.innerHTML = "Guardado en <strong>" + esc(siteId) + "/notes/notes.json</strong>.";
      } else {
        statusEl.innerHTML = '<button class="notes-connect">Elegir carpeta ' + esc(siteId) + '/notes/…</button>';
        statusEl.querySelector(".notes-connect").addEventListener("click", connectFolder);
      }
    }
    function writeFile() {
      if (!fileHandle || !fileData) return;
      clearTimeout(writeTimer);
      writeTimer = setTimeout(function () {
        fileHandle.createWritable().then(function (w) {
          return w.write(JSON.stringify(fileData, null, 2)).then(function () { return w.close(); });
        }).catch(function () {});
      }, 400);
    }
    function enterFileMode(handle, data) {
      fileHandle = handle;
      fileData = data && typeof data === "object" ? data : {};
      fileMode = true;
      renderStatus();
      if (typeof fileData[dir] === "string") {
        textarea.value = fileData[dir];
      } else if (textarea.value.trim()) {
        fileData[dir] = textarea.value; // migra lo que habia en localStorage
        writeFile();
      }
      btn.classList.toggle("has-notes", !!textarea.value.trim());
      if (textarea.value.trim()) panel.classList.add("open");
    }
    function loadFromDirHandle(dirHandle) {
      return dirHandle.getFileHandle(NOTES_FILENAME, { create: true }).then(function (fh) {
        return fh.getFile().then(function (f) { return f.text(); }).then(function (text) {
          let data = {};
          try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
          enterFileMode(fh, data);
        });
      });
    }
    function connectFolder() {
      window.showDirectoryPicker({ mode: "readwrite", id: "notes-" + siteId }).then(function (dirHandle) {
        return idbSet("dirHandle", dirHandle).then(function () { return dirHandle; });
      }).then(loadFromDirHandle).catch(function () {});
    }

    if (supportsFS) {
      idbGet("dirHandle").then(function (dirHandle) {
        if (!dirHandle) { renderStatus(); return; }
        dirHandle.queryPermission({ mode: "readwrite" }).then(function (state) {
          if (state === "granted") {
            loadFromDirHandle(dirHandle).catch(function () { renderStatus(); });
          } else {
            statusEl.innerHTML = '<button class="notes-connect">Reconectar carpeta notes/…</button>';
            statusEl.querySelector(".notes-connect").addEventListener("click", function () {
              dirHandle.requestPermission({ mode: "readwrite" }).then(function (s2) {
                if (s2 === "granted") loadFromDirHandle(dirHandle);
              });
            });
          }
        });
      });
    } else {
      renderStatus();
    }

    textarea.addEventListener("input", function () {
      btn.classList.toggle("has-notes", !!textarea.value.trim());
      clearTimeout(localTimer);
      localTimer = setTimeout(function () {
        try { localStorage.setItem(localKey, textarea.value); } catch (e) {}
      }, 300);
      if (fileMode) { fileData[dir] = textarea.value; writeFile(); }
    });
    btn.addEventListener("click", function () {
      panel.classList.toggle("open");
      if (panel.classList.contains("open")) textarea.focus();
    });
    closeBtn.addEventListener("click", function () { panel.classList.remove("open"); });
  }

  function setupDone() {
    const dir = lessonDirFromPath();
    const holder = document.querySelector(".lesson-done");
    if (!dir || !holder) return;

    const btn = document.createElement("button");
    btn.className = "lesson-done-btn";

    function render() {
      const done = isDone(dir);
      btn.classList.toggle("done", done);
      btn.innerHTML = done ? "&check; Lecci\u00f3n finalizada" : "&#9744; Marcar como finalizada";
    }
    render();
    holder.appendChild(btn);

    function syncToFile(done) {
      idbGet("dirHandle").then(function (dirHandle) {
        if (!dirHandle) return;
        return dirHandle.queryPermission({ mode: "readwrite" }).then(function (state) {
          if (state !== "granted") return;
          return dirHandle.getFileHandle("progress.json", { create: true }).then(function (fh) {
            return fh.getFile().then(function (f) { return f.text(); }).then(function (text) {
              let data = {};
              try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
              if (done) data[dir] = true; else delete data[dir];
              return fh.createWritable().then(function (w) {
                return w.write(JSON.stringify(data, null, 2)).then(function () { return w.close(); });
              });
            });
          });
        });
      }).catch(function () {});
    }

    btn.addEventListener("click", function () {
      const next = !isDone(dir);
      setDoneLocal(dir, next);
      render();
      syncToFile(next);
      const active = document.querySelector(".sidebar nav li a.active");
      if (active) {
        const existing = active.querySelector(".done-check");
        if (next && !existing) {
          active.insertAdjacentHTML("beforeend", '<span class="done-check" title="Finalizada">&check;</span>');
        }
        if (!next && existing) existing.remove();
      }
    });

    // Si ya hay una carpeta notes/ conectada (con permiso ya concedido), sincroniza
    // el estado desde progress.json por si se marco desde otra maquina/navegador.
    idbGet("dirHandle").then(function (dirHandle) {
      if (!dirHandle) return;
      return dirHandle.queryPermission({ mode: "readwrite" }).then(function (state) {
        if (state !== "granted") return;
        return dirHandle.getFileHandle("progress.json", { create: true }).then(function (fh) {
          return fh.getFile().then(function (f) { return f.text(); }).then(function (text) {
            let data = {};
            try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
            if (typeof data[dir] === "boolean" && data[dir] !== isDone(dir)) {
              setDoneLocal(dir, data[dir]);
              render();
            }
          });
        });
      });
    }).catch(function () {});
  }

  function updateDoneCount() {
    const el = document.getElementById("done-count");
    if (!el || typeof LESSONS === "undefined") return;
    const ready = LESSONS.filter(function (l) { return l.ready; });
    const done = ready.filter(function (l) { return isDone(l.dir); }).length;
    el.textContent = done + " de " + ready.length + " finalizadas";
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupTheme();
    buildSidebar();
    setupMobileToggle();
    setupNotes();
    setupDone();
    updateDoneCount();
  });
})();
