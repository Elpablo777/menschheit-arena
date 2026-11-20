/* Menschheit Arena – UI-Logik ohne Build-Schritt. */
(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const state = {
    lang: localStorage.getItem("ma.lang") || "de",
    messages: {},
    config: null,
    health: null,
    debates: [],
    debateLimit: 20,
    engagements: [],
    selectedDebate: null,
    selectedEngagement: null,
    pollTimer: null,
    showPrivate: localStorage.getItem("ma.showPrivate") !== "false",
    transcriptOpen: new Set(),
  };

  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ESCAPES[character]);
  }

  function t(key, fallback) {
    const value = state.messages[key];
    if (typeof value === "string" && value.trim()) return value;
    return fallback || key;
  }

  function langLabel(language) {
    return language === "en" ? t("lang.en", "Englisch") : t("lang.de", "Deutsch");
  }

  function statusLabel(status) {
    const map = {
      pending: "Ausstehend",
      running: "Läuft",
      completed: "Fertig",
      failed: "Fehler",
      killed: "Beendet",
      active: "Aktiv",
      proposed: "Vorgeschlagen",
      approved: "Freigegeben",
      rejected: "Abgelehnt",
      blocked_by_scope: "Scope blockiert",
      allowed: "Erlaubt",
      denied: "Blockiert",
    };
    return state.messages[`status.${status}`] || map[status] || status || "–";
  }

  function statusChip(status) {
    const safe = escapeHtml(status || "unknown");
    return `<span class="status-chip" data-status="${safe}">${escapeHtml(statusLabel(status))}</span>`;
  }

  function actionTypeLabel(type) {
    return type === "ACTIVE_REQUIRES_APPROVAL"
      ? t("sentinel.action.type_active", "Aktiv – Freigabe nötig")
      : t("sentinel.action.type_read", "Read-only");
  }

  function scoreValue(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "–";
    return Number.isInteger(number) ? String(number) : number.toFixed(1);
  }

  function formatDate(value) {
    if (!value) return "–";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(state.lang === "de" ? "de-DE" : "en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function formatTime(value) {
    if (!value) return "–";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(state.lang === "de" ? "de-DE" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  }

  function formatDay(value) {
    if (!value) return "–";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(state.lang === "de" ? "de-DE" : "en-GB", {
      dateStyle: "medium",
    }).format(date);
  }

  function formatDuration(seconds) {
    const value = Number(seconds);
    if (!Number.isFinite(value) || value <= 0) return "–";
    const minutes = Math.floor(value / 60);
    const rest = Math.round(value % 60);
    if (minutes >= 60) return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    return minutes > 0 ? `${minutes} min ${rest} s` : `${rest} s`;
  }

  function formatDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && item.msg) {
            const location = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
            return location ? `${location}: ${item.msg}` : item.msg;
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
    return JSON.stringify(detail);
  }

  async function api(path, options = {}) {
    const method = options.method || "GET";
    const headers = { Accept: "application/json" };
    const token = localStorage.getItem("ma.token");
    if (token) headers["X-App-Token"] = token;
    const init = { method, headers };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try {
        const data = await response.json();
        if (data && data.detail !== undefined) message = formatDetail(data.detail);
      } catch {
        /* Kein JSON-Fehlerkoerper. */
      }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    if (!type.includes("application/json")) return response.text();
    return response.json();
  }

  /* ---------- Sprache & statische Texte ---------- */

  function applyI18n() {
    $$("[data-i18n]").forEach((element) => {
      const value = state.messages[element.dataset.i18n];
      if (typeof value === "string" && value.trim()) element.textContent = value;
    });
    $$("[data-i18n-placeholder]").forEach((element) => {
      const value = state.messages[element.dataset.i18nPlaceholder];
      if (typeof value === "string" && value.trim()) element.placeholder = value;
    });
    $$("[data-i18n-aria-label]").forEach((element) => {
      const value = state.messages[element.dataset.i18nAriaLabel];
      if (typeof value === "string" && value.trim()) element.setAttribute("aria-label", value);
    });
    document.title = t("app.name", "Menschheit Arena");
    const lang = normalizeDocLang(state.lang);
    document.documentElement.lang = lang;
    document.documentElement.dataset.lang = lang;
  }

  function normalizeDocLang(value) {
    return String(value || "de").toLowerCase().startsWith("en") ? "en" : "de";
  }

  async function setLanguage(language) {
    try {
      const data = await api(`/api/i18n/${encodeURIComponent(language)}`);
      state.lang = data.lang || language;
      state.messages = data.messages || {};
      localStorage.setItem("ma.lang", state.lang);
      $$("[data-set-lang]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.setLang === state.lang));
      });
      applyI18n();
      renderModeBadges();
      renderDebateList();
      renderEngagementList();
      if (state.selectedDebate) renderDebateDetail(state.selectedDebate);
      if (state.selectedEngagement) renderEngagementDetail(state.selectedEngagement);
      if (state.config) {
        renderSystem();
        renderProviders();
      }
      return true;
    } catch (error) {
      toast(error.message, true);
      return false;
    }
  }

  /* ---------- Toast ---------- */

  let toastTimer = null;

  function toast(message, isError = false) {
    const element = $("#toast");
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("error", Boolean(isError));
    element.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      element.hidden = true;
    }, isError ? 8000 : 4000);
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.original = button.dataset.original || button.textContent;
      button.disabled = true;
      if (label) button.textContent = label;
    } else {
      button.disabled = false;
      if (button.dataset.original) {
        button.textContent = button.dataset.original;
        delete button.dataset.original;
      }
    }
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value);
      toast(t("toast.copied", "In die Zwischenablage kopiert."));
    } catch {
      toast(t("common.copy_failed", "Kopieren nicht möglich"), true);
    }
  }

  /* ---------- Arena ---------- */

  async function loadDebates(reset = true) {
    try {
      if (reset) state.debateLimit = 20;
      const data = await api(`/api/arena/debates?limit=${state.debateLimit}`);
      state.debates = Array.isArray(data) ? data : [];
      renderDebateList();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderDebateList() {
    const list = $("#debate-list");
    if (!list) return;
    const more = $("#debate-more-wrap");
    if (!state.debates.length) {
      list.innerHTML = `<p class="empty">${escapeHtml(t("arena.history.empty", "Noch keine Debatte."))}</p>`;
      if (more) more.hidden = true;
      return;
    }
    list.innerHTML = state.debates
      .map((debate) => {
        const rounds = Number(debate.rounds_actual) || Number(debate.rounds_requested) || 0;
        const requested = Number(debate.rounds_requested) || 0;
        const roundsText =
          rounds > 0
            ? `${t("arena.rounds_progress", "Runden")}: ${rounds}${requested > rounds ? ` / ${requested}` : ""}`
            : `${t("arena.rounds_progress", "Runden")}: ${requested}`;
        return `
        <button type="button" class="list-item" data-debate-id="${escapeHtml(debate.id)}">
          <span class="item-main">
            <span class="item-title">${escapeHtml(debate.topic)}</span>
            <span class="item-meta">${escapeHtml(formatDate(debate.created_at))} · ${escapeHtml(
              langLabel(debate.language)
            )} · ${escapeHtml(roundsText)}</span>
          </span>
          ${statusChip(debate.status)}
        </button>`;
      })
      .join("");
    if (more) more.hidden = state.debates.length < state.debateLimit;
  }

  async function openDebate(debateId, scroll = true) {
    clearTimeout(state.pollTimer);
    state.selectedDebate = null;
    const detail = $("#debate-detail");
    if (!detail) return;
    detail.hidden = false;
    detail.innerHTML = `<p class="empty">${escapeHtml(t("arena.detail.loading", "Debatte wird geladen …"))}</p>`;
    try {
      const debate = await api(`/api/arena/debates/${encodeURIComponent(debateId)}`);
      state.selectedDebate = debate;
      renderDebateDetail(debate);
      if (scroll) detail.scrollIntoView({ behavior: "smooth", block: "start" });
      if (["pending", "running"].includes(debate.status)) scheduleDebatePoll(debateId);
    } catch (error) {
      detail.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
      toast(error.message, true);
    }
  }

  function scheduleDebatePoll(debateId) {
    clearTimeout(state.pollTimer);
    state.pollTimer = setTimeout(async () => {
      if (!state.selectedDebate || state.selectedDebate.id !== debateId) return;
      try {
        const debate = await api(`/api/arena/debates/${encodeURIComponent(debateId)}`);
        state.selectedDebate = debate;
        renderDebateDetail(debate);
        if (["pending", "running"].includes(debate.status)) {
          scheduleDebatePoll(debateId);
        } else {
          loadDebates(false);
          loadDebateCalls(debateId);
        }
      } catch {
        /* Netzwerk-Hiccup: Ansicht bleibt stehen. */
      }
    }, 1500);
  }

  function debateMeta(debate) {
    const models = debate.models || {};
    const rounds = Number(debate.rounds_actual) || 0;
    const requested = Number(debate.rounds_requested) || 0;
    return [
      formatDate(debate.created_at),
      langLabel(debate.language),
      rounds > 0
        ? `${t("arena.rounds_progress", "Runden")}: ${rounds}${requested > rounds ? ` / ${requested}` : ""}`
        : `${t("arena.rounds_progress", "Runden")}: ${requested}`,
      `Pro: ${models.pro || "–"} · Contra: ${models.contra || "–"} · Judge: ${models.judge || "–"} · Mod: ${
        models.moderator || "–"
      }`,
    ].join(" · ");
  }

  function renderDebateDetail(debate) {
    const detail = $("#debate-detail");
    if (!detail) return;
    const judgment = debate.judgment;
    const turns = debate.turns || [];
    const moderations = debate.moderations || [];
    const finished = debate.completed_at && debate.created_at
      ? (new Date(debate.completed_at) - new Date(debate.created_at)) / 1000
      : null;

    const progress = ["pending", "running"].includes(debate.status)
      ? `<div class="progress-line"><strong>${escapeHtml(
          t("arena.progress_live", "Fortschritt")
        )}:</strong> ${escapeHtml(debate.progress || debate.status)}</div>`
      : "";

    const reportLink = judgment
      ? `<a class="btn secondary small" href="/api/arena/debates/${encodeURIComponent(
          debate.id
        )}/report.md">${escapeHtml(t("arena.report_download", "Bericht als Markdown"))}</a>`
      : "";

    const errorBlock =
      debate.status === "failed" && debate.error
        ? `<details class="advanced"><summary>${escapeHtml(
            t("arena.error_detail", "Fehlerdetails")
          )}</summary><p class="prose small">${escapeHtml(debate.error)}</p></details>`
        : "";

    detail.innerHTML = `
      <header class="detail-head">
        <div>
          <p class="kicker">${escapeHtml(t("arena.transcript", "Gesprächsverlauf"))}</p>
          <h2>${escapeHtml(debate.topic)}</h2>
          <p class="meta-line">${escapeHtml(debateMeta(debate))}</p>
          ${
            finished !== null
              ? `<p class="item-meta">${escapeHtml(t("arena.finished_at", "Beendet am"))}: ${escapeHtml(
                  formatDate(debate.completed_at)
                )} · ${escapeHtml(t("arena.duration_total", "Gesamtdauer"))}: ${escapeHtml(
                  formatDuration(finished)
                )}</p>`
              : ""
          }
        </div>
        <div class="detail-tools">
          ${statusChip(debate.status)}
          ${reportLink}
          <button type="button" class="btn ghost small" data-close="debate">${escapeHtml(
            t("common.close", "Schließen")
          )}</button>
        </div>
      </header>
      ${progress}
      ${errorBlock}
      <div class="toolbar">
        <button type="button" class="btn secondary small" data-fork="true">${escapeHtml(
          t("arena.fork", "Als neue Debatte starten")
        )}</button>
        <button type="button" class="btn ghost small" data-transcript-toggle="true" aria-pressed="${state.showPrivate}">
          ${escapeHtml(
            state.showPrivate
              ? t("arena.hide_private", "Privates Reasoning ausblenden")
              : t("arena.show_private", "Privates Reasoning anzeigen")
          )}
        </button>
        <button type="button" class="btn danger small" data-delete="true">${escapeHtml(
          t("arena.delete", "Debatte löschen")
        )}</button>
      </div>
      ${renderTranscript(debate, turns, moderations)}
      ${renderJudgment(judgment)}
      <h3>${escapeHtml(t("arena.calls_title", "LLM-Aufrufe"))}</h3>
      <p class="hint">${escapeHtml(
        t("arena.calls_hint", "Jeder Aufruf mit Prompt, Antwort und Token-Zahlen.")
      )}</p>
      <div id="call-list" class="call-list">
        <p class="empty">${escapeHtml(t("common.loading", "Lädt …"))}</p>
      </div>
    `;
    loadDebateCalls(debate.id);
  }

  function renderTranscript(debate, turns, moderations) {
    const roundNumbers = Array.from(new Set(turns.map((turn) => turn.round_no))).sort((a, b) => a - b);
    if (!roundNumbers.length) {
      return `<h3>${escapeHtml(t("arena.transcript", "Gesprächsverlauf"))}</h3>
        <p class="empty">${escapeHtml(t("arena.no_argument", "Kein Beitrag in dieser Runde."))}</p>`;
    }
    const missing = [];
    for (let index = 1; index <= Math.max(...roundNumbers); index += 1) {
      if (!roundNumbers.includes(index)) missing.push(index);
    }
    const jump = roundNumbers.length > 4
      ? `<div class="round-jump">${roundNumbers
          .map((round) => `<button type="button" data-jump="${round}">#${round}</button>`)
          .join("")}</div>`
      : "";
    const header = `<h3>${escapeHtml(t("arena.transcript", "Gesprächsverlauf"))}</h3>
      <p class="item-meta">${roundNumbers.length} ${escapeHtml(
        t("arena.rounds_progress", "Runden")
      )}${
        missing.length
          ? ` · ${escapeHtml(t("arena.rounds_missing", "Runden ohne Beitrag"))}: ${missing
              .slice(0, 20)
              .join(", ")}`
          : ""
      }</p>${jump}`;
    const rounds = roundNumbers
      .map((round) => {
        const pro = turns.find((turn) => turn.round_no === round && turn.role === "pro");
        const contra = turns.find((turn) => turn.round_no === round && turn.role === "contra");
        const moderation = moderations.find((mod) => mod.round_no === round);
        const open = state.transcriptOpen.has(`${debate.id}:${round}`) || roundNumbers.length <= 2;
        const summaryBits = [pro ? "Pro" : "", contra ? "Contra" : ""].filter(Boolean).join(" · ");
        return `
        <details class="transcript-round" id="round-${round}" ${open ? "open" : ""}>
          <summary>
            <span>${escapeHtml(t("arena.round_free", "Runde"))} ${round}</span>
            ${summaryBits ? `<span class="tag">${escapeHtml(summaryBits)}</span>` : ""}
            ${
              pro || contra
                ? `<span class="item-meta">${escapeHtml(
                    t("arena.confidence", "Konfidenz")
                  )}: ${pro ? pro.confidence : "–"} / ${contra ? contra.confidence : "–"}</span>`
                : ""
            }
            ${moderation ? statusChip(moderation.decision) : ""}
          </summary>
          <div class="transcript-body">
            ${renderTurn(pro, round, debate.id)}
            ${renderTurn(contra, round, debate.id)}
            ${moderation ? renderModeration(moderation) : ""}
          </div>
        </details>`;
      })
      .join("");
    return `${header}<div class="transcript">${rounds}</div>`;
  }

  function renderTurn(turn, round, debateId) {
    if (!turn) {
      return `<div class="turn-card"><p class="empty">${escapeHtml(
        t("arena.no_argument", "Kein Beitrag in dieser Runde.")
      )}</p></div>`;
    }
    const isPro = turn.role === "pro";
    const confidence = Math.max(0, Math.min(100, Number(turn.confidence) || 0));
    const conceded = Array.isArray(turn.conceded_claims) ? turn.conceded_claims : [];
    const reasoning = escapeHtml(turn.internal_reasoning || "–");
    return `
      <article class="turn-card" data-role="${isPro ? "pro" : "contra"}">
        <header class="turn-head">
          <span class="role-pill">${escapeHtml(
            isPro ? t("arena.side_pro", "Pro") : t("arena.side_contra", "Contra")
          )}</span>
          <span class="tag">${escapeHtml(t("arena.round_free", "Runde"))} ${round}</span>
          <span class="confidence">${escapeHtml(t("arena.confidence", "Konfidenz"))} <strong>${confidence}</strong></span>
          <span class="tag">${escapeHtml(formatTime(turn.created_at))}</span>
        </header>
        <div class="confidence-bar"><span style="width:${confidence}%;${
          confidence <= 25 ? "background:var(--danger)" : ""
        }"></span></div>
        <p class="label">${escapeHtml(t("arena.steelman", "Steelman des Gegners"))}</p>
        <p class="prose">${escapeHtml(turn.steelman || "–")}</p>
        <p class="label">${escapeHtml(t("arena.public_argument", "Öffentliches Argument"))}</p>
        <p class="prose">${escapeHtml(turn.public_argument || "")}</p>
        ${
          state.showPrivate
            ? `<details class="private">
                <summary>${escapeHtml(t("arena.private_reasoning", "Internes Reasoning (nur für dich sichtbar)"))}</summary>
                <p class="prose">${reasoning}</p>
                <p class="label">${escapeHtml(t("arena.conceded", "Zugestandene Punkte"))}</p>
                ${
                  conceded.length
                    ? `<ul>${conceded.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
                    : `<p class="prose">${escapeHtml(t("common.none", "Keine"))}</p>`
                }
                <p class="label">${escapeHtml(t("arena.falsification", "Falsifikationsbedingung"))}</p>
                <p class="prose">${escapeHtml(turn.falsification || "–")}</p>
              </details>`
            : `<p class="hint">${escapeHtml(t("arena.private_hidden_hint", "Ausgeblendet."))}</p>`
        }
        <div class="turn-actions">
          <button type="button" class="btn ghost small" data-call-filter="${isPro ? "pro" : "contra"}">
            ${escapeHtml(t("arena.prompt_view", "Verwendete Prompts"))}
          </button>
          <button type="button" class="btn ghost small" data-copy-turn="${escapeHtml(turn.id)}">
            ${escapeHtml(t("common.copy", "Kopieren"))}
          </button>
        </div>
      </article>`;
  }

  function renderModeration(moderation) {
    const flags = [];
    if (moderation.sycophancy) flags.push(t("arena.sycophancy", "Sycophancy erkannt"));
    if (moderation.drift) flags.push(t("arena.drift", "Problem-Drift erkannt"));
    return `
      <aside class="moderation-card">
        <div class="moderation-head">
          <span class="role-pill">${escapeHtml(t("arena.moderator_note", "Moderator"))}</span>
          ${statusChip(moderation.decision)}
          ${flags.length ? `<span class="tag bad">${escapeHtml(flags.join(" · "))}</span>` : ""}
        </div>
        <p>${escapeHtml(moderation.summary || "")}</p>
        ${
          moderation.directive
            ? `<p><strong>${escapeHtml(
                t("arena.next_directive", "Direktive für die nächste Runde")
              )}:</strong> ${escapeHtml(moderation.directive)}</p>`
            : ""
        }
      </aside>`;
  }

  async function loadDebateCalls(debateId, role = null) {
    const list = $("#call-list");
    if (!list) return;
    try {
      const query = role ? `?role=${encodeURIComponent(role)}&limit=500` : "?limit=500";
      const data = await api(`/api/arena/debates/${encodeURIComponent(debateId)}/calls${query}`);
      const calls = data.calls || [];
      if (!calls.length) {
        list.innerHTML = `<p class="empty">${escapeHtml(t("arena.no_calls", "Noch keine Aufrufe."))}</p>`;
        return;
      }
      list.innerHTML = calls.map(renderCall).join("");
      const summary = document.createElement("p");
      summary.className = "item-meta";
      summary.textContent = `${calls.length} ${escapeHtml(
        t("arena.calls_title", "LLM-Aufrufe")
      )} · ${data.total_tokens} ${escapeHtml(t("arena.call_tokens", "Tokens"))}`;
      list.prepend(summary);
    } catch (error) {
      list.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    }
  }

  function renderCall(call) {
    const messages = Array.isArray(call.messages) ? call.messages : [];
    const system = messages.filter((entry) => entry.role === "system").map((entry) => entry.content).join("\n\n");
    const others = messages.filter((entry) => entry.role !== "system");
    const ok = Boolean(call.parsed_ok);
    const duration = Number(call.duration_ms) / 1000;
    return `
      <details class="call-card">
        <summary>
          <span class="tag">${escapeHtml(call.role || call.purpose || "–")}</span>
          ${call.round_no ? `<span class="tag">${escapeHtml(t("arena.call_round", "Runde"))} ${call.round_no}</span>` : ""}
          <span class="item-meta">${escapeHtml(call.model || "–")}</span>
          <span class="tag">${call.total_tokens || 0} ${escapeHtml(t("arena.call_tokens", "Tokens"))}</span>
          <span class="tag">${Number.isFinite(duration) ? `${duration.toFixed(1)} s` : "–"}</span>
          <span class="tag ${ok ? "ok" : "bad"}">${escapeHtml(
            ok ? t("arena.call_parsed", "geparst") : t("arena.call_failed", "fehlgeschlagen")
          )}</span>
        </summary>
        <div class="call-body">
          <div class="call-meta">
            <span>${escapeHtml(t("arena.call_role", "Rolle"))}: ${escapeHtml(call.role || "–")}</span>
            <span>${escapeHtml(t("arena.call_model", "Modell"))}: ${escapeHtml(call.model || "–")}</span>
            <span>prompt ${call.prompt_tokens || 0} · completion ${call.completion_tokens || 0}</span>
            ${call.error ? `<span class="tag bad">${escapeHtml(call.error)}</span>` : ""}
          </div>
          <div class="call-section">
            <h4>${escapeHtml(t("arena.prompt_system", "System-Prompt der Rolle"))}</h4>
            <pre>${escapeHtml(system || "–")}</pre>
          </div>
          <div class="call-section">
            <h4>${escapeHtml(t("arena.prompt_user", "Benutzer-Nachricht (Rohtext)"))}</h4>
            <pre>${escapeHtml(
              others.map((entry) => `[${entry.role}]\n${entry.content}`).join("\n\n") || "–"
            )}</pre>
          </div>
          <div class="call-section">
            <h4>${escapeHtml(t("arena.prompt_response", "Antwort des Modells"))}</h4>
            <pre>${escapeHtml(call.response_text || "–")}</pre>
          </div>
        </div>
      </details>`;
  }

  async function submitDebate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $("#debate-submit");
    const data = new FormData(form);
    const topic = String(data.get("topic") || "").trim();
    if (topic.length < 8) {
      toast(`${t("arena.form.topic", "Debattenthema")}: min. 8`, true);
      $("#debate-topic")?.focus();
      return;
    }
    const rounds = Number(data.get("rounds") || 0);
    if (!Number.isInteger(rounds) || rounds < 1 || rounds > 2000) {
      toast(`${t("arena.rounds_free", "Runden")}: 1–2000`, true);
      $("#debate-rounds")?.focus();
      return;
    }
    const models = {};
    [
      ["pro", "model_pro"],
      ["contra", "model_contra"],
      ["judge", "model_judge"],
      ["moderator", "model_moderator"],
    ].forEach(([role, field]) => {
      const value = String(data.get(field) || "").trim();
      if (value) models[role] = value;
    });
    const config = {};
    const wordLimit = Number(data.get("word_limit") || 0);
    if (wordLimit >= 80) config.word_limit = wordLimit;
    const temperature = Number(data.get("temperature"));
    if (Number.isFinite(temperature) && temperature > 0) config.temperature = temperature;
    const maxTokens = Number(data.get("max_tokens") || 0);
    if (maxTokens >= 128) config.max_tokens = maxTokens;
    const confidence = Number(data.get("confidence_gate"));
    if (Number.isInteger(confidence) && confidence >= 0 && confidence <= 100) {
      config.confidence_gate = confidence;
    }
    config.early_stop = Boolean(data.get("early_stop"));
    config.show_private_reasoning = Boolean(data.get("show_private_reasoning"));
    if (config.show_private_reasoning) {
      state.showPrivate = true;
      localStorage.setItem("ma.showPrivate", "true");
    }

    const payload = {
      topic,
      rounds,
      language: String(data.get("language") || state.lang),
      config,
    };
    if (Object.keys(models).length) payload.models = models;
    setBusy(button, true, t("arena.form.starting", "Debatte läuft …"));
    try {
      const debate = await api("/api/arena/debates", { method: "POST", body: payload });
      toast(t("toast.debate_started", "Debatte gestartet."));
      form.reset();
      $("#debate-lang").value = state.lang;
      if (state.config) $("#debate-rounds").value = String(state.config.default_rounds || 4);
      await loadDebates();
      await openDebate(debate.id, true);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function forkDebate(button) {
    const debate = state.selectedDebate;
    if (!debate) return;
    const dialog = $("#fork-dialog");
    if (!dialog || !dialog.open) {
      if (dialog && typeof dialog.showModal === "function") dialog.showModal();
      return;
    }
    const input = $("#fork-topic");
    const topic = input ? input.value.trim() : "";
    if (topic.length < 8) {
      toast(`${t("arena.fork_topic", "Neues Thema")}: min. 8`, true);
      input?.focus();
      return;
    }
    const roundsField = $("#fork-rounds");
    const inheritModels = Boolean($("#fork-inherit-models")?.checked);
    const inheritConfig = Boolean($("#fork-inherit-config")?.checked);
    const roundsValue = Number(roundsField ? roundsField.value : 0);
    const rounds = Number.isInteger(roundsValue) && roundsValue >= 1 ? roundsValue : null;
    setBusy(button, true, t("arena.fork_start", "Neue Debatte starten"));
    try {
      const body = { topic, inherit_models: inheritModels, inherit_config: inheritConfig };
      if (rounds) body.rounds = rounds;
      const created = await api(`/api/arena/debates/${encodeURIComponent(debate.id)}/fork`, {
        method: "POST",
        body,
      });
      if (dialog) dialog.close();
      toast(t("toast.debate_forked", "Neue Debatte gestartet."));
      await loadDebates();
      await openDebate(created.id, true);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function deleteDebate(button) {
    const debate = state.selectedDebate;
    if (!debate) return;
    if (!window.confirm(t("arena.delete_confirm", "Debatte löschen?"))) return;
    setBusy(button, true);
    try {
      await api(`/api/arena/debates/${encodeURIComponent(debate.id)}`, { method: "DELETE" });
      toast(t("toast.debate_deleted", "Debatte gelöscht."));
      state.selectedDebate = null;
      const detail = $("#debate-detail");
      if (detail) {
        detail.hidden = true;
        detail.innerHTML = "";
      }
      await loadDebates();
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  function renderJudgment(judgment) {
    if (!judgment) {
      return `<p class="hint">${escapeHtml(
        t("arena.detail.judge_pending", "Das Urteil erscheint, sobald alle Runden abgeschlossen sind.")
      )}</p>`;
    }
    const average = (judgment.toulmin && judgment.toulmin.average) || {};
    const winner =
      (judgment.toulmin && judgment.toulmin.winner) ||
      (judgment.pass_ab && judgment.pass_ab.winner) ||
      "draw";
    const bias = Number(judgment.bias_delta || 0);
    const summary =
      (judgment.pass_ab && judgment.pass_ab.summary) || (judgment.pass_ba && judgment.pass_ba.summary) || "";
    const winnerLabel =
      winner === "pro"
        ? t("arena.side_pro", "Pro")
        : winner === "contra"
        ? t("arena.side_contra", "Contra")
        : t("arena.draw", "Unentschieden");
    const biasText =
      bias >= 4
        ? t("arena.detail.bias_high", "Auffällige Abweichung zwischen den Richter-Durchläufen.")
        : t("arena.detail.bias_ok", "Geringe Abweichung zwischen den Richter-Durchläufen.");
    const rules = (judgment.pass_ab && judgment.pass_ab.architecture_rules) || [];
    const conflicts = (judgment.pass_ab && judgment.pass_ab.open_conflicts) || [];

    return `
      <h3>${escapeHtml(t("arena.judgment", "Richter-Urteil (Dual-Order)"))}</h3>
      <div class="judge-grid">
        <article class="judge-card">
          <h3>${escapeHtml(t("arena.detail.summary", "Zusammenfassung"))}</h3>
          <p class="prose">${escapeHtml(summary)}</p>
          <p><span class="label">${escapeHtml(t("arena.winner", "Urteil"))}</span><br><strong>${escapeHtml(
            winnerLabel
          )}</strong></p>
          <p class="hint">${escapeHtml(t("arena.bias_delta", "Positionsbias-Delta"))}: <strong>${escapeHtml(
            bias.toFixed(1)
          )}</strong> · ${escapeHtml(biasText)}</p>
          ${
            conflicts.length
              ? `<details class="private"><summary>${escapeHtml(
                  t("report.conflicts", "Offene Grundsatzkonflikte")
                )}</summary><ul>${conflicts.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>`
              : ""
          }
          ${
            rules.length
              ? `<details class="private"><summary>${escapeHtml(
                  t("report.rules", "Konkrete Architektur- & Verfassungsregeln")
                )}</summary><ul>${rules.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>`
              : ""
          }
        </article>
        <article class="judge-card">
          <h3>${escapeHtml(t("arena.detail.scores", "Punktwertung"))}</h3>
          <table class="score-table">
            <thead>
              <tr><th scope="col"></th><th scope="col">Pro</th><th scope="col">Contra</th></tr>
            </thead>
            <tbody>${scoreRows(average)}</tbody>
            <tfoot>
              <tr><th scope="row">Total</th><td>${scoreValue(average.pro && average.pro.total)}</td><td>${scoreValue(
                average.contra && average.contra.total
              )}</td></tr>
            </tfoot>
          </table>
          <details class="private"><summary>${escapeHtml(
            t("arena.detail.pass_ab", "Richter-Durchlauf A/B")
          )}</summary><p class="prose small">${escapeHtml(
            (judgment.pass_ab && judgment.pass_ab.summary) || ""
          )}</p></details>
          <details class="private"><summary>${escapeHtml(
            t("arena.detail.pass_ba", "Richter-Durchlauf B/A")
          )}</summary><p class="prose small">${escapeHtml(
            (judgment.pass_ba && judgment.pass_ba.summary) || ""
          )}</p></details>
        </article>
      </div>
    `;
  }

  function scoreRows(average) {
    const rows = [
      ["claims", "Claims"],
      ["logic", "Logic"],
      ["qualifiers", "Qualifiers"],
      ["rebuttals", "Rebuttals"],
      ["realism", "Realism"],
    ];
    return rows
      .map(
        ([key, label]) =>
          `<tr><th scope="row">${label}</th><td>${scoreValue(
            average.pro && average.pro[key]
          )}</td><td>${scoreValue(average.contra && average.contra[key])}</td></tr>`
      )
      .join("");
  }

  /* ---------- Sentinel ---------- */

  async function loadEngagements() {
    try {
      const data = await api("/api/sentinel/engagements?limit=100");
      state.engagements = Array.isArray(data) ? data : [];
      renderEngagementList();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderEngagementList() {
    const list = $("#engagement-list");
    if (!list) return;
    if (!state.engagements.length) {
      list.innerHTML = `<p class="empty">${escapeHtml(t("sentinel.list.empty", "Noch kein Engagement."))}</p>`;
      return;
    }
    list.innerHTML = state.engagements
      .map(
        (engagement) => `
        <button type="button" class="list-item" data-engagement-id="${escapeHtml(engagement.id)}">
          <span class="item-main">
            <span class="item-title">${escapeHtml(engagement.client_name)}</span>
            <span class="item-meta">${escapeHtml(formatDay(engagement.valid_from))} – ${escapeHtml(
              formatDay(engagement.valid_until)
            )}</span>
          </span>
          <span class="list-badges">
            ${engagement.kill_switch ? statusChip("killed") : statusChip(engagement.status)}
          </span>
        </button>`
      )
      .join("");
  }

  async function openEngagement(engagementId, scroll = true) {
    const detail = $("#engagement-detail");
    if (!detail) return;
    detail.hidden = false;
    detail.innerHTML = `<p class="empty">${escapeHtml(t("common.loading", "Lädt …"))}</p>`;
    try {
      const engagement = await api(`/api/sentinel/engagements/${encodeURIComponent(engagementId)}`);
      state.selectedEngagement = engagement;
      renderEngagementDetail(engagement);
      if (scroll) detail.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      detail.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
      toast(error.message, true);
    }
  }

  function renderEngagementDetail(engagement) {
    const detail = $("#engagement-detail");
    if (!detail) return;
    const actions = engagement.actions || [];
    const findings = engagement.findings || [];
    const needsApproval = actions.some(
      (action) => action.approval_required && action.status === "proposed" && action.scope_allowed
    );
    const reportLink = `<a class="btn secondary small" href="/api/sentinel/engagements/${encodeURIComponent(
      engagement.id
    )}/report.md?lang=${encodeURIComponent(state.lang)}">${escapeHtml(
      t("sentinel.report_download", "Bericht als Markdown")
    )}</a>`;

    detail.innerHTML = `
      <header class="detail-head">
        <div>
          <p class="kicker">${escapeHtml(t("sentinel.detail.title", "Engagement-Details"))}</p>
          <h2>${escapeHtml(engagement.client_name)}</h2>
          <p class="meta-line">${escapeHtml(engagement.id)} · ${escapeHtml(formatDate(engagement.created_at))}</p>
        </div>
        <div class="detail-tools">
          ${engagement.kill_switch ? statusChip("killed") : statusChip(engagement.status)}
          ${reportLink}
          <button type="button" class="btn ghost small" data-close="engagement">${escapeHtml(
            t("common.close", "Schließen")
          )}</button>
        </div>
      </header>

      <div class="meta-grid">
        <div><span class="stat-label">${escapeHtml(
          t("sentinel.detail.client", "Auftraggeber")
        )}</span><strong>${escapeHtml(engagement.client_name)}</strong></div>
        <div><span class="stat-label">${escapeHtml(
          t("sentinel.detail.authorized", "Freigegeben durch")
        )}</span><strong>${escapeHtml(engagement.authorized_by)}</strong></div>
        <div><span class="stat-label">${escapeHtml(
          t("sentinel.detail.emergency", "Notfallkontakt")
        )}</span><strong>${escapeHtml(engagement.emergency_contact)}</strong></div>
        <div><span class="stat-label">${escapeHtml(
          t("sentinel.detail.validity", "Gültigkeit")
        )}</span><strong>${escapeHtml(formatDay(engagement.valid_from))} – ${escapeHtml(
          formatDay(engagement.valid_until)
        )}</strong></div>
        <div><span class="stat-label">${escapeHtml(
          t("sentinel.detail.ports", "Erlaubte Ports")
        )}</span><strong>${escapeHtml((engagement.ports || []).join(", "))}</strong></div>
        <div><span class="stat-label">${escapeHtml(
          t("report.audit", "Audit-Kette")
        )}</span><strong>${escapeHtml(
          engagement.audit_valid ? t("common.yes", "Ja") : t("common.no", "Nein")
        )} (${actions.length} ${escapeHtml(t("common.actions", "Aktionen"))})</strong></div>
      </div>

      <h3>${escapeHtml(t("sentinel.detail.scope", "Scope"))}</h3>
      <div class="scope-chips">${(engagement.scope || [])
        .map((entry) => `<code>${escapeHtml(entry)}</code>`)
        .join("")}</div>
      <p class="item-meta">${escapeHtml(t("sentinel.detail.roe_hash", "RoE-Hash (SHA-256)"))}: ${escapeHtml(
        engagement.roe_hash
      )}</p>

      <div class="toolbar">
        <button type="button" class="btn secondary" data-action="plan" data-mode="rules" data-id="${escapeHtml(
          engagement.id
        )}" ${engagement.kill_switch ? "disabled" : ""}>${escapeHtml(
          t("sentinel.detail.plan_rules", "Regelbasierten Plan erzeugen")
        )}</button>
        <button type="button" class="btn ghost" data-action="plan" data-mode="llm" data-id="${escapeHtml(
          engagement.id
        )}" ${engagement.kill_switch ? "disabled" : ""}>${escapeHtml(
          t("sentinel.detail.plan_llm", "LLM-Plan erzeugen")
        )}</button>
        <button type="button" class="btn danger" data-action="kill" data-id="${escapeHtml(engagement.id)}" ${
          engagement.kill_switch ? "disabled" : ""
        }>${escapeHtml(t("sentinel.detail.kill", "Kill-Switch"))}</button>
        <button type="button" class="btn ghost" data-action="delete-engagement" data-id="${escapeHtml(
          engagement.id
        )}">${escapeHtml(t("sentinel.delete", "Engagement löschen"))}</button>
      </div>

      <h3>${escapeHtml(t("sentinel.actions.title", "Aktionen"))}</h3>
      <p class="hint">${escapeHtml(
        t(
          "sentinel.detail.actions_hint",
          "Read-only-Aktionen werden nicht ausgeführt. Aktive Aktionen benötigen eine dokumentierte Freigabe."
        )
      )}</p>
      ${
        needsApproval
          ? `<div class="approval-bar">
              <div class="field">
                <label for="approver-name">${escapeHtml(t("sentinel.form.approver", "Freigabe durch"))}</label>
                <input id="approver-name" autocomplete="name" placeholder="${escapeHtml(
                  t("sentinel.form.approver_placeholder", "Vor- und Nachname der freigebenden Person")
                )}">
              </div>
              <div class="field">
                <label for="reject-reason">${escapeHtml(
                  t("sentinel.action.reject_reason", "Grund für Ablehnung")
                )}</label>
                <input id="reject-reason">
              </div>
            </div>`
          : ""
      }
      <div class="actions">
        ${
          actions.length
            ? actions.map(renderAction).join("")
            : `<p class="empty">${escapeHtml(t("sentinel.detail.no_actions", "Noch keine Aktionen."))}</p>`
        }
      </div>

      <h3>${escapeHtml(t("sentinel.findings.title", "Geprüfte Findings"))}</h3>
      <p class="hint">${escapeHtml(
        t("sentinel.detail.findings_hint", "Findings erscheinen erst nach menschlicher Verifikation im Bericht.")
      )}</p>
      ${
        findings.length
          ? findings.map(renderFinding).join("")
          : `<p class="empty">${escapeHtml(
              t("sentinel.findings.empty", "Noch keine menschlich verifizierten Findings.")
            )}</p>`
      }
      <details class="advanced">
        <summary>${escapeHtml(t("sentinel.finding.add", "Finding melden"))}</summary>
        <form id="finding-form" class="stack" novalidate>
          <div class="field">
            <label for="f-title">${escapeHtml(t("sentinel.finding.title", "Titel"))}</label>
            <input id="f-title" name="title" required minlength="3" maxlength="300">
          </div>
          <div class="row">
            <div class="field">
              <label for="f-owasp">${escapeHtml(t("sentinel.finding.owasp", "OWASP-Referenz"))}</label>
              <input id="f-owasp" name="owasp_ref" maxlength="120" placeholder="A01:2021">
            </div>
            <div class="field grow">
              <label for="f-cvss">${escapeHtml(t("sentinel.finding.cvss", "CVSS-v4.0-Vektor"))}</label>
              <input id="f-cvss" name="cvss_vector" maxlength="300" placeholder="CVSS:4.0/AV:N/AC:L/...">
            </div>
          </div>
          <div class="field">
            <label for="f-evidence">${escapeHtml(t("sentinel.finding.evidence", "Evidenz (reproduzierbar)"))}</label>
            <textarea id="f-evidence" name="evidence" rows="3" required minlength="10" maxlength="20000"></textarea>
          </div>
          <div class="field">
            <label for="f-remediation">${escapeHtml(t("sentinel.finding.remediation", "Remediation"))}</label>
            <textarea id="f-remediation" name="remediation" rows="3" required minlength="10" maxlength="20000"></textarea>
          </div>
          <div class="field">
            <label for="f-actor">${escapeHtml(t("sentinel.finding.actor", "Geprüft von"))}</label>
            <input id="f-actor" name="actor" autocomplete="name" value="${escapeHtml(
              engagement.authorized_by || "human"
            )}">
          </div>
          <label class="check">
            <input type="checkbox" name="verified_by_human" value="true" required>
            <span>${escapeHtml(
              t("sentinel.finding.verified", "Ich habe dieses Finding menschlich verifiziert.")
            )}</span>
          </label>
          <div class="form-actions">
            <button type="submit" class="btn primary" id="finding-submit">${escapeHtml(
              t("sentinel.finding.submit", "Finding speichern")
            )}</button>
          </div>
        </form>
      </details>
    `;
    const form = $("#finding-form");
    if (form) form.addEventListener("submit", (event) => submitFinding(event, engagement.id));
  }

  function renderAction(action) {
    const allowed = Boolean(action.scope_allowed);
    const canApprove =
      allowed && action.status === "proposed" && Boolean(action.approval_required) && !action.approved_by;
    const canReject = ["proposed", "approved"].includes(action.status);
    const approvedBy = action.approved_by
      ? `<span>${escapeHtml(t("sentinel.action.approved_by", "Freigegeben von"))}: ${escapeHtml(
          action.approved_by
        )}</span>`
      : "";
    return `
      <article class="action-card">
        <div class="action-head">
          <div>
            <span class="phase">${escapeHtml(action.phase)}</span>
            <strong>${escapeHtml(action.target)}:${escapeHtml(action.port)}</strong>
          </div>
          ${statusChip(action.status)}
        </div>
        <code class="command">${escapeHtml(action.command)}</code>
        <div class="action-meta">
          <span>${escapeHtml(actionTypeLabel(action.action_type))}</span>
          <span>${escapeHtml(t("sentinel.action.risk", "Risiko"))}: ${escapeHtml(action.risk)}</span>
          <span>${escapeHtml(t("sentinel.action.scope", "Scope-Check"))}: ${
            allowed ? escapeHtml(t("sentinel.validate.allowed", "Erlaubt")) : escapeHtml(t("sentinel.validate.denied", "Blockiert"))
          }</span>
          ${approvedBy}
        </div>
        ${action.scope_reason ? `<p class="hint">${escapeHtml(action.scope_reason)}</p>` : ""}
        <p class="prose small">${escapeHtml(
          t("sentinel.action.evidence", "Erwartete Evidenz")
        )}: ${escapeHtml(action.expected_evidence || "–")}</p>
        ${
          canApprove || canReject
            ? `<div class="form-actions">
                ${
                  canApprove
                    ? `<button type="button" class="btn primary small" data-action="approve" data-id="${escapeHtml(
                        action.id
                      )}">${escapeHtml(t("sentinel.action.approve", "Freigeben"))}</button>`
                    : ""
                }
                ${
                  canReject
                    ? `<button type="button" class="btn danger small" data-action="reject" data-id="${escapeHtml(
                        action.id
                      )}">${escapeHtml(t("sentinel.action.reject", "Ablehnen"))}</button>`
                    : ""
                }
              </div>`
            : ""
        }
      </article>`;
  }

  function renderFinding(finding) {
    return `
      <article class="finding">
        <h4>${escapeHtml(finding.title)}</h4>
        <div class="action-meta">
          <span>${escapeHtml(t("sentinel.finding.owasp", "OWASP-Referenz"))}: ${escapeHtml(
            finding.owasp_ref || "–"
          )}</span>
          <span>${escapeHtml(t("sentinel.finding.cvss", "CVSS-v4.0-Vektor"))}: ${escapeHtml(
            finding.cvss_vector || "–"
          )}</span>
          ${statusChip(finding.verified_by_human ? "approved" : "pending")}
        </div>
        <p class="prose small"><strong>${escapeHtml(
          t("sentinel.finding.evidence", "Evidenz (reproduzierbar)")
        )}:</strong> ${escapeHtml(finding.evidence)}</p>
        <p class="prose small"><strong>${escapeHtml(
          t("sentinel.finding.remediation", "Remediation")
        )}:</strong> ${escapeHtml(finding.remediation)}</p>
      </article>`;
  }

  async function submitEngagement(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $("#engagement-submit");
    const data = new FormData(form);
    const scope = String(data.get("scope") || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const ports = String(data.get("ports") || "")
      .split(/[,\s]+/)
      .map((port) => port.trim())
      .filter(Boolean)
      .map(Number);
    if (!scope.length) {
      toast(`${t("sentinel.form.scope", "In-Scope-Ziele")}: ${t("common.none", "Keine")}`, true);
      return;
    }
    if (!ports.length || ports.some((port) => !Number.isInteger(port) || port < 1 || port > 65535)) {
      toast(`${t("sentinel.form.ports", "Erlaubte Ports")}: 1–65535`, true);
      return;
    }
    const payload = {
      client_name: String(data.get("client_name") || "").trim(),
      scope,
      ports,
      valid_from: String(data.get("valid_from") || ""),
      valid_until: String(data.get("valid_until") || ""),
      roe_text: String(data.get("roe_text") || "").trim(),
      authorized_by: String(data.get("authorized_by") || "").trim(),
      emergency_contact: String(data.get("emergency_contact") || "").trim(),
    };
    if (payload.roe_text.length < 50) {
      toast(`${t("sentinel.form.roe", "Rules of Engagement (RoE)")}: min. 50`, true);
      return;
    }
    setBusy(button, true);
    try {
      const engagement = await api("/api/sentinel/engagements", { method: "POST", body: payload });
      toast(t("toast.engagement_created", "Engagement angelegt."));
      form.reset();
      setDefaultDates();
      $("#eng-ports").value = "80, 443";
      await loadEngagements();
      await openEngagement(engagement.id, true);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function generatePlan(button) {
    const engagement = state.selectedEngagement;
    if (!engagement) return;
    setBusy(button, true);
    try {
      await api(`/api/sentinel/engagements/${engagement.id}/plan`, {
        method: "POST",
        body: { mode: button.dataset.mode || "rules", language: state.lang },
      });
      toast(t("toast.plan_created", "Plan erzeugt."));
      await refreshEngagement(engagement.id);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function approveAction(button) {
    const approver = ($("#approver-name")?.value || "").trim();
    if (!approver) {
      toast(t("sentinel.form.approver", "Freigabe durch"), true);
      $("#approver-name")?.focus();
      return;
    }
    setBusy(button, true);
    try {
      await api(`/api/sentinel/actions/${button.dataset.id}/approve`, {
        method: "POST",
        body: { approver },
      });
      toast(t("toast.action_approved", "Aktion freigegeben."));
      if (state.selectedEngagement) await refreshEngagement(state.selectedEngagement.id);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function rejectAction(button) {
    const actor = ($("#approver-name")?.value || "").trim() || "human";
    const reason = ($("#reject-reason")?.value || "").trim();
    setBusy(button, true);
    try {
      await api(`/api/sentinel/actions/${button.dataset.id}/reject`, {
        method: "POST",
        body: { actor, reason },
      });
      toast(t("toast.action_rejected", "Aktion abgelehnt."));
      if (state.selectedEngagement) await refreshEngagement(state.selectedEngagement.id);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function killEngagement(button) {
    if (!window.confirm(t("sentinel.detail.kill_confirm", "Kill-Switch aktivieren?"))) return;
    const actor = ($("#approver-name")?.value || "").trim() || "human";
    setBusy(button, true);
    try {
      await api(`/api/sentinel/engagements/${button.dataset.id}/kill`, {
        method: "POST",
        body: { actor },
      });
      toast(t("toast.kill_switch", "Kill-Switch aktiviert."));
      await refreshEngagement(button.dataset.id);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function deleteEngagement(button) {
    if (!window.confirm(t("sentinel.delete_confirm", "Engagement löschen?"))) return;
    setBusy(button, true);
    try {
      await api(`/api/sentinel/engagements/${button.dataset.id}`, { method: "DELETE" });
      toast(t("sentinel.deleted", "Engagement gelöscht."));
      state.selectedEngagement = null;
      const detail = $("#engagement-detail");
      if (detail) {
        detail.hidden = true;
        detail.innerHTML = "";
      }
      await loadEngagements();
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function refreshEngagement(engagementId) {
    const engagement = await api(`/api/sentinel/engagements/${engagementId}`);
    state.selectedEngagement = engagement;
    renderEngagementDetail(engagement);
    await loadEngagements();
  }

  async function submitFinding(event, engagementId) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $("#finding-submit");
    const data = new FormData(form);
    if (!data.get("verified_by_human")) {
      toast(t("sentinel.finding.verified", "Ich habe dieses Finding menschlich verifiziert."), true);
      return;
    }
    const payload = {
      title: String(data.get("title") || "").trim(),
      owasp_ref: String(data.get("owasp_ref") || "").trim(),
      cvss_vector: String(data.get("cvss_vector") || "").trim(),
      evidence: String(data.get("evidence") || "").trim(),
      remediation: String(data.get("remediation") || "").trim(),
      verified_by_human: true,
      actor: String(data.get("actor") || "").trim() || "human",
    };
    if (payload.evidence.length < 10 || payload.remediation.length < 10) {
      toast(t("sentinel.validate.invalid", "Ungültige Eingabe."), true);
      return;
    }
    setBusy(button, true);
    try {
      await api(`/api/sentinel/engagements/${engagementId}/findings`, {
        method: "POST",
        body: payload,
      });
      toast(t("toast.finding_saved", "Finding gespeichert."));
      await refreshEngagement(engagementId);
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false);
    }
  }

  async function submitValidation(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const result = $("#validate-result");
    const target = String(data.get("target") || "").trim();
    const scope = String(data.get("scope") || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const ports = String(data.get("ports") || "")
      .split(/[,\s]+/)
      .map((port) => port.trim())
      .filter(Boolean)
      .map(Number);
    if (!target || !scope.length) {
      toast(t("sentinel.validate.invalid", "Ungültige Eingabe."), true);
      return;
    }
    if (!result) return;
    result.hidden = false;
    try {
      const decision = await api("/api/sentinel/validate", {
        method: "POST",
        body: { target, scope, ports },
      });
      result.className = `result ${decision.allowed ? "allowed" : "denied"}`;
      result.innerHTML = `
        ${statusChip(decision.allowed ? "allowed" : "denied")}
        <p>${escapeHtml(decision.reason || "")}</p>
        <p class="item-meta">${escapeHtml(decision.host || "–")}:${escapeHtml(
          decision.port || "–"
        )} · ${escapeHtml(decision.kind || "")}</p>`;
    } catch (error) {
      result.className = "result denied";
      result.innerHTML = `${statusChip("denied")}<p>${escapeHtml(error.message)}</p>`;
    }
  }

  /* ---------- Modelle / Provider ---------- */

  let providers = [];

  async function loadProviders() {
    try {
      const data = await api("/api/providers");
      providers = data.providers || [];
      renderProviders();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function currentProviderId() {
    return (state.config && state.config.provider) || "mock";
  }

  function providerById(id) {
    return providers.find((item) => item.id === id) || null;
  }

  function providerLabel(provider) {
    return state.lang === "en" ? provider.label_en || provider.label : provider.label_de || provider.label;
  }

  function groupLabel(group) {
    const map = {
      cloud: t("provider.group_cloud", "Cloud"),
      local: t("provider.group_local", "Lokal"),
      selfhosted: t("provider.group_selfhosted", "Selbst gehostet"),
      custom: t("provider.group_custom", "Eigener Endpunkt"),
    };
    return map[group] || group;
  }

  function renderProviders() {
    const grid = $("#provider-grid");
    if (!grid) return;
    if (!providers.length) {
      grid.innerHTML = `<p class="empty">${escapeHtml(t("common.loading", "Lädt …"))}</p>`;
      return;
    }
    const active = currentProviderId();
    const groups = [];
    const seen = new Set();
    providers.forEach((provider) => {
      const key = provider.group || "cloud";
      if (seen.has(key)) return;
      seen.add(key);
      groups.push(key);
    });

    grid.innerHTML = groups
      .map((group) => {
        const items = providers
          .filter((provider) => (provider.group || "cloud") === group)
          .map((provider) => {
            const selected = provider.id === active;
            const tags = [];
            if (selected) tags.push(`<span class="provider-tag current">${escapeHtml(t("provider.selected", "Ausgewaehlt"))}</span>`);
            if (provider.id === "openrouter" || provider.models.some((model) => String(model.id).endsWith(":free")))
              tags.push(`<span class="provider-tag free">${escapeHtml(t("provider.free", "kostenlos"))}</span>`);
            const modelCount = provider.models.length;
            if (modelCount)
              tags.push(`<span class="provider-tag">${modelCount} ${escapeHtml(t("provider.models", "Modelle"))}</span>`);
            return `
              <button type="button" class="provider-card" data-provider="${escapeHtml(
                provider.id
              )}" aria-pressed="${selected}">
                <span class="provider-name">${escapeHtml(providerLabel(provider))}</span>
                <span class="provider-meta">${escapeHtml(provider.base_url || "–")}</span>
                <span class="provider-tags">${tags.join("")}</span>
              </button>`;
          })
          .join("");
        return `<div class="provider-group"><p class="label">${escapeHtml(groupLabel(group))}</p>
          <div class="provider-grid">${items}</div></div>`;
      })
      .join("");
    renderProviderConfig();
  }

  function renderProviderConfig() {
    const card = $("#provider-config-card");
    if (!card) return;
    const provider = providerById(activeProviderId());
    if (!provider) {
      card.hidden = true;
      return;
    }
    card.hidden = false;
    $("#provider-config-title").textContent = providerLabel(provider);
    $("#provider-base-url").value = (state.config && state.config.provider === provider.id && state.config.provider_base_url) || provider.base_url || "";
    $("#provider-model").value = (state.config && state.config.models && state.config.models.pro) || provider.defaults.pro || "";
    $("#provider-api-key").value = "";
    $("#provider-api-key").placeholder = (state.config && state.config.api_key_set)
      ? t("provider.key_set", "Key gesetzt")
      : t("provider.key_missing", "kein Key gesetzt");
    const badge = $("#provider-key-state");
    if (badge) {
      const hasKey = provider.needs_key && state.config && state.config.api_key_set;
      badge.textContent = hasKey ? t("provider.key_set", "Key gesetzt") : t("provider.key_missing", "kein Key gesetzt");
    }
    const docs = $("#provider-docs");
    const keys = $("#provider-keys");
    if (docs) {
      docs.hidden = !provider.docs;
      if (provider.docs) docs.href = provider.docs;
    }
    if (keys) {
      keys.hidden = !provider.key_url;
      if (provider.key_url) keys.href = provider.key_url;
    }
    const result = $("#provider-test-result");
    if (result) result.hidden = true;
  }

  async function testProvider(button) {
    const provider = providerById(activeProviderId());
    if (!provider) return;
    const result = $("#provider-test-result");
    if (!result) return;
    result.hidden = false;
    result.className = "result";
    result.innerHTML = `<p class="empty">${escapeHtml(t("provider.testing", "Teste ..."))}</p>`;
    setBusy(button, true, t("provider.testing", "Teste ..."));
    try {
      const body = {
        provider: provider.id,
        base_url: $("#provider-base-url").value.trim() || null,
        api_key: $("#provider-api-key").value.trim() || null,
        model: $("#provider-model").value.trim() || null,
      };
      const data = await api("/api/providers/test", { method: "POST", body });
      result.className = `result ${data.ok ? "allowed" : "denied"}`;
      result.innerHTML = `${statusChip(data.ok ? "allowed" : "denied")}
        <p>${escapeHtml(data.message || "")}</p>
        ${
          data.sample
            ? `<div class="call-section"><h4>${escapeHtml(t("provider.sample", "Antwort des Modells"))}</h4><pre>${escapeHtml(
                data.sample
              )}</pre></div>`
            : ""
        }`;
    } catch (error) {
      result.className = "result denied";
      result.innerHTML = `${statusChip("denied")}<p>${escapeHtml(error.message)}</p>`;
    } finally {
      setBusy(button, false, t("provider.test", "Verbindung testen"));
    }
  }

  async function saveProvider(button) {
    const provider = providerById(activeProviderId());
    if (!provider) return;
    setBusy(button, true);
    try {
      const data = await api("/api/providers/select", {
        method: "POST",
        body: {
          provider: provider.id,
          base_url: $("#provider-base-url").value.trim() || provider.base_url || "",
          api_key: $("#provider-api-key").value.trim() || "",
          model: $("#provider-model").value.trim() || provider.defaults.pro || "",
        },
      });
      toast(data.message || t("toast.provider_saved", "Standard gespeichert."));
      $("#provider-api-key").value = "";
      await loadConfig();
      await loadProviders();
      renderProviderConfig();
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(button, false, t("provider.save", "Als Standard speichern"));
    }
  }

  /* ---------- System ---------- */

  async function loadConfig() {
    try {
      state.config = await api("/api/config");
      const config = state.config;
      const demo = $("#mode-badge-demo");
      const live = $("#mode-badge-live");
      if (demo) demo.hidden = !config.mock;
      if (live) live.hidden = Boolean(config.mock);
      $("#footer-version").textContent = `v${config.version}`;
      ["pro", "contra", "judge", "moderator"].forEach((role) => {
        const field = $(`#model-${role}`);
        if (field) field.placeholder = (config.models && config.models[role]) || "";
      });
      const rounds = $("#debate-rounds");
      if (rounds) rounds.value = String(Math.min(Math.max(1, config.default_rounds || 4), 2000));
      renderModeBadges();
      return config;
    } catch (error) {
      toast(error.message, true);
      return null;
    }
  }

  async function loadSystem() {
    try {
      const [config, health] = await Promise.all([api("/api/config"), api("/api/health")]);
      state.config = config;
      state.health = health;
      renderModeBadges();
      renderSystem();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderModeBadges() {
    if (!state.config) return;
    const demo = $("#mode-badge-demo");
    const live = $("#mode-badge-live");
    if (demo) demo.hidden = !state.config.mock;
    if (live) live.hidden = Boolean(state.config.mock);
  }

  function renderSystem() {
    const config = state.config;
    const health = state.health;
    if (!config) return;
    $("#sys-provider").textContent = config.provider || "–";
    $("#sys-provider-label").textContent = config.provider_label || "";
    $("#sys-db").textContent =
      health && health.database ? t("system.db_ok", "Datenbank erreichbar") : t("system.db_fail", "Datenbank nicht erreichbar");
    $("#sys-db").className = health && health.database ? "ok-text" : "danger-text";
    $("#sys-exec").textContent = config.pentest_execution_enabled ? t("common.yes", "Ja") : t("common.no", "Nein");
    $("#sys-exec").className = config.pentest_execution_enabled ? "danger-text" : "ok-text";
    $("#sys-public").textContent = config.allow_public_targets ? t("common.yes", "Ja") : t("common.no", "Nein");
    $("#sys-public").className = config.allow_public_targets ? "danger-text" : "ok-text";
    $("#sys-version").textContent = `v${config.version} · ${config.lang}`;
    const mock = Boolean(config.mock);
    $("#sys-mode-note").textContent = mock
      ? t("system.mock_note", "Demo-Modus: Alle LLM-Antworten werden deterministisch lokal erzeugt.")
      : t("system.live_note", "Live-Modus: Anfragen gehen an den konfigurierten Provider.");
  }

  /* ---------- Navigation & Events ---------- */

  function activateTab(name, options = {}) {
    const valid = ["arena", "sentinel", "providers", "system"];
    const target = valid.includes(name) ? name : "arena";
    $$(".tab").forEach((tab) => {
      const active = tab.dataset.panel === target;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && options.focus) tab.focus();
    });
    $$(".panel").forEach((panel) => {
      panel.hidden = panel.id !== `panel-${target}`;
    });
    if (options.updateHash !== false) history.replaceState(null, "", `#${target}`);
    if (target === "sentinel") loadEngagements();
    if (target === "providers") loadProviders();
    if (target === "system") loadSystem();
  }

  function setDefaultDates() {
    const from = $("#eng-from");
    const until = $("#eng-until");
    if (!from || !until || from.value || until.value) return;
    const today = new Date();
    const future = new Date(today);
    future.setDate(future.getDate() + 30);
    const iso = (date) => date.toISOString().slice(0, 10);
    from.value = iso(today);
    until.value = iso(future);
  }

  function bindStaticEvents() {
    const tabs = $$(".tab");
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activateTab(tab.dataset.panel));
      tab.addEventListener("keydown", (event) => {
        let next = null;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (next) {
          event.preventDefault();
          activateTab(next.dataset.panel, { focus: true });
        }
      });
    });

    $$("[data-set-lang]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.setLang !== state.lang) setLanguage(button.dataset.setLang);
      });
    });

    $("#debate-form")?.addEventListener("submit", submitDebate);
    $("#demo-topic")?.addEventListener("click", () => {
      const topic = $("#debate-topic");
      if (topic) {
        topic.value = t("arena.form.demo_topic", "");
        topic.focus();
      }
    });
    $("#debates-refresh")?.addEventListener("click", () => loadDebates());
    $("#debate-more")?.addEventListener("click", () => {
      state.debateLimit += 20;
      loadDebates(false);
    });

    $("#engagement-form")?.addEventListener("submit", submitEngagement);
    $("#engagements-refresh")?.addEventListener("click", loadEngagements);
    $("#validate-form")?.addEventListener("submit", submitValidation);

    $("#provider-grid")?.addEventListener("click", (event) => {
      const card = event.target.closest("[data-provider]");
      if (!card) return;
      $$("[data-provider]").forEach((element) =>
        element.setAttribute("aria-pressed", String(element === card))
      );
      $$(".provider-card").forEach((element) => element.setAttribute("aria-pressed", "false"));
      card.setAttribute("aria-pressed", "true");
      state.config = state.config || {};
      const provider = providerById(card.dataset.provider);
      if (!provider) return;
      if (state.config.provider !== provider.id) {
        state.config.provider = provider.id;
        state.config.provider_base_url = provider.base_url || "";
        state.config.api_key_set = false;
      }
      renderProviderConfig();
    });
    $("#provider-test")?.addEventListener("click", (event) => testProvider(event.currentTarget));
    $("#provider-save")?.addEventListener("click", (event) => saveProvider(event.currentTarget));

    $("#fork-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      forkDebate($("#fork-submit"));
    });
    $("#fork-cancel")?.addEventListener("click", () => $("#fork-dialog")?.close());
    $("#fork-dialog")?.addEventListener("click", (event) => {
      if (event.target === event.currentTarget) event.currentTarget.close();
    });

    $("#token-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = String(new FormData(event.currentTarget).get("token") || "").trim();
      localStorage.setItem("ma.token", value);
      toast(t("system.token_saved", "Token gespeichert."));
    });

    document.addEventListener("click", (event) => {
      const debateButton = event.target.closest("[data-debate-id]");
      if (debateButton) {
        openDebate(debateButton.dataset.debateId);
        return;
      }
      const engagementButton = event.target.closest("[data-engagement-id]");
      if (engagementButton) {
        openEngagement(engagementButton.dataset.engagementId);
        return;
      }
      const jump = event.target.closest("[data-jump]");
      if (jump) {
        const target = document.getElementById(`round-${jump.dataset.jump}`);
        if (target) {
          target.open = true;
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        return;
      }
      const callFilter = event.target.closest("[data-call-filter]");
      if (callFilter && state.selectedDebate) {
        loadDebateCalls(state.selectedDebate.id, callFilter.dataset.callFilter);
        document.getElementById("call-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      const copyTurn = event.target.closest("[data-copy-turn]");
      if (copyTurn && state.selectedDebate) {
        const turn = (state.selectedDebate.turns || []).find((item) => item.id === copyTurn.dataset.copyTurn);
        if (turn) {
          copyText(
            [
              `${t("arena.round_free", "Runde")} ${turn.round_no} – ${turn.role}`,
              "",
              t("arena.steelman", "Steelman"),
              turn.steelman,
              "",
              t("arena.public_argument", "Öffentliches Argument"),
              turn.public_argument,
              "",
              t("arena.confidence", "Konfidenz"),
              String(turn.confidence),
            ].join("\n")
          );
        }
        return;
      }
      const toggle = event.target.closest("[data-transcript-toggle]");
      if (toggle) {
        state.showPrivate = !state.showPrivate;
        localStorage.setItem("ma.showPrivate", String(state.showPrivate));
        if (state.selectedDebate) renderDebateDetail(state.selectedDebate);
        return;
      }
      if (event.target.closest("[data-fork]")) {
        forkDebate(event.target.closest("[data-fork]"));
        return;
      }
      if (event.target.closest("[data-delete]")) {
        deleteDebate(event.target.closest("[data-delete]"));
        return;
      }
      const closeButton = event.target.closest("[data-close]");
      if (closeButton) {
        clearTimeout(state.pollTimer);
        if (closeButton.dataset.close === "debate") {
          state.selectedDebate = null;
          const detail = $("#debate-detail");
          if (detail) {
            detail.hidden = true;
            detail.innerHTML = "";
          }
        } else {
          state.selectedEngagement = null;
          const detail = $("#engagement-detail");
          if (detail) {
            detail.hidden = true;
            detail.innerHTML = "";
          }
        }
        return;
      }
      const actionButton = event.target.closest("[data-action]");
      if (actionButton) {
        const action = actionButton.dataset.action;
        if (action === "plan") generatePlan(actionButton);
        if (action === "approve") approveAction(actionButton);
        if (action === "reject") rejectAction(actionButton);
        if (action === "kill") killEngagement(actionButton);
        if (action === "delete-engagement") deleteEngagement(actionButton);
      }
    });

    document.addEventListener("toggle", (event) => {
      const details = event.target;
      if (!(details instanceof HTMLDetailsElement) || !details.classList.contains("transcript-round")) return;
      const summary = details.querySelector("summary span");
      const label = summary ? summary.textContent.trim() : "";
      const match = label.match(/(\d+)/);
      if (!match || !state.selectedDebate) return;
      const key = `${state.selectedDebate.id}:${match[1]}`;
      if (details.open) state.transcriptOpen.add(key);
      else state.transcriptOpen.delete(key);
    }, true);
  }

  async function init() {
    bindStaticEvents();
    setDefaultDates();
    await setLanguage(state.lang);
    await loadConfig();
    await loadProviders();
    await loadDebates();
    const token = localStorage.getItem("ma.token");
    if (token) {
      const input = $("#token-input");
      if (input) input.value = token;
    }
    const hash = location.hash.replace("#", "");
    activateTab(hash || "arena", { updateHash: false });
  }

  document.addEventListener("DOMContentLoaded", init);
})();