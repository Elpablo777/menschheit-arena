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
    engagements: [],
    selectedDebate: null,
    selectedEngagement: null,
    pollTimer: null,
  };

  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ESCAPES[character]);
  }

  function t(key, fallback) {
    return state.messages[key] || fallback || key;
  }

  function langLabel(language) {
    return language === "en" ? t("lang.en", "Englisch") : t("lang.de", "Deutsch");
  }

  function statusLabel(status) {
    return state.messages[`status.${status}`] || status || "–";
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

  function formatDay(value) {
    if (!value) return "–";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(state.lang === "de" ? "de-DE" : "en-GB", {
      dateStyle: "medium",
    }).format(date);
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
      element.textContent = t(element.dataset.i18n, element.textContent);
    });
    $$("[data-i18n-placeholder]").forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder, element.placeholder);
    });
    $$("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel, element.getAttribute("aria-label") || ""));
    });
    document.title = t("app.name", "Menschheit Arena");
  }

  async function setLanguage(language) {
    try {
      const data = await api(`/api/i18n/${language}`);
      state.lang = data.lang || language;
      state.messages = data.messages || {};
      localStorage.setItem("ma.lang", state.lang);
      document.documentElement.lang = state.lang;
      document.documentElement.dataset.lang = state.lang;
      $$("[data-set-lang]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.setLang === state.lang));
      });
      applyI18n();
      renderModeBadges();
      renderDebateList();
      renderEngagementList();
      if (state.selectedDebate) renderDebateDetail(state.selectedDebate);
      if (state.selectedEngagement) renderEngagementDetail(state.selectedEngagement);
      if (state.config && state.health) renderSystem();
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
    }, isError ? 7000 : 4000);
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.original = button.textContent;
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

  /* ---------- Arena ---------- */

  async function loadDebates() {
    try {
      state.debates = await api("/api/arena/debates");
      renderDebateList();
    } catch (error) {
      toast(error.message, true);
    }
  }

  function renderDebateList() {
    const list = $("#debate-list");
    if (!list) return;
    if (!state.debates.length) {
      list.innerHTML = `<p class="empty">${escapeHtml(t("arena.history.empty", "Noch keine Debatte."))}</p>`;
      return;
    }
    list.innerHTML = state.debates
      .map(
        (debate) => `
        <button type="button" class="list-item" data-debate-id="${escapeHtml(debate.id)}">
          <span class="item-main">
            <span class="item-title">${escapeHtml(debate.topic)}</span>
            <span class="item-meta">${escapeHtml(formatDate(debate.created_at))} · ${escapeHtml(
              langLabel(debate.language)
            )}</span>
          </span>
          ${statusChip(debate.status)}
        </button>`
      )
      .join("");
  }

  async function openDebate(debateId, scroll = true) {
    clearTimeout(state.pollTimer);
    const detail = $("#debate-detail");
    if (!detail) return;
    detail.hidden = false;
    detail.innerHTML = `<p class="empty">${escapeHtml(t("arena.detail.loading", "Debatte wird geladen …"))}</p>`;
    try {
      const debate = await api(`/api/arena/debates/${debateId}`);
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
        const debate = await api(`/api/arena/debates/${debateId}`);
        state.selectedDebate = debate;
        renderDebateDetail(debate);
        if (["pending", "running"].includes(debate.status)) {
          scheduleDebatePoll(debateId);
        } else {
          loadDebates();
        }
      } catch {
        /* Netzwerk-Hiccup: kein harter Abbruch der Ansicht. */
      }
    }, 1400);
  }

  function renderDebateDetail(debate) {
    const detail = $("#debate-detail");
    if (!detail) return;
    const models = debate.models || {};
    const turns = debate.turns || [];
    const moderations = debate.moderations || [];
    const judgment = debate.judgment;
    const roundCount = new Set(turns.map((turn) => turn.round_no)).size || debate.rounds_requested;
    const meta = [
      formatDate(debate.created_at),
      langLabel(debate.language),
      `${t("arena.detail.rounds_meta", "Runden")}: ${roundCount}`,
      `Pro: ${models.pro || "–"} · Contra: ${models.contra || "–"} · Judge: ${models.judge || "–"} · Mod: ${
        models.moderator || "–"
      }`,
    ].join(" · ");

    const reportLink = judgment
      ? `<a class="btn secondary small" href="/api/arena/debates/${encodeURIComponent(
          debate.id
        )}/report.md">${escapeHtml(t("arena.report_download", "Bericht als Markdown"))}</a>`
      : "";

    const progress = ["pending", "running"].includes(debate.status)
      ? `<div class="progress-line">${escapeHtml(t("arena.detail.progress", "Fortschritt"))}: ${escapeHtml(
          debate.progress || debate.status
        )}</div>`
      : "";

    detail.innerHTML = `
      <header class="detail-head">
        <div>
          <p class="kicker">${escapeHtml(t("arena.detail.title", "Debattenprotokoll"))}</p>
          <h2>${escapeHtml(debate.topic)}</h2>
          <p class="meta-line">${escapeHtml(meta)}</p>
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
      ${renderJudgment(judgment)}
      <h3>${escapeHtml(t("arena.turns", "Züge"))}</h3>
      ${renderRounds(turns, moderations)}
    `;
  }

  function renderJudgment(judgment) {
    if (!judgment) {
      return `<p class="hint">${escapeHtml(
        t("arena.detail.judge_pending", "Das Urteil erscheint, sobald alle Runden abgeschlossen sind.")
      )}</p>`;
    }
    const average = (judgment.toulmin && judgment.toulmin.average) || {};
    const winner = (judgment.toulmin && judgment.toulmin.winner) || (judgment.pass_ab && judgment.pass_ab.winner) || "draw";
    const bias = Number(judgment.bias_delta || 0);
    const summary =
      (judgment.pass_ab && judgment.pass_ab.summary) || (judgment.pass_ba && judgment.pass_ba.summary) || "";
    const winnerLabel =
      winner === "pro"
        ? t("arena.turn.pro", "Pro Menschheit")
        : winner === "contra"
        ? t("arena.turn.contra", "Contra / Skeptiker")
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
                )}</summary><ul>${conflicts
                  .map((item) => `<li>${escapeHtml(item)}</li>`)
                  .join("")}</ul></details>`
              : ""
          }
          ${
            rules.length
              ? `<details class="private"><summary>${escapeHtml(
                  t("report.rules", "Konkrete Architektur- & Verfassungsregeln")
                )}</summary><ul>${rules
                  .map((item) => `<li>${escapeHtml(item)}</li>`)
                  .join("")}</ul></details>`
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

  function renderRounds(turns, moderations) {
    if (!turns.length) {
      return `<p class="empty">${escapeHtml(t("arena.detail.no_turns", "Noch keine Beiträge."))}</p>`;
    }
    const rounds = [...new Set(turns.map((turn) => turn.round_no))].sort((a, b) => a - b);
    return rounds
      .map((round) => {
        const pro = turns.find((turn) => turn.round_no === round && turn.role === "pro");
        const contra = turns.find((turn) => turn.round_no === round && turn.role === "contra");
        const moderation = moderations.find((item) => item.round_no === round);
        return `
          <section class="round">
            <header class="round-head">
              <h4>${escapeHtml(t("arena.round", "Runde"))} ${round}</h4>
              ${moderation ? statusChip(moderation.decision) : ""}
            </header>
            <div class="turns">
              ${pro ? renderTurn(pro) : ""}
              ${contra ? renderTurn(contra) : ""}
            </div>
            ${moderation ? renderModeration(moderation) : ""}
          </section>`;
      })
      .join("");
  }

  function renderTurn(turn) {
    const isPro = turn.role === "pro";
    const confidence = Math.max(0, Math.min(100, Number(turn.confidence) || 0));
    const conceded = Array.isArray(turn.conceded_claims) ? turn.conceded_claims : [];
    const meterColor = confidence <= 25 ? "background:var(--danger)" : "";
    return `
      <article class="turn" data-role="${isPro ? "pro" : "contra"}">
        <header class="turn-head">
          <span class="role-pill">${escapeHtml(
            isPro ? t("arena.turn.pro", "Pro Menschheit") : t("arena.turn.contra", "Contra / Skeptiker")
          )}</span>
          <span class="confidence">${escapeHtml(t("arena.confidence", "Konfidenz"))} <strong>${confidence}</strong></span>
        </header>
        <div class="confidence-bar"><span style="width:${confidence}%;${meterColor}"></span></div>
        <p class="label">${escapeHtml(t("arena.steelman", "Steelman des Gegners"))}</p>
        <p class="prose">${escapeHtml(turn.steelman || "–")}</p>
        <p class="label">${escapeHtml(t("arena.public_argument", "Öffentliches Argument"))}</p>
        <p class="prose">${escapeHtml(turn.public_argument || "")}</p>
        <details class="private">
          <summary>${escapeHtml(
            t("arena.internal_reasoning", "Internes Reasoning (archiviert, für Gegner unsichtbar)")
          )}</summary>
          <p class="prose">${escapeHtml(turn.internal_reasoning || "–")}</p>
          <p class="label">${escapeHtml(t("arena.conceded", "Zugestandene Punkte"))}</p>
          ${
            conceded.length
              ? `<ul>${conceded.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : `<p class="prose">${escapeHtml(t("common.none", "Keine"))}</p>`
          }
          <p class="label">${escapeHtml(t("arena.falsification", "Falsifikationsbedingung"))}</p>
          <p class="prose">${escapeHtml(turn.falsification || "–")}</p>
        </details>
      </article>`;
  }

  function renderModeration(moderation) {
    const flags = [];
    if (moderation.sycophancy) flags.push(t("arena.sycophancy", "Sycophancy erkannt"));
    if (moderation.drift) flags.push(t("arena.drift", "Problem-Drift erkannt"));
    return `
      <aside class="moderation">
        <span class="moderation-label">${escapeHtml(t("arena.moderator", "Moderator & Anti-Sycophancy-Gate"))}</span>
        <p>${escapeHtml(moderation.summary || "")}</p>
        <p class="item-meta">${escapeHtml(moderation.decision || "")}${
          flags.length ? ` · ${flags.map(escapeHtml).join(" · ")}` : ""
        }</p>
        ${
          moderation.directive
            ? `<p><strong>${escapeHtml(
                t("arena.directive", "Anweisung für die nächste Runde")
              )}:</strong> ${escapeHtml(moderation.directive)}</p>`
            : ""
        }
      </aside>`;
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
    const models = {};
    [["pro", "model_pro"], ["contra", "model_contra"], ["judge", "model_judge"], ["moderator", "model_moderator"]].forEach(
      ([role, field]) => {
        const value = String(data.get(field) || "").trim();
        if (value) models[role] = value;
      }
    );
    const payload = {
      topic,
      rounds: Number(data.get("rounds") || 4),
      language: String(data.get("language") || state.lang),
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

  /* ---------- Sentinel ---------- */

  async function loadEngagements() {
    try {
      state.engagements = await api("/api/sentinel/engagements");
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
      const engagement = await api(`/api/sentinel/engagements/${engagementId}`);
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
              (state.selectedEngagement && state.selectedEngagement.authorized_by) || "human"
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
      if (rounds) rounds.value = String(Math.min(Math.max(1, config.default_rounds || 4), 8));
    } catch (error) {
      toast(error.message, true);
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
    $("#sys-db").textContent = health && health.database ? t("system.db_ok", "Datenbank erreichbar") : t("system.db_fail", "Datenbank nicht erreichbar");
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
    const target = ["arena", "sentinel", "system"].includes(name) ? name : "arena";
    $$(".tab").forEach((tab) => {
      const active = tab.dataset.panel === target;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && options.focus) tab.focus();
    });
    $$(".panel").forEach((panel) => {
      panel.hidden = panel.id !== `panel-${target}`;
    });
    if (options.updateHash !== false) {
      history.replaceState(null, "", `#${target}`);
    }
    if (target === "sentinel") loadEngagements();
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
    $("#debates-refresh")?.addEventListener("click", loadDebates);

    $("#engagement-form")?.addEventListener("submit", submitEngagement);
    $("#engagements-refresh")?.addEventListener("click", loadEngagements);
    $("#validate-form")?.addEventListener("submit", submitValidation);

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
      const closeButton = event.target.closest("[data-close]");
      if (closeButton) {
        if (closeButton.dataset.close === "debate") {
          clearTimeout(state.pollTimer);
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
      }
    });
  }

  async function init() {
    bindStaticEvents();
    setDefaultDates();
    await setLanguage(state.lang);
    await loadConfig();
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
