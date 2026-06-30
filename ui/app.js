const state = {
  scenarios: [],
  runHistory: [],
  latest: null,
  readiness: null,
  approvals: null,
  audit: null,
  selectedRunId: null,
  selectedScenarioId: null,
  selectedArtifactId: null,
  selectedArtifact: null,
  selectedEvidenceRef: null,
  selectedEvidence: null,
  selectedAuditEventId: null,
  submittingApproval: false,
  launchScenarioIds: [],
  runningWorkflow: false,
  launchMessage: "Ready",
};

const gateLabels = {
  can_generate_final_plan: "Final Plan",
  can_accept_validation: "Accept Validation",
  can_recommend_cutover: "Cutover",
  can_recommend_rollback: "Rollback",
  can_mark_ready: "Ready",
};

const approvalGateByType = {
  cutover_recommendation: "can_recommend_cutover",
  final_planning: "can_generate_final_plan",
  ready: "can_mark_ready",
  rollback_recommendation: "can_recommend_rollback",
  validation_acceptance: "can_accept_validation",
};

const approvalLabels = {
  cutover_recommendation: "Cutover Recommendation",
  final_planning: "Final Planning",
  ready: "Ready",
  rollback_recommendation: "Rollback Recommendation",
  validation_acceptance: "Validation Acceptance",
};

const scenarioLabels = {
  clean_migration: "Clean Migration",
  failed_checksum: "Failed Checksum",
  schema_drift: "Schema Drift",
  schema_relaxed_unique_violation: "Relaxed Unique Violation",
};

const workflowStepLabels = {
  run_deterministic_evals: "Run Deterministic Evaluations",
  generate_runbook_drafts: "Generate Runbook Drafts",
  validate_artifact_bundle: "Validate Artifact Bundle",
  write_artifact_bundle: "Write Artifact Bundle",
};

const stageLabels = {
  not_started: "Not Started",
  evaluation: "Evaluation",
  runbook: "Runbook",
  artifact_validation: "Artifact Validation",
  artifacts_written: "Artifacts Written",
};

const artifactTypeLabels = {
  eval_report: "Evaluation Report",
  evidence_registry: "Evidence Registry",
  runbook: "Runbook",
  runbook_draft: "Runbook Draft",
};

const detailFieldLabels = {
  actor: "Actor",
  artifact_ids: "Artifact IDs",
  content_hash: "Content Hash",
  decision: "Decision",
  error: "Error",
  event_id: "Event ID",
  evidence_ref: "Evidence Reference",
  evidence_refs: "Evidence References",
  finding_keys: "Finding Keys",
  model_calls: "Model Calls",
  producer: "Producer",
  scenario: "Scenario",
  source_artifact_id: "Source Artifact",
  source_artifact_path: "Source Path",
  source_type: "Source Type",
  stage: "Stage",
  status: "Status",
};

const els = {
  apiStatus: document.querySelector("#api-status"),
  runSelect: document.querySelector("#run-select"),
  launchForm: document.querySelector("#launch-form"),
  launchScenarioList: document.querySelector("#launch-scenario-list"),
  launchSubmitButton: document.querySelector("#launch-submit-button"),
  launchStatus: document.querySelector("#launch-status"),
  scenarioList: document.querySelector("#scenario-list"),
  runTitle: document.querySelector("#run-title"),
  refreshButton: document.querySelector("#refresh-button"),
  notice: document.querySelector("#notice"),
  metricWorkflow: document.querySelector("#metric-workflow"),
  metricScenarios: document.querySelector("#metric-scenarios"),
  metricApprovals: document.querySelector("#metric-approvals"),
  metricAudit: document.querySelector("#metric-audit"),
  resultStatus: document.querySelector("#result-status"),
  resultSummaryList: document.querySelector("#result-summary-list"),
  progressCount: document.querySelector("#progress-count"),
  workflowStepList: document.querySelector("#workflow-step-list"),
  transitionCount: document.querySelector("#transition-count"),
  transitionList: document.querySelector("#transition-list"),
  selectedScenarioLabel: document.querySelector("#selected-scenario-label"),
  gateGrid: document.querySelector("#gate-grid"),
  findingCount: document.querySelector("#finding-count"),
  findingList: document.querySelector("#finding-list"),
  approvalCount: document.querySelector("#approval-count"),
  approvalState: document.querySelector("#approval-state"),
  artifactCount: document.querySelector("#artifact-count"),
  artifactList: document.querySelector("#artifact-list"),
  auditCount: document.querySelector("#audit-count"),
  auditList: document.querySelector("#audit-list"),
  runbookStatus: document.querySelector("#runbook-status"),
  runbookTitle: document.querySelector("#runbook-title"),
  runbookSections: document.querySelector("#runbook-sections"),
  runbookEvidenceList: document.querySelector("#runbook-evidence-list"),
  evidenceStage: document.querySelector("#evidence-stage"),
  evidenceDetail: document.querySelector("#evidence-detail"),
  auditDetailStatus: document.querySelector("#audit-detail-status"),
  auditDetail: document.querySelector("#audit-detail"),
  approvalForm: document.querySelector("#approval-form"),
  approvalTypeSelect: document.querySelector("#approval-type-select"),
  approvalEvidenceSelect: document.querySelector("#approval-evidence-select"),
  approvalActorInput: document.querySelector("#approval-actor-input"),
  approvalNotesInput: document.querySelector("#approval-notes-input"),
  approvalSubmitButton: document.querySelector("#approval-submit-button"),
  approvalActionStatus: document.querySelector("#approval-action-status"),
};

els.refreshButton.addEventListener("click", () => {
  loadDashboard();
});

els.runSelect.addEventListener("change", () => {
  state.selectedRunId = els.runSelect.value || null;
  resetSelections({ keepRun: true });
  loadDashboard();
});

els.approvalForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitApproval();
});

els.launchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runWorkflowFromLaunchControls();
});

loadDashboard();

async function loadDashboard() {
  setNotice("", true);
  setLoading();
  try {
    const [health, scenarios, runs] = await Promise.all([
      getJson("/health"),
      getJson("/scenarios"),
      getJson("/workflows"),
    ]);
    els.apiStatus.textContent = `${health.status} / v${health.version}`;
    state.scenarios = scenarios.scenarios || [];
    ensureLaunchSelection();
    state.runHistory = runs.runs || [];
    state.selectedRunId = selectedRunId(runs);

    if (!state.selectedRunId) {
      state.latest = null;
      state.readiness = null;
      state.approvals = null;
      state.audit = null;
      resetSelections({ keepRun: true });
      render();
      setNotice("No persisted workflow run is available.", false);
      return;
    }

    const runManifest = state.runHistory.find(
      (run) => run.workflow_run_id === state.selectedRunId,
    ) || {};
    const workflow = await getJson(`/workflows/${encodeURIComponent(state.selectedRunId)}`);
    state.latest = {
      run_manifest: runManifest,
      workflow_run: workflow.workflow_run,
    };

    const runId = state.selectedRunId;
    const [readiness, approvals, audit] = await Promise.all([
      getJson(`/workflows/${encodeURIComponent(runId)}/readiness`),
      getJson(`/workflows/${encodeURIComponent(runId)}/approvals`),
      getJson(`/workflows/${encodeURIComponent(runId)}/audit`),
    ]);
    state.readiness = readiness;
    state.approvals = approvals;
    state.audit = audit;
    const scenarioIds = readiness.scenarios.map((scenario) => scenario.scenario_id);
    if (!state.selectedScenarioId || !scenarioIds.includes(state.selectedScenarioId)) {
      state.selectedScenarioId = readiness.scenarios[0].scenario_id;
    }
    ensureSelections();
    render();
    await hydrateDetails();
    render();
  } catch (error) {
    setNotice(error.message, false);
    render();
  }
}

function selectedRunId(runs) {
  const runIds = (runs.runs || []).map((run) => run.workflow_run_id).filter(Boolean);
  if (state.selectedRunId && runIds.includes(state.selectedRunId)) {
    return state.selectedRunId;
  }
  if (runs.latest_workflow_run_id && runIds.includes(runs.latest_workflow_run_id)) {
    return runs.latest_workflow_run_id;
  }
  return runIds[0] || null;
}

async function getJson(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (!response.ok) {
    const message = payload.error?.message || `Request failed: ${path}`;
    throw new Error(message);
  }
  return payload;
}

async function getOptionalJson(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const message = payload.error?.message || `Request failed: ${path}`;
    throw new Error(message);
  }
  return payload;
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    const message = body.error?.message || `Request failed: ${path}`;
    throw new Error(message);
  }
  return body;
}

function setLoading() {
  els.metricWorkflow.textContent = "-";
  els.metricScenarios.textContent = "-";
  els.metricApprovals.textContent = "-";
  els.metricAudit.textContent = "-";
}

function render() {
  const run = state.latest?.workflow_run;
  const manifest = currentArtifactManifest();
  const readiness = state.readiness;
  const selected = selectedScenario();

  els.runTitle.textContent = run ? shortRunId(run.workflow_run_id) : "Latest Run";
  els.metricWorkflow.textContent = run ? titleCase(run.status) : "-";
  els.metricScenarios.textContent = readiness ? String(readiness.scenario_count) : String(state.scenarios.length || "-");
  els.metricApprovals.textContent = state.approvals ? String(state.approvals.approval_count) : "-";
  els.metricAudit.textContent = state.audit ? String(state.audit.event_count) : "-";
  els.selectedScenarioLabel.textContent = selected ? scenarioLabel(selected.scenario_id) : "-";
  els.artifactCount.textContent = manifest ? String(manifest.artifact_count || 0) : "-";
  els.auditCount.textContent = state.audit ? `${state.audit.event_count} events` : "-";
  els.approvalCount.textContent = state.approvals ? `${state.approvals.approval_count} recorded` : "-";

  renderRuns();
  renderLaunchControls();
  renderRunResult();
  renderWorkflowProgress();
  renderStageTransitions();
  renderScenarios();
  renderGates(selected);
  renderFindings(selected);
  renderApprovals();
  renderApprovalAction();
  renderArtifacts(manifest);
  renderAudit();
  renderArtifactDetail();
  renderEvidenceDetail();
  renderAuditDetail();
}

function ensureLaunchSelection() {
  const knownScenarioIds = state.scenarios.map((scenario) => scenario.scenario_id);
  state.launchScenarioIds = state.launchScenarioIds.filter((scenarioId) =>
    knownScenarioIds.includes(scenarioId),
  );
  if (!state.launchScenarioIds.length && knownScenarioIds.length) {
    state.launchScenarioIds = [knownScenarioIds[0]];
  }
}

function currentRunId() {
  return state.selectedRunId || state.latest?.workflow_run?.workflow_run_id || null;
}

function resetSelections({keepRun = false} = {}) {
  if (!keepRun) {
    state.selectedRunId = null;
  }
  state.selectedScenarioId = null;
  state.selectedArtifactId = null;
  state.selectedArtifact = null;
  state.selectedEvidenceRef = null;
  state.selectedEvidence = null;
  state.selectedAuditEventId = null;
}

function currentArtifactManifest() {
  return state.latest?.workflow_run?.artifact_manifest || state.latest?.run_manifest || null;
}

function ensureSelections() {
  const manifest = currentArtifactManifest();
  const artifacts = manifest?.artifacts || [];
  const selected = selectedScenario();
  const artifactIds = artifacts.map((artifact) => artifact.artifact_id).filter(Boolean);
  const preferredRunbookId = selected
    ? `artifact.runbook_draft.${selected.scenario_id}.v1`
    : null;

  if (!state.selectedArtifactId || !artifactIds.includes(state.selectedArtifactId)) {
    state.selectedArtifactId =
      artifactIds.find((artifactId) => artifactId === preferredRunbookId) ||
      artifactIds.find((artifactId) => artifactId.includes(".runbook_draft.")) ||
      artifactIds[0] ||
      null;
    state.selectedArtifact = null;
    state.selectedEvidenceRef = null;
    state.selectedEvidence = null;
  }

  const events = state.audit?.events || [];
  const eventIds = events.map((event) => event.audit_event_id).filter(Boolean);
  if (!state.selectedAuditEventId || !eventIds.includes(state.selectedAuditEventId)) {
    const latestEvent = events[events.length - 1];
    state.selectedAuditEventId = latestEvent?.audit_event_id || null;
  }
}

async function hydrateDetails() {
  if (!state.selectedArtifactId) {
    state.selectedArtifact = null;
    state.selectedEvidenceRef = null;
    state.selectedEvidence = null;
    return;
  }

  state.selectedArtifact = await getJson(
    artifactUrl(state.selectedArtifactId),
  );
  const refs = artifactEvidenceRefs(state.selectedArtifact);
  if (!state.selectedEvidenceRef || !refs.includes(state.selectedEvidenceRef)) {
    state.selectedEvidenceRef = refs[0] || null;
    state.selectedEvidence = null;
  }
  if (!state.selectedEvidenceRef) {
    state.selectedEvidence = null;
    return;
  }
  await hydrateEvidence(state.selectedEvidenceRef);
}

async function hydrateEvidence(evidenceRef) {
  try {
    state.selectedEvidence = await getJson(evidenceUrl(evidenceRef));
  } catch (error) {
    state.selectedEvidence = {
      evidence_ref: evidenceRef,
      error: error.message,
    };
  }
}

function artifactUrl(artifactId) {
  const runId = currentRunId();
  const encodedArtifactId = encodeURIComponent(artifactId);
  if (!runId) {
    return `/artifacts/${encodedArtifactId}`;
  }
  return `/workflows/${encodeURIComponent(runId)}/artifacts/${encodedArtifactId}`;
}

function evidenceUrl(evidenceRef) {
  const runId = currentRunId();
  const encodedEvidenceRef = encodeURIComponent(evidenceRef);
  if (!runId) {
    return `/evidence/${encodedEvidenceRef}`;
  }
  return `/workflows/${encodeURIComponent(runId)}/evidence/${encodedEvidenceRef}`;
}

function selectedScenario() {
  const scenarios = state.readiness?.scenarios || [];
  if (!scenarios.length) {
    return null;
  }
  return (
    scenarios.find((scenario) => scenario.scenario_id === state.selectedScenarioId) ||
    scenarios[0]
  );
}

function renderRuns() {
  const runs = state.runHistory || [];
  if (!runs.length) {
    els.runSelect.innerHTML = '<option value="">No persisted runs</option>';
    els.runSelect.disabled = true;
    return;
  }

  els.runSelect.disabled = false;
  els.runSelect.innerHTML = runs
    .map((run) => {
      const runId = run.workflow_run_id;
      const label = `${shortRunId(runId)}${run.is_latest ? " (latest)" : ""}`;
      return `<option value="${escapeAttr(runId)}">${escapeHtml(label)}</option>`;
    })
    .join("");
  els.runSelect.value = state.selectedRunId || "";
}

function renderLaunchControls() {
  const scenarios = state.scenarios || [];
  if (!scenarios.length) {
    els.launchScenarioList.innerHTML = emptyMarkup("No scenarios");
    els.launchSubmitButton.disabled = true;
    els.launchStatus.textContent = "No scenarios available";
    return;
  }

  els.launchScenarioList.innerHTML = scenarios
    .map((scenario) => {
      const scenarioId = scenario.scenario_id;
      const checked = state.launchScenarioIds.includes(scenarioId) ? "checked" : "";
      return `
        <label class="launch-option">
          <input type="checkbox" value="${escapeAttr(scenarioId)}" ${checked}>
          <span>${escapeHtml(scenarioLabel(scenarioId))}</span>
        </label>
      `;
    })
    .join("");

  els.launchScenarioList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      state.launchScenarioIds = Array.from(
        els.launchScenarioList.querySelectorAll("input[type='checkbox']:checked"),
      ).map((input) => input.value);
      state.launchMessage = null;
      renderLaunchControls();
    });
  });

  const canRun = state.launchScenarioIds.length > 0 && !state.runningWorkflow;
  els.launchSubmitButton.disabled = !canRun;
  els.launchSubmitButton.textContent = state.runningWorkflow ? "Running" : "Run Workflow";
  els.launchStatus.textContent = state.runningWorkflow
    ? "Running workflow"
    : state.launchMessage || `${state.launchScenarioIds.length} selected`;
}

function renderRunResult() {
  const run = state.latest?.workflow_run;
  const manifest = currentArtifactManifest();
  const readinessScenarios = state.readiness?.scenarios || [];
  if (!run) {
    els.resultStatus.textContent = "-";
    els.resultSummaryList.innerHTML = emptyMarkup("No run selected");
    return;
  }

  const blockedGates = readinessScenarios.flatMap((scenario) => scenario.blocked_gates || []);
  const blockingFindings = readinessScenarios
    .flatMap((scenario) =>
      Object.values(scenario.gate_results || {}).flatMap((gate) => gate.blocking_findings || []),
    )
    .filter(unique);
  const scenarioText = (run.scenario_ids || []).map(scenarioLabel).join(", ");
  els.resultStatus.textContent = titleCase(run.status);
  els.resultSummaryList.innerHTML = [
    summaryRow("Scenarios", scenarioText || "-"),
    summaryRow("Current Stage", stageLabel(run.current_stage)),
    summaryRow("Blocked Gates", String(blockedGates.length)),
    summaryRow("Blocking Findings", String(blockingFindings.length)),
    summaryRow("Artifact Bundle", manifest?.passed ? `${manifest.artifact_count || 0} accepted` : "not accepted"),
  ].join("");
}

function renderWorkflowProgress() {
  const steps = state.latest?.workflow_run?.steps || [];
  if (!steps.length) {
    els.progressCount.textContent = "-";
    els.workflowStepList.innerHTML = emptyMarkup("No workflow steps");
    return;
  }

  const completed = steps.filter((step) => step.status === "completed").length;
  els.progressCount.textContent = `${completed}/${steps.length} completed`;
  els.workflowStepList.innerHTML = steps
    .map((step) => progressItem(stepLabel(step.step), step.status, step.model_calls ? `Model Calls: ${titleCase(step.model_calls)}` : ""))
    .join("");
}

function renderStageTransitions() {
  const transitions = state.latest?.workflow_run?.stage_transitions || [];
  if (!transitions.length) {
    els.transitionCount.textContent = "-";
    els.transitionList.innerHTML = emptyMarkup("No stage transitions");
    return;
  }

  const allowed = transitions.filter((transition) => transition.allowed).length;
  els.transitionCount.textContent = `${allowed}/${transitions.length} allowed`;
  els.transitionList.innerHTML = transitions
    .map((transition) => {
      const title = `${stageLabel(transition.from_stage)} -> ${stageLabel(transition.to_stage)}`;
      const detailParts = [
        ...(transition.unmet_prerequisites || []).map(stageLabel),
        ...(transition.blocking_findings || []).map(findingLabel),
      ];
      const detail = detailParts.length ? detailParts.join(", ") : "Transition prerequisites passed.";
      return progressItem(title, transition.allowed ? "allowed" : "blocked", detail);
    })
    .join("");
}

async function runWorkflowFromLaunchControls() {
  if (!state.launchScenarioIds.length || state.runningWorkflow) {
    return;
  }

  const previousRunId = state.selectedRunId;
  state.runningWorkflow = true;
  state.launchMessage = "Running workflow";
  setNotice("", true);
  renderLaunchControls();
  try {
    const query = state.launchScenarioIds
      .map((scenarioId) => `scenario_id=${encodeURIComponent(scenarioId)}`)
      .join("&");
    const workflowRun = await postJson(`/workflows/run?${query}`);
    state.selectedRunId = workflowRun.workflow_run_id;
    resetSelections({keepRun: true});
    state.runningWorkflow = false;
    state.launchMessage = `Completed ${shortRunId(workflowRun.workflow_run_id)}`;
    await loadDashboard();
  } catch (error) {
    state.selectedRunId = previousRunId;
    state.runningWorkflow = false;
    state.launchMessage = "Workflow failed";
    setNotice(error.message, false);
    render();
  }
}

function renderScenarios() {
  const readinessScenarios = state.readiness?.scenarios || [];
  if (!readinessScenarios.length) {
    els.scenarioList.innerHTML = emptyMarkup("No runs");
    return;
  }

  els.scenarioList.innerHTML = readinessScenarios
    .map((scenario) => {
      const blocked = scenario.blocked_gates.length > 0;
      const selected = scenario.scenario_id === selectedScenario()?.scenario_id;
      return `
        <button class="scenario-button ${selected ? "is-selected" : ""}" type="button" data-scenario-id="${escapeAttr(scenario.scenario_id)}">
          <span class="scenario-dot ${blocked ? "blocked" : "ok"}"></span>
          <span>
            <span class="scenario-name">${escapeHtml(scenarioLabel(scenario.scenario_id))}</span>
            <span class="scenario-subtitle">${blocked ? `${scenario.blocked_gates.length} blocked` : "Clear"}</span>
          </span>
        </button>
      `;
    })
    .join("");

  els.scenarioList.querySelectorAll("[data-scenario-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedScenarioId = button.dataset.scenarioId;
      state.selectedArtifactId = null;
      state.selectedArtifact = null;
      state.selectedEvidenceRef = null;
      state.selectedEvidence = null;
      ensureSelections();
      render();
      reloadDetails();
    });
  });
}

function renderGates(scenario) {
  if (!scenario) {
    els.gateGrid.innerHTML = emptyMarkup("No readiness data");
    return;
  }

  els.gateGrid.innerHTML = Object.entries(scenario.gate_results)
    .map(([gate, result]) => {
      const statusClass = result.allowed ? "ok" : "blocked";
      const detail = gateDetail(result);
      return `
        <article class="gate-card ${statusClass}">
          <div class="gate-title">
            <span>${escapeHtml(gateLabels[gate] || gate)}</span>
            <span class="pill ${statusClass}">${result.allowed ? "Allowed" : "Blocked"}</span>
          </div>
          <div class="gate-detail">${escapeHtml(detail)}</div>
        </article>
      `;
    })
    .join("");
}

function renderFindings(scenario) {
  if (!scenario) {
    els.findingCount.textContent = "-";
    els.findingList.innerHTML = emptyMarkup("No findings");
    return;
  }

  const findings = Object.values(scenario.gate_results)
    .flatMap((gate) => gate.blocking_findings || [])
    .filter(unique);
  els.findingCount.textContent = `${findings.length} blocking`;
  if (!findings.length) {
    els.findingList.innerHTML = emptyMarkup("No blocking findings");
    return;
  }

  els.findingList.innerHTML = findings
    .map((findingKey) => `
      <article class="finding">
        <div class="finding-header">
          <span class="finding-key">${escapeHtml(findingLabel(findingKey))}</span>
          <span class="pill blocked">Blocking</span>
        </div>
        <div class="finding-meta">Finding key: ${escapeHtml(findingKey)}</div>
      </article>
    `)
    .join("");
}

function renderApprovals() {
  const approvals = state.approvals;
  if (!approvals) {
    els.approvalState.innerHTML = emptyMarkup("No approvals");
    return;
  }

  const effective = approvals.effective_approvals || [];
  const pending = approvals.pending_approvals || [];
  const chips = [
    ...effective.map((approval) => chipMarkup(approvalLabel(approval), "ok")),
    ...pending.map((approval) => chipMarkup(approvalLabel(approval), "warn")),
  ];
  els.approvalState.innerHTML = chips.length ? chips.join("") : emptyMarkup("No approval requirements");
}

function renderApprovalAction() {
  const pending = state.approvals?.pending_approvals || [];
  const evidenceRefs = approvalEvidenceRefs();
  const disabled = !currentRunId() || !pending.length || !evidenceRefs.length || state.submittingApproval;

  els.approvalTypeSelect.innerHTML = pending.length
    ? pending
        .map((approval) => `
          <option value="${escapeAttr(approval)}">${escapeHtml(approvalLabel(approval))}</option>
        `)
        .join("")
    : '<option value="">No pending approvals</option>';

  els.approvalEvidenceSelect.innerHTML = evidenceRefs.length
    ? evidenceRefs
        .map((ref) => `<option value="${escapeAttr(ref)}">${escapeHtml(evidenceLabel(ref))}</option>`)
        .join("")
    : '<option value="">No evidence available</option>';

  els.approvalTypeSelect.disabled = disabled;
  els.approvalEvidenceSelect.disabled = disabled;
  els.approvalActorInput.disabled = disabled;
  els.approvalNotesInput.disabled = disabled;
  els.approvalSubmitButton.disabled = disabled;
  els.approvalSubmitButton.textContent = state.submittingApproval ? "Recording" : "Approve";
  els.approvalActionStatus.textContent = pending.length ? `${pending.length} pending` : "Clear";
}

async function submitApproval() {
  const approvalType = els.approvalTypeSelect.value;
  const evidenceRef = els.approvalEvidenceSelect.value;
  const runId = currentRunId();
  const selected = selectedScenario();
  const gate = approvalGateByType[approvalType];
  if (!runId || !selected || !gate || !evidenceRef) {
    setNotice("Approval cannot be submitted without a selected run, gate, scenario, and evidence reference.", false);
    return;
  }

  state.submittingApproval = true;
  renderApprovalAction();
  try {
    await postJson(`/workflows/${encodeURIComponent(runId)}/approvals`, {
      scenario_id: selected.scenario_id,
      gate,
      actor: els.approvalActorInput.value || "human.reviewer",
      decision: "approved",
      evidence_refs: [evidenceRef],
      notes: els.approvalNotesInput.value,
    });
    state.submittingApproval = false;
    els.approvalActionStatus.textContent = "recorded";
    await loadDashboard();
  } catch (error) {
    state.submittingApproval = false;
    setNotice(error.message, false);
    render();
  }
}

function renderArtifacts(manifest) {
  if (!manifest || !manifest.artifacts?.length) {
    els.artifactList.innerHTML = emptyMarkup("No artifacts");
    return;
  }

  els.artifactList.innerHTML = manifest.artifacts
    .slice(0, 6)
    .map((artifact) => `
      <button class="artifact ${artifact.artifact_id === state.selectedArtifactId ? "is-selected" : ""}" type="button" data-artifact-id="${escapeAttr(artifact.artifact_id)}">
        <div class="artifact-header">
          <span class="artifact-id">${escapeHtml(artifactLabel(artifact.artifact_id))}</span>
        </div>
        <div class="artifact-meta">${escapeHtml(shortHash(artifact.content_hash))}</div>
      </button>
    `)
    .join("");

  els.artifactList.querySelectorAll("[data-artifact-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedArtifactId = button.dataset.artifactId;
      state.selectedArtifact = null;
      state.selectedEvidenceRef = null;
      state.selectedEvidence = null;
      render();
      reloadDetails();
    });
  });
}

function renderAudit() {
  const events = state.audit?.events || [];
  if (!events.length) {
    els.auditList.innerHTML = emptyMarkup("No audit events");
    return;
  }

  els.auditList.innerHTML = events
    .slice(-6)
    .reverse()
    .map((event) => `
      <button class="audit-item ${event.audit_event_id === state.selectedAuditEventId ? "is-selected" : ""}" type="button" data-audit-event-id="${escapeAttr(event.audit_event_id)}">
        <div class="audit-header">
          <span class="audit-decision">${escapeHtml(titleCase(event.decision))}</span>
          <span class="pill ${event.status === "blocked" ? "blocked" : "ok"}">${escapeHtml(titleCase(event.status))}</span>
        </div>
        <div class="audit-meta">${escapeHtml(stageLabel(event.stage))} / ${escapeHtml(actorLabel(event.actor_name))}</div>
      </button>
    `)
    .join("");

  els.auditList.querySelectorAll("[data-audit-event-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedAuditEventId = button.dataset.auditEventId;
      render();
    });
  });
}

function renderArtifactDetail() {
  const artifact = state.selectedArtifact;
  const artifactId = state.selectedArtifactId;
  if (!artifactId) {
    els.runbookStatus.textContent = "-";
    els.runbookTitle.textContent = "No artifact selected";
    els.runbookSections.innerHTML = "";
    els.runbookEvidenceList.innerHTML = emptyMarkup("No evidence refs");
    return;
  }
  if (!artifact) {
    els.runbookStatus.textContent = "Loading";
    els.runbookTitle.textContent = artifactId;
    els.runbookSections.innerHTML = "";
    els.runbookEvidenceList.innerHTML = emptyMarkup("Loading artifact");
    return;
  }

  const content = artifact.content || {};
  const metadata = content.metadata || artifact.metadata || {};
  const artifactType = metadata.artifact_type || "artifact";
  els.runbookStatus.textContent = `${artifactTypeLabel(artifactType)} / ${titleCase(metadata.status || "-")}`;
  els.runbookTitle.textContent = humanizeEmbeddedIds(content.title || artifactLabel(metadata.artifact_id || artifactId));

  if (artifactType === "runbook") {
    renderRunbookSections(content.sections || []);
  } else {
    els.runbookSections.innerHTML = kvMarkup({
      producer: metadata.producer,
      scenario: metadata.scenario_id,
      model_calls: metadata.model_calls,
      content_hash: artifact.content_hash || metadata.content_hash,
    });
  }

  const refs = artifactEvidenceRefs(artifact);
  els.runbookEvidenceList.innerHTML = refs.length
    ? refs
        .map((ref) => `
          <button class="evidence-button ${ref === state.selectedEvidenceRef ? "is-selected" : ""}" type="button" data-evidence-ref="${escapeAttr(ref)}">
            ${escapeHtml(evidenceLabel(ref))}
          </button>
        `)
        .join("")
    : emptyMarkup("No evidence refs");

  els.runbookEvidenceList.querySelectorAll("[data-evidence-ref]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedEvidenceRef = button.dataset.evidenceRef;
      state.selectedEvidence = null;
      render();
      reloadEvidence();
    });
  });
}

function renderRunbookSections(sections) {
  if (!sections.length) {
    els.runbookSections.innerHTML = emptyMarkup("No runbook sections");
    return;
  }

  els.runbookSections.innerHTML = sections
    .map((section) => `
      <article class="detail-section">
        <h4>${escapeHtml(humanizeEmbeddedIds(section.title || titleCase(section.section_id)))}</h4>
        <p>${escapeHtml(humanizeEmbeddedIds(section.body_markdown || ""))}</p>
      </article>
    `)
    .join("");
}

function renderEvidenceDetail() {
  const evidence = state.selectedEvidence;
  const evidenceRef = state.selectedEvidenceRef;
  if (!evidenceRef) {
    els.evidenceStage.textContent = "-";
    els.evidenceDetail.innerHTML = emptyMarkup("No evidence selected");
    return;
  }
  if (!evidence) {
    els.evidenceStage.textContent = "Loading";
    els.evidenceDetail.innerHTML = emptyMarkup("Loading evidence");
    return;
  }
  if (evidence.error) {
    els.evidenceStage.textContent = "Unresolved";
    els.evidenceDetail.innerHTML = kvMarkup({
      evidence_ref: evidence.evidence_ref,
      error: evidence.error,
    });
    return;
  }

  const entry = evidence.entry || {};
  els.evidenceStage.textContent = stageLabel(entry.stage);
  els.evidenceDetail.innerHTML = kvMarkup({
    evidence_ref: evidence.evidence_ref,
    source_type: entry.source_type,
    producer: entry.producer,
    source_artifact_id: entry.source_artifact_id,
    source_artifact_path: entry.source_artifact_path,
    content_hash: entry.content_hash,
  });
}

function renderAuditDetail() {
  const event = selectedAuditEvent();
  if (!event) {
    els.auditDetailStatus.textContent = "-";
    els.auditDetail.innerHTML = emptyMarkup("No audit event selected");
    return;
  }

  els.auditDetailStatus.textContent = titleCase(event.status || "-");
  els.auditDetail.innerHTML = kvMarkup({
    event_id: event.audit_event_id,
    decision: event.decision,
    stage: event.stage,
    actor: event.actor_name,
    evidence_refs: (event.evidence_refs || []).join(", "),
    finding_keys: (event.finding_keys || []).join(", "),
    artifact_ids: (event.artifact_ids || []).join(", "),
  });
}

function selectedAuditEvent() {
  const events = state.audit?.events || [];
  return events.find((event) => event.audit_event_id === state.selectedAuditEventId) || null;
}

function reloadDetails() {
  hydrateDetails()
    .then(() => render())
    .catch((error) => {
      setNotice(error.message, false);
      render();
    });
}

function reloadEvidence() {
  if (!state.selectedEvidenceRef) {
    render();
    return;
  }
  hydrateEvidence(state.selectedEvidenceRef)
    .then(() => render())
    .catch((error) => {
      setNotice(error.message, false);
      render();
    });
}

function summaryRow(label, value) {
  return `
    <article class="summary-row">
      <div class="summary-label">${escapeHtml(label)}</div>
      <div class="summary-meta">${escapeHtml(value)}</div>
    </article>
  `;
}

function progressItem(title, status, detail) {
  const statusText = titleCase(status || "-");
  const statusClass = statusClassFor(status);
  return `
    <article class="progress-item ${statusClass}">
      <div class="progress-heading">
        <span class="progress-title">${escapeHtml(title || "-")}</span>
        <span class="pill ${statusClass}">${escapeHtml(statusText)}</span>
      </div>
      <div class="progress-meta">${escapeHtml(detail || "")}</div>
    </article>
  `;
}

function statusClassFor(status) {
  if (status === "completed" || status === "allowed") {
    return "ok";
  }
  if (status === "failed" || status === "blocked") {
    return "blocked";
  }
  return "warn";
}

function gateDetail(result) {
  const parts = [];
  if (result.blocking_findings?.length) {
    parts.push(`${result.blocking_findings.length} blocking finding${plural(result.blocking_findings.length)}`);
  }
  if (result.missing_approvals?.length) {
    parts.push(`${result.missing_approvals.length} missing approval${plural(result.missing_approvals.length)}`);
  }
  if (result.unmet_prerequisites?.length) {
    parts.push(`${result.unmet_prerequisites.length} unmet prerequisite${plural(result.unmet_prerequisites.length)}`);
  }
  if (result.unresolved_evidence_refs?.length) {
    parts.push(`${result.unresolved_evidence_refs.length} unresolved evidence ref${plural(result.unresolved_evidence_refs.length)}`);
  }
  return parts.length ? parts.join(" / ") : "All deterministic checks passed.";
}

function chipMarkup(label, status) {
  return `<span class="chip ${status}">${escapeHtml(label)}</span>`;
}

function artifactEvidenceRefs(artifact) {
  const content = artifact?.content || {};
  const refs = [];
  refs.push(...(content.metadata?.evidence_refs || []));
  for (const section of content.sections || []) {
    refs.push(...(section.evidence_refs || []));
  }
  for (const claim of content.claims || []) {
    refs.push(...(claim.evidence_refs || []));
  }
  return refs.filter(Boolean).filter(unique);
}

function approvalEvidenceRefs() {
  const manifest = currentArtifactManifest();
  const refs = [];
  const artifactIds = (manifest?.artifacts || [])
    .map((artifact) => artifact.artifact_id)
    .filter(Boolean);
  refs.push(...artifactIds.filter((artifactId) => artifactId.includes(".eval_report.")));
  if (state.selectedEvidenceRef) {
    refs.push(state.selectedEvidenceRef);
  }
  refs.push(...artifactEvidenceRefs(state.selectedArtifact));
  refs.push(...artifactIds);
  return refs.filter(Boolean).filter(unique);
}

function kvMarkup(rows) {
  const entries = Object.entries(rows).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!entries.length) {
    return emptyMarkup("No detail");
  }
  return `
    <div class="kv-list">
      ${entries
        .map(([key, value]) => `
          <div class="kv-row">
            <span class="kv-key">${escapeHtml(detailFieldLabel(key))}</span>
            <span class="kv-value">${escapeHtml(detailValueLabel(key, value))}</span>
          </div>
        `)
        .join("")}
    </div>
  `;
}

function emptyMarkup(text) {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function setNotice(message, hidden) {
  els.notice.hidden = hidden;
  els.notice.textContent = message;
}

function unique(value, index, list) {
  return list.indexOf(value) === index;
}

function scenarioLabel(value) {
  return value ? scenarioLabels[value] || titleCase(value) : "-";
}

function approvalLabel(value) {
  return value ? approvalLabels[value] || titleCase(value) : "-";
}

function stepLabel(value) {
  return value ? workflowStepLabels[value] || titleCase(value) : "-";
}

function stageLabel(value) {
  return value ? stageLabels[value] || titleCase(value) : "-";
}

function artifactTypeLabel(value) {
  return value ? artifactTypeLabels[value] || titleCase(value) : "-";
}

function artifactLabel(value) {
  if (!value) {
    return "-";
  }

  const normalized = String(value).replace(/^artifact\./, "").replace(/\.v\d+$/, "");
  const [artifactType, scope] = normalized.split(".");
  const typeLabel = artifactTypeLabel(artifactType);
  if (scope && scenarioLabels[scope]) {
    return `${typeLabel} - ${scenarioLabel(scope)}`;
  }
  if (scope && scope !== "fixture_suite") {
    return `${typeLabel} - ${titleCase(scope)}`;
  }
  return typeLabel;
}

function evidenceLabel(value) {
  if (!value) {
    return "-";
  }

  const ref = String(value);
  if (ref.startsWith("artifact.")) {
    return artifactLabel(ref);
  }

  const normalized = ref.replace(/\.v\d+$/, "");
  const parts = normalized.split(".");
  if (parts[0] === "gate") {
    const gate = parts[1] || "";
    const scenario = parts[2] || "";
    const gateLabel = gateLabels[gate] || titleCase(gate);
    return scenario ? `${gateLabel} Gate - ${scenarioLabel(scenario)}` : `${gateLabel} Gate`;
  }
  if (parts[0] === "validation" && parts.length >= 4) {
    return `${titleCase(parts[1])} - ${parts.slice(2).join(".")}`;
  }
  if (parts[0] === "schema" && parts.length >= 4) {
    return `${titleCase(parts[1])} - ${parts.slice(2).join(".")}`;
  }
  return titleCase(ref);
}

function findingLabel(value) {
  if (!value) {
    return "-";
  }

  const [familyAndType, ...scopeParts] = String(value).split(":");
  const type = familyAndType.split(".").slice(1).join("_") || familyAndType;
  const scope = scopeParts.filter((part) => part && part !== "*");
  if (!scope.length) {
    return titleCase(type);
  }
  return `${titleCase(type)} - ${scope.map(scopeLabel).join(" / ")}`;
}

function scopeLabel(value) {
  if (!value) {
    return "-";
  }
  if (value.includes(".")) {
    return value;
  }
  return titleCase(value);
}

function actorLabel(value) {
  if (!value) {
    return "-";
  }
  return String(value)
    .split(".")
    .map((part) => titleCase(part))
    .join(" ");
}

function detailFieldLabel(key) {
  return detailFieldLabels[key] || titleCase(key);
}

function detailValueLabel(key, value) {
  if (Array.isArray(value)) {
    return value.map((item) => detailValueLabel(key, item)).join(", ");
  }

  const text = String(value ?? "");
  if (!text) {
    return "-";
  }

  if (key === "scenario") {
    return scenarioLabel(text);
  }
  if (key === "stage") {
    return stageLabel(text);
  }
  if (key === "decision" || key === "status" || key === "model_calls" || key === "source_type" || key === "producer") {
    return titleCase(text);
  }
  if (key === "actor") {
    return actorLabel(text);
  }
  if (key === "event_id") {
    return auditEventLabel(text);
  }
  if (key === "evidence_ref") {
    return evidenceLabel(text);
  }
  if (key === "source_artifact_id" || key === "artifact_ids") {
    return splitList(text).map(artifactLabel).join(", ");
  }
  if (key === "source_artifact_path") {
    return artifactPathLabel(text);
  }
  if (key === "evidence_refs") {
    return splitList(text).map(evidenceLabel).join(", ");
  }
  if (key === "finding_keys") {
    return splitList(text).map(findingLabel).join(", ");
  }
  return humanizeEmbeddedIds(text);
}

function splitList(value) {
  return String(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function humanizeEmbeddedIds(value) {
  let text = String(value ?? "");
  const replacements = {
    ...scenarioLabels,
    ...workflowStepLabels,
    ...stageLabels,
    ...approvalLabels,
    ...gateLabels,
  };

  for (const [id, label] of Object.entries(replacements).sort((a, b) => b[0].length - a[0].length)) {
    text = text.replace(new RegExp(escapeRegExp(id), "g"), label);
  }
  return text;
}

function artifactPathLabel(value) {
  if (!value) {
    return "-";
  }
  const fileName = String(value).split("/").pop() || String(value);
  const withoutExtension = fileName.replace(/\.[^.]+$/, "");
  return `${titleCase(withoutExtension)} File`;
}

function shortRunId(value) {
  if (!value) {
    return "Latest Run";
  }
  const match = String(value).match(/(\d{8})_(\d{6})$/);
  if (!match) {
    return humanizeEmbeddedIds(String(value).replace("workflow.fixture_validation.", "Run "));
  }
  const [, date, time] = match;
  return `Run ${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)} ${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`;
}

function shortHash(value) {
  return value ? value.replace("sha256:", "sha256:").slice(0, 19) : "no hash";
}

function titleCase(value) {
  return String(value || "-").replace(/[_.-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function auditEventLabel(value) {
  if (!value) {
    return "-";
  }
  const eventId = String(value);
  const parts = eventId.split(".");
  return humanizeEmbeddedIds(titleCase(parts[parts.length - 1] || eventId));
}

function plural(count) {
  return count === 1 ? "" : "s";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
