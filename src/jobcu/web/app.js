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

const VIEWS = ["search", "score-check", "settings"];
const state = { settings: null, provider: null, search: null, usage: null, quality: null };

function showView() {
  const requested = location.hash.replace("#/", "");
  const view = VIEWS.includes(requested) ? requested : "search";
  for (const name of VIEWS) $(`view-${name}`).hidden = name !== view;
  for (const link of document.querySelectorAll("[data-view-link]")) {
    if (link.dataset.viewLink === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (view === "search") renderChecklist();
  if (view === "score-check") loadQuality();
}

// ---------------------------------------------------------------------------
// Search view: setup checklist
// ---------------------------------------------------------------------------

function renderChecklist() {
  const list = $("setup-checklist");
  const settings = state.settings;
  if (!settings) return;
  const provider = settings.providers.find((p) => p.id === settings.ai.provider);
  // Only the AI steps are needed; the job site keys just add two more sites.
  const items = [
    ["Choose an AI provider", Boolean(provider), false],
    [
      "Save your AI key",
      Boolean(provider && (provider.key.saved || provider.key_optional)),
      false,
    ],
    ["Choose an AI model", Boolean(settings.ai.model), false],
    [
      "Save your Adzuna keys",
      keySaved("adzuna_app_id") && keySaved("adzuna_app_key"),
      true,
    ],
    ["Save your Reed key", keySaved("reed_api_key"), true],
  ];
  $("setup-card").hidden = items.every(([, done, optional]) => done || optional);
  list.replaceChildren(
    ...items.map(([label, done, optional]) =>
      el(
        "li",
        { class: done ? "done" : "" },
        el("span", { class: "mark", "aria-hidden": "true", text: done ? "✓" : "○" }),
        el("span", {
          text: `${label}${done ? "" : optional ? " (optional, adds two more job sites)" : " (not done yet)"}`,
        }),
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

  const yearsText = (value, what) => (value === null ? `${what}: not clear` : `${what}: about ${value} years`);
  const years = [
    yearsText(profile.years_full_time_experience, "Full-time work"),
    yearsText(profile.years_student_or_part_time_experience, "Internships, student and part-time work"),
  ];
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
      text(`Level: ${SENIORITY[profile.seniority]}`),
      bullets(years),
      el("p", { class: "muted", text: profile.experience_note }),
    ),
    section("Skills", chips(profile.skills)),
    section("Technical areas", chips(profile.technical_areas)),
    section("Education", bullets(education, "Not stated")),
    section("Languages", bullets(languages, "Not stated")),
    section("Roles you're looking for", chips(profile.target_roles)),
    section("Fields you're looking for", chips(profile.target_fields)),
    section("Preferences", bullets(profile.preferences)),
    section(
      "Remote, hybrid or on-site wishes in your documents",
      text(WORK_MODE[profile.work_mode_preference]),
    ),
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

const POSTED_WITHIN = { 6: "6 hours", 24: "24 hours", 72: "72 hours", 168: "1 week" };

/** The choices made on the search screen, which are filters rather than part of the profile. */
function renderSearchChoices(form) {
  const section = (title, ...content) =>
    el("section", { class: "profile-section" }, el("h3", { text: title }), ...content);
  return [
    section("Posted within", el("p", { text: POSTED_WITHIN[form.posted_within_hours] })),
    section(
      "Job types",
      el("p", { text: form.job_types.map((type) => JOB_TYPE_LABELS[type]).join(", ") }),
    ),
    section(
      "Remote jobs",
      el("p", {
        text: form.exclude_remote
          ? "Left out: fully remote jobs aren't shown (hybrid and on-site jobs are)."
          : "Included",
      }),
    ),
  ];
}

function renderLocation(location) {
  const section = (title, ...content) =>
    el("section", { class: "profile-section" }, el("h3", { text: title }), ...content);
  const items = [section("Where you want to work", el("p", { text: location.understood_as }))];
  if (location.places.length) {
    items.push(
      section(
        "Places",
        el(
          "ul",
          {},
          ...location.places.map((place) =>
            el("li", {
              text:
                `${place.name}${place.local_name !== place.name ? ` (${place.local_name})` : ""}` +
                (place.radius_km ? `, within ${place.radius_km} km` : ""),
            }),
          ),
        ),
      ),
    );
  }
  const checked = (location.conditions || []).filter((c) => c.status !== "not_checked");
  if (checked.length) {
    items.push(
      section(
        "Conditions Jobcu checked",
        el("ul", { class: "conditions" }, ...checked.map(conditionLine)),
      ),
    );
  }
  const open = (location.conditions || []).filter((c) => c.status === "not_checked");
  if (open.length || location.not_checked_yet.length) {
    const lines = open.length
      ? open.map((c) => el("li", {}, el("strong", { text: `"${c.text}"` }),
                           el("span", { text: ` — ${c.note || "not checked"}` })))
      : [el("li", { text: location.not_checked_yet.join("; ") })];
    items.push(
      section(
        "Not checked",
        el("p", { class: "muted", text: "Jobcu shows these but doesn't filter on them:" }),
        el("ul", { class: "conditions" }, ...lines),
      ),
    );
  }
  return items;
}

function conditionLine(condition) {
  const how = {
    town_size: "worked out from Jobcu's own town and population figures",
    towns_that_fit: "only the places found",
    towns_to_avoid: "the places found are left out",
  }[condition.kind] || "checked";
  const how_checked =
    condition.status === "estimate"
      ? "AI estimate — please check"
      : condition.kind === "town_size"
        ? "worked out by Jobcu"
        : "checked on the web";
  const parts = [
    el("strong", { text: `"${condition.text}"` }),
    el("span", { text: ` — ${condition.understood_as} ` }),
    el("span", {
      class: condition.status === "estimate" ? "check-estimate" : "check-verified",
      text: how_checked,
    }),
  ];
  if (condition.note) parts.push(el("p", { class: "muted", text: condition.note }));
  if (condition.towns?.length) {
    const names = condition.towns.slice(0, 12).map((town) => town.name).join(", ");
    const more = condition.towns.length > 12 ? ` and ${condition.towns.length - 12} more` : "";
    parts.push(el("p", { class: "muted", text: `${how}: ${names}${more}` }));
  } else if (condition.kind === "town_size") {
    const size = condition.min_share_of_country
      ? `at least ${(condition.min_share_of_country * 100).toFixed(2)}% of the country's people`
      : `at least ${(condition.min_people || 0).toLocaleString()} people`;
    parts.push(el("p", { class: "muted", text: `Towns with ${size} (${how}).` }));
  }
  if (condition.sources?.length) {
    parts.push(
      el(
        "p",
        { class: "muted" },
        el("span", { text: "Sources: " }),
        ...condition.sources.slice(0, 5).flatMap((source, index) => [
          index ? el("span", { text: ", " }) : el("span", {}),
          el("a", { href: safeUrl(source.url), target: "_blank", rel: "noopener noreferrer",
                    text: source.title || new URL(source.url).hostname }),
        ]),
      ),
    );
  }
  return el("li", {}, ...parts);
}

function setUpDocumentActions() {
  $("close-profile").addEventListener("click", () => $("profile-dialog").close());
  $("show-profile").addEventListener("click", (event) =>
    busy(event.target, async () => {
      // After a search, show exactly what that search used. Before one, read the documents now.
      const result = state.search?.result;
      if (result?.profile) {
        $("profile-intro").textContent =
          "This is how the AI read your CV, cover letter and location in your last search. " +
          "Jobcu doesn't judge or change your documents; it only uses this to find and score jobs.";
        const parts = renderProfile(result.profile);
        if (result.location) parts.unshift(...renderLocation(result.location));
        parts.unshift(...renderSearchChoices(state.search.form));
        $("profile-content").replaceChildren(...parts);
        $("profile-dialog").showModal();
        return;
      }
      setStatus($("search-form-status"), "", "Reading your documents. This can take up to a minute…");
      try {
        const preview = await api("/api/profile/preview", { method: "POST" });
        if (preview.error) {
          setStatus($("search-form-status"), "problem", preview.error);
          return;
        }
        setStatus($("search-form-status"), "", "");
        $("profile-content").replaceChildren(...renderProfile(preview.profile));
        $("profile-dialog").showModal();
      } catch (error) {
        setStatus($("search-form-status"), "problem", error.message);
      }
    }),
  );
}

// ---------------------------------------------------------------------------
// Search view: the search form, progress and results
// ---------------------------------------------------------------------------

const JOB_TYPE_LABELS = {
  full_time_permanent: "Full-time permanent",
  fixed_term: "Fixed-term",
  part_time: "Part-time",
  internship_or_working_student: "Internship or working student",
  freelance_or_contract: "Freelance or contract",
};
const STEP_ICONS = { waiting: "○", running: "●", done: "✓", failed: "!", skipped: "–" };
let pollTimer = null;

async function loadSearchForm() {
  const form = await api("/api/search/form");
  $("location-text").value = form.location_text;
  $("posted-within").value = String(form.posted_within_hours);
  $("exclude-remote").checked = form.exclude_remote;
  $("job-types").replaceChildren(
    ...Object.entries(JOB_TYPE_LABELS).map(([value, label]) =>
      el(
        "label",
        { class: "check" },
        el("input", {
          type: "checkbox",
          name: "job-type",
          value,
          checked: form.job_types.includes(value),
        }),
        el("span", { text: label }),
      ),
    ),
  );
  const current = await api("/api/search/current");
  if (current.search) showSearch(current.search);
}

function readSearchForm() {
  return {
    location_text: $("location-text").value,
    posted_within_hours: Number($("posted-within").value),
    job_types: [...document.querySelectorAll('input[name="job-type"]:checked')].map((i) => i.value),
    exclude_remote: $("exclude-remote").checked,
  };
}

function showSearch(search) {
  state.search = search;
  const running = search.status === "running";
  $("progress-card").hidden = false;
  $("progress-title").textContent = {
    running: "Searching…",
    finished: "Search finished",
    failed: "The search stopped because of a problem",
    stopped: "Search stopped",
  }[search.status];
  $("stop-search").hidden = !running;
  $("start-search").disabled = running;

  $("search-steps").replaceChildren(
    ...search.steps.map((step) =>
      el(
        "li",
        { "data-status": step.status },
        el("span", { class: "icon", "aria-hidden": "true", text: STEP_ICONS[step.status] }),
        el("span", { class: "label", text: step.label }),
        step.detail ? el("span", { class: "step-detail", text: step.detail }) : null,
      ),
    ),
  );
  $("search-notes").replaceChildren(...search.notes.map((note) => el("li", { text: note })));
  setStatus($("search-error"), "problem", search.error || "");

  const question = search.question;
  $("search-question").hidden = !question;
  if (question) {
    $("question-text").textContent = question.message;
    $("question-yes").textContent = question.yes;
    $("question-no").textContent = question.no;
  }

  const location = search.result.location;
  if (location) {
    $("understood-as").replaceChildren(
      el("strong", { text: "Understood as: " }),
      document.createTextNode(location.understood_as),
    );
    const notes = [];
    if (location.broad) {
      notes.push("This searches every supported country, so it takes longer and uses more AI.");
    }
    if (location.outside_supported_area.length) {
      notes.push(
        `Not searched (outside the supported countries): ${location.outside_supported_area.join(", ")}`,
      );
    }
    if (location.not_checked_yet.length) {
      notes.push(
        `Not checked yet: ${location.not_checked_yet.join("; ")}. This comes with the smart location filter.`,
      );
    }
    $("location-notes").replaceChildren(...notes.map((note) => el("li", { text: note })));
  }
  $("show-details").hidden = !search.result.search_words;

  const jobs = search.result.jobs;
  $("results").hidden = !jobs;
  if (jobs) renderResults();

  clearTimeout(pollTimer);
  if (running) pollTimer = setTimeout(pollSearch, 1000);
}

async function pollSearch() {
  try {
    const current = await api("/api/search/current");
    if (current.search) showSearch(current.search);
  } catch {
    pollTimer = setTimeout(pollSearch, 3000);
  }
}

// ---------------------------------------------------------------------------
// Results: job cards
// ---------------------------------------------------------------------------

const view = { list: "results", sort: "score", showHidden: false, marked: [] };
const WORK_MODES = { remote: "Remote", hybrid: "Hybrid", on_site: "On-site" };

function renderResults() {
  const jobs = state.search.result.jobs;
  const shown = jobs.cards.length + jobs.date_unknown.length;
  const newCount = jobs.new_count;
  $("results-summary").textContent =
    `${shown} ${shown === 1 ? "job" : "jobs"} found` +
    (newCount ? `, ${newCount} new since your last search` : "");

  const dismissedNow = [...jobs.cards, ...jobs.date_unknown].filter((c) => c.state.dismissed);
  const hiddenCount = jobs.hidden.length + dismissedNow.length;
  $("show-hidden-label").textContent = hiddenCount ? `Show hidden (${hiddenCount})` : "Show hidden";

  if (view.list !== "results") {
    $("date-unknown-section").hidden = true;
    const cards = view.marked.filter((c) => view.showHidden || !c.state.dismissed);
    fillList($("job-list"), cards, `No ${view.list} jobs yet.`);
    return;
  }
  const visible = (cards) => cards.filter((c) => view.showHidden || !c.state.dismissed);
  let main = visible(jobs.cards);
  if (view.showHidden) main = main.concat(jobs.hidden);
  fillList($("job-list"), sortCards(main), "No jobs to show for this search.");
  const unknown = visible(jobs.date_unknown);
  $("date-unknown-section").hidden = !unknown.length;
  fillList($("date-unknown-list"), sortCards(unknown), "");
}

function sortCards(cards) {
  const time = (c) => (c.posted_at ? Date.parse(c.posted_at) : 0);
  const copy = [...cards];
  if (view.sort === "newest") return copy.sort((a, b) => time(b) - time(a));
  return copy.sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || time(b) - time(a));
}

function fillList(container, cards, emptyText) {
  if (!cards.length) {
    container.replaceChildren(emptyText ? el("div", { class: "card empty", text: emptyText }) : "");
    return;
  }
  container.replaceChildren(...cards.map(renderCard));
}

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

function postedLabel(card) {
  if (!card.posted_at) return "posting date unknown";
  const posted = new Date(card.posted_at);
  const now = new Date();
  if (card.date_precision === "day") {
    const days = Math.round(
      (Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) -
        Date.UTC(posted.getUTCFullYear(), posted.getUTCMonth(), posted.getUTCDate())) /
        86400000,
    );
    if (days <= 0) return "posted today";
    if (days === 1) return "posted yesterday";
    return `posted ${days} days ago`;
  }
  const hours = Math.max(0, Math.round((now - posted) / 3600000));
  if (hours < 1) return "posted within the last hour";
  if (hours < 48) return `posted ${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  return `posted ${Math.round(hours / 24)} days ago`;
}

function renderCard(card) {
  const band = card.score === null ? "" : card.score >= 75 ? "high" : card.score >= 50 ? "mid" : "";
  const title = el("h3", { class: "job-title" }, document.createTextNode(card.title));
  if (card.is_new && view.list === "results") title.append(el("span", { class: "badge new", text: "New" }));
  if (card.state.applied) title.append(el("span", { class: "badge applied", text: "Applied" }));
  else if (card.state.saved) title.append(el("span", { class: "badge saved", text: "Saved" }));
  if (card.possible_duplicate_of) {
    title.append(el("span", { class: "badge", text: "Possible duplicate" }));
  }

  const types = card.job_types.length
    ? card.job_types.map((t) => JOB_TYPE_LABELS[t]).join(" or ")
    : "Type unclear";
  const meta = [card.location || "Location not stated", WORK_MODES[card.work_mode], types,
    postedLabel(card), card.salary].filter(Boolean).join(" · ");

  const checks = el("p", { class: "job-checks" });
  for (const check of card.location_checks) {
    const statusClass = { verified: "check-verified", unclear: "check-unclear" }[check.status] ||
      "check-estimate";
    const label = check.status === "verified" && check.source
      ? `${check.label} (verified: ${check.source})`
      : check.status === "unclear" ? check.label : `${check.label} (AI estimate — please check)`;
    checks.append(el("span", { class: statusClass, text: label }));
  }
  if (card.summary_only && card.score !== null) {
    checks.append(el("span", { class: "check-estimate", text: "Scored from a short summary of the ad" }));
  }

  const link = safeUrl(card.main_link.url);
  const actions = el(
    "div",
    { class: "job-actions" },
    link
      ? el("a", {
          class: "button",
          href: link,
          target: "_blank",
          rel: "noopener noreferrer",
          text: `Open job (${card.main_link.source})`,
        })
      : null,
  );
  const also = card.also_on
    .map((copy) => ({ ...copy, url: safeUrl(copy.url) }))
    .filter((copy) => copy.url);
  if (also.length) {
    const span = el("span", { class: "also-on", text: "Also on: " });
    also.forEach((copy, i) => {
      if (i) span.append(", ");
      span.append(el("a", { href: copy.url, target: "_blank", rel: "noopener noreferrer", text: copy.source }));
    });
    actions.append(span);
  }
  actions.append(el("span", { class: "spacer" }));
  actions.append(
    stateButton(card, "saved", card.state.saved ? "Saved" : "Save"),
    stateButton(card, "applied", "Applied"),
    stateButton(card, "dismissed", card.state.dismissed ? "Undo Not interested" : "Not interested"),
  );

  return el(
    "article",
    { class: `job-card${card.state.dismissed ? " is-hidden" : ""}` },
    el(
      "div",
      { class: `score ${band}`, title: scoreTooltip(card) },
      document.createTextNode(card.score === null ? "–" : String(card.score)),
      el("small", { text: card.score === null ? "not scored" : "match" }),
    ),
    title,
    el("p", { class: "job-company", text: card.company || "Company not stated" }),
    el("p", { class: "job-meta", text: meta }),
    card.reasons.length ? el("p", { class: "job-reasons", text: card.reasons.join(" · ") }) : null,
    checks.childNodes.length ? checks : null,
    actions,
  );
}

function scoreTooltip(card) {
  if (!card.parts) return "Not scored";
  const names = {
    role_and_skills: "Role and skills (40)",
    seniority: "Seniority (20)",
    languages: "Languages (15)",
    hard_requirements: "Hard requirements (15)",
    location_and_preferences: "Location and preferences (10)",
  };
  return Object.entries(card.parts).map(([k, v]) => `${names[k]}: ${v}`).join("\n");
}

function stateButton(card, name, label) {
  return el("button", {
    type: "button",
    class: "secondary",
    "aria-pressed": String(Boolean(card.state[name])),
    text: label,
    onclick: async (event) => {
      await busy(event.target, async () => {
        const body = { [name]: !card.state[name] };
        const result = await api(`/api/jobs/${card.job_id}/state`, { method: "POST", body });
        updateCardState(card.job_id, result.state);
        renderResults();
      });
    },
  });
}

function updateCardState(jobId, newState) {
  const jobs = state.search?.result?.jobs;
  const lists = jobs ? [jobs.cards, jobs.date_unknown, jobs.hidden] : [];
  for (const list of [...lists, view.marked]) {
    for (const card of list) if (card.job_id === jobId) card.state = newState;
  }
}

async function switchList(list) {
  view.list = list;
  for (const button of document.querySelectorAll("[data-list]")) {
    button.setAttribute("aria-pressed", String(button.dataset.list === list));
  }
  view.marked = list === "results" ? [] : (await api(`/api/jobs/marked/${list}`)).cards;
  renderResults();
}

// ---------------------------------------------------------------------------
// Search details
// ---------------------------------------------------------------------------

function renderDetails(search) {
  const result = search.result;
  const section = (title, ...content) =>
    el("section", { class: "profile-section" }, el("h3", { text: title }), ...content);
  const parts = [];
  const jobs = result.jobs;
  if (jobs) {
    const row = (cells, header = false) =>
      el("tr", {}, ...cells.map((cell, i) =>
        el(header ? "th" : "td", { class: i > 1 ? "number" : "", text: String(cell) })));
    const statusText = { ok: "Worked", partial: "Partly", failed: "Failed", unavailable: "Unavailable", skipped: "Not used" };
    parts.push(
      section(
        "Job sources",
        el(
          "table",
          { class: "data-table" },
          row(["Source", "Status", "Ads found", "Only here", "Requests"], true),
          ...jobs.sources.map((s) =>
            row([s.name, statusText[s.status] + (s.message ? ` — ${s.message}` : ""), s.jobs_found, s.unique, s.requests]),
          ),
        ),
      ),
    );
    const c = jobs.counts;
    const funnel = [
      `${c.ads_found} job ads found`,
      `${c.different_jobs} different jobs after removing duplicates`,
      ...c.left_out.map((item) => `${item.count} left out: ${item.reason}`),
      `${c.unrelated} left out as clearly unrelated to what you're looking for`,
      c.not_scored ? `${c.not_scored} not scored (scoring limit)` : null,
      `${c.shown} shown`,
    ].filter(Boolean);
    const unrelated = el(
      "details",
      { class: "advanced" },
      el("summary", { text: "See the titles left out as clearly unrelated" }),
      el("ul", {}, ...c.unrelated_titles.map((t) => el("li", { text: t }))),
    );
    parts.push(section("What happened to the jobs", el("ul", {}, ...funnel.map((t) => el("li", { text: t }))),
      c.unrelated ? unrelated : null));
  }
  parts.push(section("Countries searched", el("p", { text: (result.country_names || []).join(", ") })));
  for (const language of result.languages || []) {
    const words = result.search_words.filter((w) => w.language === language.code);
    const titles = words.filter((w) => w.kind === "job_title").map((w) => w.text);
    const fields = words.filter((w) => w.kind === "field_or_skill").map((w) => w.text);
    parts.push(
      section(
        `Search words in ${language.name}`,
        el("p", { class: "muted", text: "Job titles" }),
        el("ul", { class: "chips" }, ...titles.map((t) => el("li", { text: t }))),
        el("p", { class: "muted term-group", text: "Fields and skills" }),
        el("ul", { class: "chips" }, ...fields.map((t) => el("li", { text: t }))),
      ),
    );
  }
  const usage = result.usage || {};
  const stepNames = {
    profile: "Understanding your profile",
    location: "Understanding the location",
    search_words: "Preparing search words",
    quick_pass: "Quick relevance check",
    scoring: "Scoring jobs",
  };
  const rows = Object.entries(usage).map(([step, used]) =>
    el("li", {
      text: `${stepNames[step] || step}: ${used.input_tokens.toLocaleString()} tokens in, ${used.output_tokens.toLocaleString()} tokens out`,
    }),
  );
  if (rows.length) {
    parts.push(
      section(
        "AI use in this search",
        el("p", {
          class: "muted",
          text: "Tokens are the pieces of text the AI reads and writes. Providers charge by tokens.",
        }),
        el("ul", {}, ...rows),
      ),
    );
  }
  return parts;
}

function setUpSearchActions() {
  $("search-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = readSearchForm();
    if (!form.job_types.length) {
      setStatus($("search-form-status"), "problem", "Please tick at least one job type.");
      return;
    }
    setStatus($("search-form-status"), "", "");
    await busy($("start-search"), async () => {
      try {
        if (view.list !== "results") await switchList("results");
        showSearch(await api("/api/search", { method: "POST", body: form }));
      } catch (error) {
        setStatus($("search-form-status"), "problem", error.message);
      }
    });
  });
  $("stop-search").addEventListener("click", async () => {
    if (state.search) await api(`/api/search/${state.search.id}/stop`, { method: "POST" });
  });
  for (const [id, yes] of [["question-yes", true], ["question-no", false]]) {
    $(id).addEventListener("click", async () => {
      if (!state.search) return;
      $("search-question").hidden = true;
      await api(`/api/search/${state.search.id}/answer`, { method: "POST", body: { yes } });
    });
  }
  $("show-details").addEventListener("click", () => {
    if (!state.search) return;
    $("details-content").replaceChildren(...renderDetails(state.search));
    $("details-dialog").showModal();
  });
  $("close-details").addEventListener("click", () => $("details-dialog").close());
  $("sort-order").addEventListener("change", (event) => {
    view.sort = event.target.value;
    renderResults();
  });
  $("show-hidden").addEventListener("change", (event) => {
    view.showHidden = event.target.checked;
    renderResults();
  });
  for (const button of document.querySelectorAll("[data-list]")) {
    button.addEventListener("click", () => switchList(button.dataset.list));
  }
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

// ---------------------------------------------------------------------------
// Score check
// ---------------------------------------------------------------------------

const SCORED_CHOICES = [
  ["good", "Good fit"],
  ["okay", "Okay"],
  ["poor", "Poor"],
];
const TITLE_CHOICES = [
  ["unrelated", "Right, not for me"],
  ["worth_a_look", "No, worth a look"],
];

async function loadQuality() {
  state.quality = await api("/api/quality");
  renderQuality();
}

function renderQuality() {
  const { ads, progress, blockers } = state.quality;
  $("quality-progress").textContent =
    `Jobs: ${progress.scored.rated} of ${progress.scored.collected} answered ` +
    `(Jobcu keeps up to ${progress.scored.wanted}). ` +
    `Titles: ${progress.title_only.rated} of ${progress.title_only.collected} answered.`;
  fillQuality($("quality-scored"), ads.filter((ad) => ad.kind === "scored"), blockers,
              "Run a search first: Jobcu keeps a few of its jobs here.");
  fillQuality($("quality-titles"), ads.filter((ad) => ad.kind === "title_only"), blockers,
              "Nothing left out yet.");
}

function fillQuality(container, ads, blockers, emptyText) {
  if (!ads.length) {
    container.replaceChildren(el("p", { class: "muted", text: emptyText }));
    return;
  }
  container.replaceChildren(...ads.map((ad) => qualityRow(ad, blockers)));
}

function qualityRow(ad, blockers) {
  const choices = ad.kind === "scored" ? SCORED_CHOICES : TITLE_CHOICES;
  const where = [ad.company, ad.location].filter(Boolean).join(" · ");
  const head = el(
    "div",
    { class: "quality-head" },
    el("strong", { text: ad.title }),
    el("span", { class: "muted", text: where }),
  );
  const parts = [head];
  if (ad.url) {
    parts.push(el("p", {}, el("a", { href: safeUrl(ad.url), target: "_blank",
                                     rel: "noopener noreferrer", text: "Open the ad" })));
  }
  if (ad.text) {
    parts.push(el("details", {},
      el("summary", { text: "Read the ad" }),
      el("pre", { class: "quality-text", text: ad.text })));
  }
  const buttons = choices.map(([value, label]) =>
    el("button", {
      type: "button",
      class: ad.rating === value ? "" : "secondary",
      text: label,
      onclick: () => rateAd(ad, { rating: ad.rating === value ? null : value }),
    }),
  );
  parts.push(el("div", { class: "actions" }, ...buttons,
    ad.rating && ad.score !== null
      ? el("span", { class: "muted", text: `Jobcu gave ${ad.score}` })
      : el("span", {}),
  ));
  if (ad.kind === "scored" && ad.rating && ad.rating !== "good") {
    parts.push(el("div", { class: "checks" }, ...blockers.map((blocker) => {
      const box = el("input", {
        type: "checkbox",
        ...(ad.blockers.includes(blocker.id) ? { checked: "" } : {}),
        onchange: (event) => {
          const chosen = event.target.checked
            ? [...ad.blockers, blocker.id]
            : ad.blockers.filter((id) => id !== blocker.id);
          rateAd(ad, { blockers: chosen });
        },
      });
      return el("label", { class: "check" }, box, el("span", { text: blocker.label }));
    })));
  }
  return el("div", { class: "quality-row" }, ...parts);
}

async function rateAd(ad, changes) {
  const body = {
    rating: changes.rating !== undefined ? changes.rating : ad.rating,
    blockers: changes.blockers !== undefined ? changes.blockers : ad.blockers,
    note: ad.note || "",
  };
  const result = await api(`/api/quality/${ad.id}`, { method: "PUT", body });
  Object.assign(ad, result.ad);
  state.quality.progress = result.progress;
  renderQuality();
}

// ---------------------------------------------------------------------------
// Usage, limits, prices and job sources
// ---------------------------------------------------------------------------

const PROVIDER_NAMES = {
  anthropic: "Anthropic",
  gemini: "Google",
  openai: "OpenAI",
  openai_compatible: "Other",
};

function money(part) {
  if (!part.cost && !part.cost_is_complete) return "cost unknown (no prices saved)";
  const amount = `${part.cost.toFixed(2)} ${part.currency || ""}`.trim();
  return part.cost_is_complete ? `about ${amount}` : `at least ${amount}`;
}

function tokens(count) {
  return `${count.toLocaleString()} tokens`;
}

async function loadUsage() {
  state.usage = await api("/api/usage");
  renderUsage();
}

function renderUsage() {
  const usage = state.usage;
  $("usage-month").textContent = `This month: ${tokens(usage.this_month.tokens)}, ${money(usage.this_month)}`;
  $("usage-models").replaceChildren(
    ...usage.this_month.by_model.map((row) =>
      el(
        "li",
        {},
        el("span", { text: `${PROVIDER_NAMES[row.provider] || row.provider} · ${row.model}` }),
        el("span", { class: "used", text: `${tokens(row.tokens)}, ${money(row)}` }),
      ),
    ),
  );
  $("usage-last").textContent = usage.last_search
    ? `Last search: ${tokens(usage.last_search.tokens)}, ${money(usage.last_search)}.`
    : "No search yet.";

  $("scoring-cap").value = usage.limits.scoring_cap;
  $("token-limit").value = usage.limits.monthly_token_limit ?? "";
  $("cost-limit").value = usage.limits.monthly_cost_limit ?? "";
  renderPrices(usage.prices);
  renderSources(usage.sources);
}

function priceRow(price = {}) {
  const provider = el("select", { class: "price-provider" },
    ...Object.entries(PROVIDER_NAMES).map(([id, name]) =>
      el("option", { value: id, text: name, ...(price.provider === id ? { selected: "" } : {}) }),
    ),
  );
  return el(
    "div",
    { class: "price-row" },
    provider,
    el("input", { class: "price-model", type: "text", placeholder: "Model name",
                  value: price.model || "", spellcheck: "false" }),
    el("input", { class: "price-in", type: "number", min: "0", step: "0.01",
                  placeholder: "In, per million", value: price.input_per_million ?? "" }),
    el("input", { class: "price-out", type: "number", min: "0", step: "0.01",
                  placeholder: "Out, per million", value: price.output_per_million ?? "" }),
    el("input", { class: "price-currency", type: "text", placeholder: "USD",
                  value: price.currency || "USD", size: "5" }),
    el("button", { type: "button", class: "secondary", text: "Remove",
                   onclick: (event) => event.target.closest(".price-row").remove() }),
  );
}

function renderPrices(prices) {
  $("price-rows").replaceChildren(...prices.map(priceRow));
}

function readPrices() {
  return [...document.querySelectorAll(".price-row")]
    .map((row) => ({
      provider: row.querySelector(".price-provider").value,
      model: row.querySelector(".price-model").value.trim(),
      input_per_million: Number(row.querySelector(".price-in").value || 0),
      output_per_million: Number(row.querySelector(".price-out").value || 0),
      currency: row.querySelector(".price-currency").value.trim().toUpperCase() || "USD",
    }))
    .filter((price) => price.model);
}

function renderSources(sources) {
  $("source-list").replaceChildren(
    ...sources.map((source) => {
      const box = el("input", {
        type: "checkbox",
        ...(source.enabled ? { checked: "" } : {}),
        onchange: () => saveSources(),
      });
      box.dataset.sourceId = source.id;
      const used = source.requests_this_month
        ? `${source.requests_today} requests today, ${source.requests_this_month} this month`
        : source.needs_key
          ? "needs a key in Settings"
          : "";
      return el(
        "li",
        {},
        el("label", { class: "check" }, box, el("span", { text: source.name })),
        el("span", { class: "used", text: used }),
      );
    }),
  );
}

async function saveSources() {
  const disabled = [...document.querySelectorAll("#source-list input[type=checkbox]")]
    .filter((box) => !box.checked)
    .map((box) => box.dataset.sourceId);
  try {
    state.usage = await api("/api/settings/sources", { method: "PUT", body: { disabled } });
    setStatus($("sources-status"), "ok", "Saved.");
  } catch (error) {
    setStatus($("sources-status"), "problem", error.message);
  }
}

function setUpUsageActions() {
  $("save-limits").addEventListener("click", (event) =>
    busy(event.target, async () => {
      const value = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));
      try {
        state.usage = await api("/api/settings/limits", {
          method: "PUT",
          body: {
            scoring_cap: Number($("scoring-cap").value || 150),
            monthly_token_limit: value("token-limit"),
            monthly_cost_limit: value("cost-limit"),
          },
        });
        renderUsage();
        setStatus($("limits-status"), "ok", "Saved.");
      } catch (error) {
        setStatus($("limits-status"), "problem", error.message);
      }
    }),
  );

  $("add-price").addEventListener("click", () => $("price-rows").append(priceRow()));

  $("save-prices").addEventListener("click", (event) =>
    busy(event.target, async () => {
      try {
        state.usage = await api("/api/settings/prices", {
          method: "PUT",
          body: { prices: readPrices() },
        });
        renderUsage();
        setStatus($("prices-status"), "ok", "Saved.");
      } catch (error) {
        setStatus($("prices-status"), "problem", error.message);
      }
    }),
  );
}

function setUpSettingsActions() {
  setUpUsageActions();
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
  setUpSearchActions();
  showView();
  try {
    const about = await api("/api/about");
    $("about-version").textContent = `Jobcu ${about.version}`;
    $("about-copyright").textContent = about.copyright;
    $("footer-copyright").textContent = about.copyright;
    $("about-data-folder").textContent = about.data_folder;
    await Promise.all([loadSettings(), loadDocuments(), loadSearchForm(), loadUsage()]);
  } catch {
    // The engine problem message is already visible.
  }
}

start();
