"use strict";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Calls Jobcu's engine. Changes carry the X-Jobcu header, which the engine requires. */
async function api(path, { method = "GET", body } = {}) {
  const options = { method, headers: {} };
  if (method !== "GET") options.headers["X-Jobcu"] = "1";
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    document.getElementById("engine-problem").hidden = false;
    throw new Error("Jobcu's engine isn't answering.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
  return data;
}

/** Creates an element. Text is always set as text, never as HTML. */
function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === false || value === null || value === undefined) continue;
    if (name === "text") node.textContent = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

function setStatus(element, kind, text) {
  element.hidden = !text;
  element.className = `status ${kind}`;
  element.textContent = text || "";
}

/** Disables a button while `work` runs, so it can't be pressed twice. */
async function busy(button, work) {
  button.disabled = true;
  try {
    return await work();
  } finally {
    button.disabled = false;
  }
}

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

const VIEWS = ["search", "settings"];
const state = { settings: null, provider: null };

function showView() {
  const requested = location.hash.replace("#/", "");
  const view = VIEWS.includes(requested) ? requested : "search";
  for (const name of VIEWS) $(`view-${name}`).hidden = name !== view;
  for (const link of document.querySelectorAll("[data-view-link]")) {
    if (link.dataset.viewLink === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (view === "search") renderChecklist();
}

// ---------------------------------------------------------------------------
// Search view: setup checklist
// ---------------------------------------------------------------------------

function renderChecklist() {
  const list = $("setup-checklist");
  const settings = state.settings;
  if (!settings) return;
  const provider = settings.providers.find((p) => p.id === settings.ai.provider);
  const items = [
    ["Choose an AI provider", Boolean(provider)],
    [
      "Save your AI key",
      Boolean(provider && (provider.key.saved || provider.key_optional)),
    ],
    ["Choose an AI model", Boolean(settings.ai.model)],
    ["Save your Adzuna keys", keySaved("adzuna_app_id") && keySaved("adzuna_app_key")],
    ["Save your Reed key", keySaved("reed_api_key")],
  ];
  $("setup-card").hidden = items.every(([, done]) => done);
  list.replaceChildren(
    ...items.map(([label, done]) =>
      el(
        "li",
        { class: done ? "done" : "" },
        el("span", { class: "mark", "aria-hidden": "true", text: done ? "✓" : "○" }),
        el("span", { text: `${label}${done ? "" : " (not done yet)"}` }),
      ),
    ),
  );
}

function keySaved(name) {
  return Boolean(state.settings.job_site_keys.find((k) => k.name === name)?.saved);
}

// ---------------------------------------------------------------------------
// Search view: documents and "What Jobcu understood"
// ---------------------------------------------------------------------------

const DOCUMENT_LABELS = { cv: "CV", cover_letter: "Cover letter" };

async function loadDocuments() {
  const data = await api("/api/documents");
  for (const row of document.querySelectorAll("[data-document]")) {
    const kind = row.dataset.document;
    renderDocumentRow(row, kind, data.documents[kind], data.accepted[kind]);
  }
}

function renderDocumentRow(row, kind, info, accepted) {
  const types = accepted.map((ext) => ext.slice(1).toUpperCase()).join(", ");
  const picker = el("input", { type: "file", accept: accepted.join(","), hidden: true });
  const message = el("span", { class: "doc-message", role: "alert" });
  const chooseButton = el("button", {
    type: "button",
    class: info ? "secondary" : "",
    text: info ? "Replace" : "Choose file…",
    onclick: () => picker.click(),
  });

  picker.addEventListener("change", async () => {
    const file = picker.files[0];
    if (!file) return;
    message.textContent = "";
    await busy(chooseButton, async () => {
      chooseButton.textContent = "Reading…";
      try {
        const saved = await uploadDocument(kind, file);
        renderDocumentRow(row, kind, saved, accepted);
      } catch (error) {
        chooseButton.textContent = info ? "Replace" : "Choose file…";
        message.textContent = error.message;
      }
    });
  });

  const actions = el("div", { class: "doc-actions" }, chooseButton);
  if (info) {
    actions.append(
      el("button", {
        type: "button",
        class: "link",
        text: "Remove",
        onclick: async (event) => {
          if (!confirm(`Remove your ${DOCUMENT_LABELS[kind].toLowerCase()} from Jobcu?`)) return;
          await busy(event.target, async () => {
            await api(`/api/documents/${kind}`, { method: "DELETE" });
            renderDocumentRow(row, kind, null, accepted);
          });
        },
      }),
    );
  }

  const name = info
    ? el(
        "span",
        { class: "doc-name" },
        el("span", { text: info.original_name }),
        el("small", { class: "muted", text: ` · added ${formatDate(info.uploaded_at)}` }),
      )
    : el("span", { class: "doc-name muted", text: `Not added yet (${types})` });

  row.replaceChildren(
    el("span", { class: "doc-label", text: DOCUMENT_LABELS[kind] }),
    name,
    actions,
    picker,
    message,
  );
}

async function uploadDocument(kind, file) {
  const form = new FormData();
  form.append("file", file);
  let response;
  try {
    response = await fetch(`/api/documents/${kind}`, {
      method: "POST",
      headers: { "X-Jobcu": "1" },
      body: form,
    });
  } catch {
    $("engine-problem").hidden = false;
    throw new Error("Jobcu's engine isn't answering.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Jobcu couldn't add this file.");
  return data;
}

function formatDate(isoText) {
  return new Date(isoText).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const SENIORITY = {
  student: "Student",
  graduate_or_entry: "Graduate / entry level",
  junior: "Junior",
  mid: "Mid-level",
  senior: "Senior",
  lead_or_principal: "Lead / principal",
  unclear: "Unclear",
};
const WORK_MODE = {
  remote: "Remote",
  hybrid: "Hybrid",
  on_site: "On-site",
  flexible: "Flexible",
  not_stated: "Not stated",
};

function renderProfile(profile) {
  const section = (title, ...content) =>
    el("section", { class: "profile-section" }, el("h3", { text: title }), ...content);
  const text = (value, fallback = "Not stated") =>
    el("p", { class: value ? "" : "muted", text: value || fallback });
  const chips = (items) =>
    items.length
      ? el("ul", { class: "chips" }, ...items.map((item) => el("li", { text: item })))
      : text("");
  const bullets = (items, fallback = "None stated") =>
    items.length ? el("ul", {}, ...items.map((item) => el("li", { text: item }))) : text("", fallback);

  const years =
    profile.years_of_experience === null ? "Not clear" : `About ${profile.years_of_experience} years`;
  const languages = profile.languages.map((lang) => {
    let level = lang.level_as_written || "level not stated";
    if (lang.cefr) {
      const cefr = lang.cefr === "native" ? "native" : lang.cefr;
      level += lang.cefr_is_estimate ? ` (about ${cefr}, estimated)` : ` (${cefr})`;
    }
    return `${lang.language}: ${level}`;
  });
  const education = profile.education.map((item) =>
    [item.degree, item.institution, item.finished].filter(Boolean).join(" · "),
  );

  return [
    section("Summary", text(profile.summary)),
    section("Current or most recent role", text(profile.current_or_last_role)),
    section("Field", text(profile.field)),
    section(
      "Experience",
      text(`${years} · ${SENIORITY[profile.seniority]}`),
      el("p", { class: "muted", text: profile.experience_note }),
    ),
    section("Skills", chips(profile.skills)),
    section("Technical areas", chips(profile.technical_areas)),
    section("Education", bullets(education, "Not stated")),
    section("Languages", bullets(languages, "Not stated")),
    section("Roles you're looking for", chips(profile.target_roles)),
    section("Fields you're looking for", chips(profile.target_fields)),
    section("Preferences", bullets(profile.preferences)),
    section("Remote, hybrid or on-site", text(WORK_MODE[profile.work_mode_preference])),
    section("Dealbreakers", bullets(profile.dealbreakers)),
    section(
      "Work permit or visa",
      text(profile.work_authorisation, "Not stated in your documents, so Jobcu doesn't assume anything."),
    ),
    section(
      "Left out because it was about one specific application",
      bullets(profile.ignored_as_application_specific, "Nothing"),
    ),
  ];
}

function setUpDocumentActions() {
  $("close-profile").addEventListener("click", () => $("profile-dialog").close());
  $("show-profile").addEventListener("click", (event) =>
    busy(event.target, async () => {
      setStatus($("profile-status"), "", "Reading your documents. This can take up to a minute…");
      try {
        const result = await api("/api/profile/preview", { method: "POST" });
        if (result.error) {
          setStatus($("profile-status"), "problem", result.error);
          return;
        }
        setStatus($("profile-status"), "", "");
        $("profile-content").replaceChildren(...renderProfile(result.profile));
        $("profile-dialog").showModal();
      } catch (error) {
        setStatus($("profile-status"), "problem", error.message);
      }
    }),
  );
}

// ---------------------------------------------------------------------------
// Settings view
// ---------------------------------------------------------------------------

async function loadSettings() {
  state.settings = await api("/api/settings");
  state.provider = state.settings.ai.provider;
  renderProviderOptions();
  renderProviderDetails();
  for (const row of document.querySelectorAll("[data-key-name]")) {
    const status = state.settings.job_site_keys.find((k) => k.name === row.dataset.keyName);
    renderKeyRow(row, status, status.label);
  }
  renderChecklist();
}

function renderProviderOptions() {
  $("provider-options").replaceChildren(
    ...state.settings.providers.map((provider) =>
      el(
        "label",
        { class: "provider-option" },
        el("input", {
          type: "radio",
          name: "provider",
          value: provider.id,
          checked: provider.id === state.provider,
          onchange: () => {
            state.provider = provider.id;
            renderProviderDetails();
          },
        }),
        el("span", { text: provider.name }),
      ),
    ),
  );
}

function currentProvider() {
  return state.settings.providers.find((p) => p.id === state.provider);
}

function renderProviderDetails() {
  const provider = currentProvider();
  $("provider-details").hidden = !provider;
  if (!provider) return;

  // Model names belong to one provider, so switching provider starts empty.
  const saved = state.settings.ai;
  const same = provider.id === saved.provider;
  $("model").value = same ? saved.model : "";
  $("reasoning-model").value = same ? saved.reasoning_model : "";
  $("base-url").value = same ? saved.base_url : "";
  $("model-list").replaceChildren();
  $("model-list-status").textContent = "";
  setStatus($("ai-status"), "", "");

  $("key-page-line").hidden = !provider.key_page;
  if (provider.key_page) $("key-page-link").href = provider.key_page;
  $("base-url-field").hidden = !provider.needs_base_url;
  $("ai-key-label").textContent = provider.key_optional
    ? "API key (only if the provider needs one)"
    : "API key";
  renderKeyRow($("ai-key-row"), provider.key, $("ai-key-label").textContent);
}

/** Shows "Saved (ends in ••••abcd)" with Replace/Remove, or an input with Save. */
function renderKeyRow(row, status, label, editing = false) {
  const update = (newStatus) => {
    Object.assign(status, newStatus);
    renderKeyRow(row, status, label);
    renderChecklist();
  };

  if (status.saved && !editing) {
    row.replaceChildren(
      el("span", { class: "key-saved", text: `Saved (ends in ${status.hint})` }),
      el("button", {
        type: "button",
        class: "secondary",
        text: "Replace",
        onclick: () => renderKeyRow(row, status, label, true),
      }),
      el("button", {
        type: "button",
        class: "link",
        text: "Remove",
        onclick: async (event) => {
          if (!confirm(`Remove the saved ${label}?`)) return;
          await busy(event.target, async () =>
            update(await api(`/api/keys/${status.name}`, { method: "DELETE" })),
          );
        },
      }),
    );
    return;
  }

  const input = el("input", {
    type: "password",
    autocomplete: "off",
    spellcheck: "false",
    "aria-label": label,
    placeholder: "Paste here",
  });
  const message = el("small", { class: "muted" });
  const save = el("button", { type: "submit", text: "Save" });
  // A form, so pressing Enter in the box saves too.
  const form = el(
    "form",
    {
      class: "key-row",
      onsubmit: async (event) => {
        event.preventDefault();
        if (!input.value.trim()) {
          message.textContent = "Please paste the key first.";
          return;
        }
        await busy(save, async () => {
          try {
            const body = { value: input.value };
            update(await api(`/api/keys/${status.name}`, { method: "PUT", body }));
          } catch (error) {
            message.textContent = error.message;
          }
        });
      },
    },
    input,
    save,
  );
  if (status.saved) {
    form.append(
      el("button", {
        type: "button",
        class: "link",
        text: "Cancel",
        onclick: () => renderKeyRow(row, status, label),
      }),
    );
  }
  row.replaceChildren(form, message);
}

async function saveAiChoice() {
  const body = {
    provider: state.provider,
    model: $("model").value,
    reasoning_model: $("reasoning-model").value,
    base_url: $("base-url").value,
  };
  // Only the AI part is replaced, so the key rows keep their live status objects.
  state.settings.ai = (await api("/api/settings/ai", { method: "PUT", body })).ai;
  renderChecklist();
}

function setUpSettingsActions() {
  $("save-ai").addEventListener("click", (event) =>
    busy(event.target, async () => {
      try {
        await saveAiChoice();
        setStatus($("ai-status"), "ok", "Saved.");
      } catch (error) {
        setStatus($("ai-status"), "problem", error.message);
      }
    }),
  );

  $("check-ai").addEventListener("click", (event) =>
    busy(event.target, async () => {
      setStatus($("ai-status"), "", "Testing the connection. This can take up to a minute…");
      try {
        await saveAiChoice();
        const result = await api("/api/ai/check", { method: "POST" });
        setStatus($("ai-status"), result.ok ? "ok" : "problem", result.message);
      } catch (error) {
        setStatus($("ai-status"), "problem", error.message);
      }
    }),
  );

  $("load-models").addEventListener("click", (event) =>
    busy(event.target, async () => {
      const status = $("model-list-status");
      status.textContent = "Asking the provider for its models…";
      try {
        const result = await api("/api/ai/models", {
          method: "POST",
          body: { provider: state.provider, base_url: $("base-url").value },
        });
        if (result.error) {
          status.textContent = result.error;
          return;
        }
        $("model-list").replaceChildren(...result.models.map((name) => el("option", { value: name })));
        status.textContent = result.models.length
          ? `${result.models.length} models found. Click the Model box to pick one.`
          : "The provider didn't list any models. You can type a model name instead.";
      } catch (error) {
        status.textContent = error.message;
      }
    }),
  );

  for (const button of document.querySelectorAll("[data-check-site]")) {
    const site = button.dataset.checkSite;
    button.addEventListener("click", () =>
      busy(button, async () => {
        setStatus($(`${site}-status`), "", "Testing…");
        try {
          const result = await api(`/api/job-sites/${site}/check`, { method: "POST" });
          setStatus($(`${site}-status`), result.ok ? "ok" : "problem", result.message);
        } catch (error) {
          setStatus($(`${site}-status`), "problem", error.message);
        }
      }),
    );
  }
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function start() {
  window.addEventListener("hashchange", showView);
  setUpSettingsActions();
  setUpDocumentActions();
  showView();
  try {
    const about = await api("/api/about");
    $("about-version").textContent = `Jobcu ${about.version}`;
    $("about-copyright").textContent = about.copyright;
    $("footer-copyright").textContent = about.copyright;
    $("about-data-folder").textContent = about.data_folder;
    await Promise.all([loadSettings(), loadDocuments()]);
  } catch {
    // The engine problem message is already visible.
  }
}

start();
