import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { StatCard } from "../../components/common/StatCard";
import { PERMISSIONS } from "../../config/permissions";
import { extractErrorMessage } from "../../lib/errorUtils";
import {
  advanceRolloutBatch,
  buildAgentBinary,
  createRollout,
  downloadAgentReleaseBinary,
  downloadBuiltAgentBinary,
  getAgentBuildStatus,
  getAgentReleaseGuide,
  getAgentReleasePolicy,
  getAgentReleases,
  getNextReleaseVersion,
  listRollouts,
  markRolloutTested,
  rollbackRollout,
  setAgentReleasePolicy,
  triggerGithubBuild,
  uploadAgentRelease,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { useAuthStore } from "../../store/authStore";

const JsonViewer = lazy(() =>
  import("../../components/common/JsonViewer").then((m) => ({ default: m.JsonViewer }))
);

type Tab = "build" | "releases" | "rollouts";

interface RolloutBatch {
  id: number;
  batch_num: number;
  percentage: number;
  agent_serials: string[];
  status: string;
  started_at: string | null;
  completed_at: string | null;
  agents_total: number;
  agents_updated: number;
  agents_failed: number;
}

interface Rollout {
  id: number;
  version: string;
  status: string;
  total_batches: number;
  current_batch: number;
  batch_config: number[];
  notes: string;
  github_run_url: string | null;
  created_at: string;
  tested_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_by: string | null;
  batches?: RolloutBatch[];
}

interface AgentRelease {
  version: string;
  filename: string;
  size_bytes: number;
  modified_at: string;
  sha256?: string;
}

// Map rollout/batch statuses to CSS badge class names
function badgeClass(status: string): string {
  const map: Record<string, string> = {
    draft: "badge--draft",
    testing: "badge--testing",
    rolling_out: "badge--rolling-out",
    completed: "badge--completed",
    rolled_back: "badge--rolled-back",
    pending: "badge--pending",
    in_progress: "badge--in-progress",
    cancelled: "badge--cancelled",
  };
  return `badge ${map[status] ?? "badge--draft"}`;
}

function ProgressBar({ value, max, variant }: { value: number; max: number; variant?: "warn" | "error" | "done" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="progress-track">
      <div
        className={`progress-fill${variant ? ` progress-fill--${variant}` : ""}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function BatchCard({ batch, rolloutVersion }: { batch: RolloutBatch; rolloutVersion: string }) {
  const stepClass =
    batch.status === "completed"
      ? "rollout-step rollout-step--done"
      : batch.status === "in_progress"
      ? "rollout-step rollout-step--active"
      : batch.status === "cancelled"
      ? "rollout-step rollout-step--fail"
      : "rollout-step";

  const progressVariant =
    batch.status === "cancelled"
      ? "error"
      : batch.status === "completed"
      ? "done"
      : undefined;

  return (
    <div className={stepClass}>
      <div className="row-between" style={{ marginBottom: 8 }}>
        <div>
          <strong style={{ fontSize: "0.95rem" }}>Batch {batch.batch_num}</strong>
          <span style={{ marginLeft: 8, fontSize: "0.82rem", color: "#64748b" }}>
            {batch.percentage}% of fleet
          </span>
        </div>
        <span className={badgeClass(batch.status)}>{batch.status.replace(/_/g, " ")}</span>
      </div>

      <ProgressBar value={batch.agents_updated} max={batch.agents_total || 1} variant={progressVariant} />

      <div className="stat-row" style={{ marginTop: 10 }}>
        <div className="stat-pill">
          <strong>{batch.agents_total}</strong>
          <span>Total</span>
        </div>
        <div className="stat-pill">
          <strong style={{ color: "#15803d" }}>{batch.agents_updated}</strong>
          <span>Updated</span>
        </div>
        <div className="stat-pill">
          <strong style={{ color: batch.agents_failed > 0 ? "#b91c1c" : "#64748b" }}>
            {batch.agents_failed}
          </strong>
          <span>Failed</span>
        </div>
        <div className="stat-pill" style={{ flex: 2 }}>
          <strong style={{ fontSize: "0.95rem" }}>
            {batch.agents_updated}/{batch.agents_total}
          </strong>
          <span>on v{rolloutVersion}</span>
        </div>
      </div>

      {batch.agent_serials.length > 0 && (
        <p style={{ marginTop: 8, fontSize: "0.78rem", color: "#94a3b8" }}>
          Agents: {batch.agent_serials.slice(0, 4).join(", ")}
          {batch.agent_serials.length > 4 && ` +${batch.agent_serials.length - 4} more`}
        </p>
      )}

      {batch.started_at && (
        <p style={{ marginTop: 4, fontSize: "0.75rem", color: "#94a3b8" }}>
          Started {new Date(batch.started_at).toLocaleString()}
          {batch.completed_at && ` · Done ${new Date(batch.completed_at).toLocaleString()}`}
        </p>
      )}
    </div>
  );
}

export function ReleasesPage() {
  const queryClient = useQueryClient();
  const userPermissions = useAuthStore((s) => s.user?.permissions ?? []);
  const canManage = userPermissions.includes(PERMISSIONS.TENANT_MANAGE);

  const [tab, setTab] = useState<Tab>("build");
  const [feedback, setFeedback] = useState<{ msg: string; ok: boolean } | null>(null);

  // Build tab
  const [githubVersion, setGithubVersion] = useState("");
  const [uploadVersion, setUploadVersion] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [targetVersion, setTargetVersion] = useState("");
  const [policyNotes, setPolicyNotes] = useState("");
  const [guideVersion, setGuideVersion] = useState("");
  const [requestedGuideVersion, setRequestedGuideVersion] = useState("");

  // Rollouts tab
  const [rolloutVersion, setRolloutVersion] = useState("");
  const [rolloutNotes, setRolloutNotes] = useState("");
  const [batchMode, setBatchMode] = useState<"default" | "custom">("default");
  const [customBatches, setCustomBatches] = useState("25,25,50");
  const [selectedRolloutId, setSelectedRolloutId] = useState<number | null>(null);

  const ok = (msg: string) => setFeedback({ msg, ok: true });
  const err = (msg: string) => setFeedback({ msg, ok: false });

  // ── Queries ─────────────────────────────────────────────────────────────
  const releasesQ = useQuery({ queryKey: queryKeys.releases, queryFn: getAgentReleases, staleTime: 60_000 });
  const buildStatusQ = useQuery({ queryKey: ["agent", "build", "status"], queryFn: getAgentBuildStatus, staleTime: 30_000 });
  const policyQ = useQuery({ queryKey: queryKeys.releasePolicy, queryFn: getAgentReleasePolicy, staleTime: 60_000 });
  const nextVersionQ = useQuery({ queryKey: queryKeys.releaseNextVersion, queryFn: getNextReleaseVersion, staleTime: 30_000, enabled: canManage });
  const rolloutsQ = useQuery({ queryKey: queryKeys.rollouts, queryFn: listRollouts, staleTime: 15_000 });
  const rolloutDetailQ = useQuery({
    queryKey: selectedRolloutId != null ? queryKeys.rollout(selectedRolloutId) : ["rollouts", "none"],
    queryFn: () => import("../../lib/api").then((m) => m.getRollout(selectedRolloutId!)),
    enabled: selectedRolloutId != null,
    refetchInterval: 6000,
  });
  const guideQ = useQuery({
    queryKey: queryKeys.releaseGuide(requestedGuideVersion || "none"),
    queryFn: () => getAgentReleaseGuide(requestedGuideVersion),
    enabled: Boolean(requestedGuideVersion),
  });

  // Auto-fill suggested version
  useEffect(() => {
    const next = nextVersionQ.data?.next_version;
    if (next) {
      if (!githubVersion) setGithubVersion(next);
      if (!uploadVersion) setUploadVersion(next);
    }
  }, [nextVersionQ.data, githubVersion, uploadVersion]);

  useEffect(() => {
    const p = policyQ.data?.policy;
    if (p && !targetVersion) {
      setTargetVersion(p.target_version ?? "");
      setPolicyNotes(p.notes ?? "");
    }
  }, [policyQ.data, targetVersion]);

  const versions = useMemo(
    () => (releasesQ.data?.releases ?? []).map((r: AgentRelease) => r.version),
    [releasesQ.data]
  );
  const releasesList = (releasesQ.data?.releases ?? []) as AgentRelease[];
  const rolloutsList = (rolloutsQ.data?.rollouts ?? []) as Rollout[];
  const selectedRollout = rolloutDetailQ.data?.rollout as Rollout | undefined;

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.releases });
    void queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
    void queryClient.invalidateQueries({ queryKey: queryKeys.releaseNextVersion });
    if (selectedRolloutId) void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(selectedRolloutId) });
  };

  // ── Validation ───────────────────────────────────────────────────────────
  const VERSION_RE = /^[A-Za-z0-9._-]{1,64}$/;
  const uploadVersionErr = uploadVersion && !VERSION_RE.test(uploadVersion)
    ? "Use letters, numbers, dot, hyphen or underscore (max 64)." : "";
  const uploadFileErr = uploadFile && !uploadFile.name.toLowerCase().endsWith(".exe")
    ? "Only .exe files are accepted." : "";
  const customBatchErr = (() => {
    if (batchMode !== "custom") return "";
    const parts = customBatches.split(",").map(s => parseInt(s.trim(), 10));
    if (parts.some(isNaN)) return "Use comma-separated numbers.";
    if (parts.reduce((a, b) => a + b, 0) !== 100) return "Percentages must sum to 100.";
    return "";
  })();

  // ── Mutations ────────────────────────────────────────────────────────────
  const githubBuildM = useMutation({
    mutationFn: () => triggerGithubBuild(githubVersion),
    onSuccess: (d) => ok(`GitHub Actions triggered for v${githubVersion}. Actions: ${d.actions_url}`),
    onError: (e) => {
      const msg = extractErrorMessage(e);
      if (msg.includes("github_not_configured"))
        err("GitHub secrets not configured. Set GITHUB_PERSONAL_ACCESS_TOKEN as a Replit secret.");
      else err(msg);
    },
  });

  const uploadM = useMutation({
    mutationFn: () => uploadAgentRelease(uploadFile!, uploadVersion),
    onSuccess: () => {
      ok(`Release v${uploadVersion} uploaded successfully.`);
      setUploadVersion(""); setUploadFile(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.releases });
      void queryClient.invalidateQueries({ queryKey: queryKeys.releaseNextVersion });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  const buildM = useMutation({
    mutationFn: buildAgentBinary,
    onSuccess: () => ok("Server-side binary build complete."),
    onError: (e) => err(extractErrorMessage(e)),
  });

  const policyM = useMutation({
    mutationFn: () => setAgentReleasePolicy({ target_version: targetVersion, notes: policyNotes }),
    onSuccess: () => {
      ok("Release policy saved.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  const createRolloutM = useMutation({
    mutationFn: () => {
      const bp = batchMode === "custom"
        ? customBatches.split(",").map(s => parseInt(s.trim(), 10))
        : undefined;
      return createRollout({ version: rolloutVersion, notes: rolloutNotes, batch_percentages: bp });
    },
    onSuccess: (d) => {
      const r = d.rollout as Rollout;
      ok(`Rollout plan created for v${r.version} (ID: ${r.id}).`);
      setSelectedRolloutId(r.id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  const testM = useMutation({
    mutationFn: (id: number) => markRolloutTested(id),
    onSuccess: (_, id) => {
      ok("Rollout marked as tested — ready to deploy.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  const advanceM = useMutation({
    mutationFn: (id: number) => advanceRolloutBatch(id),
    onSuccess: (d, id) => {
      const res = d as { status: string };
      ok(res.status === "completed"
        ? "All batches complete — rollout finished!"
        : `Next batch started.`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  const rollbackM = useMutation({
    mutationFn: (id: number) => rollbackRollout(id),
    onSuccess: (_, id) => {
      ok("Rollout rolled back — all pending batches cancelled.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => err(extractErrorMessage(e)),
  });

  // ── Download helpers ─────────────────────────────────────────────────────
  async function downloadRelease(filename: string) {
    try {
      const blob = await downloadAgentReleaseBinary(filename);
      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), { href: url, download: filename }).click();
      URL.revokeObjectURL(url);
    } catch (e) { err(extractErrorMessage(e)); }
  }

  async function downloadBuilt() {
    try {
      const blob = await downloadBuiltAgentBinary();
      const name = buildStatusQ.data?.build?.binary_name ?? "aaditech-agent";
      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), { href: url, download: name }).click();
      URL.revokeObjectURL(url);
    } catch (e) { err(extractErrorMessage(e)); }
  }

  // ── Derived states ───────────────────────────────────────────────────────
  const canAdvance = selectedRollout && ["testing", "rolling_out"].includes(selectedRollout.status);
  const canRollback = selectedRollout && ["draft", "testing", "rolling_out"].includes(selectedRollout.status);
  const batchesDone = selectedRollout?.batches?.filter(b => b.status === "completed").length ?? 0;
  const totalBatches = selectedRollout?.total_batches ?? 0;
  const nextSuggestedVersion = nextVersionQ.data?.next_version ?? "";

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <ModulePage
      title="Agent Releases"
      description="Build, publish, and safely roll out agent updates to your fleet."
      actions={
        <div className="module-page-actions-group">
          <button type="button" className="button--secondary" onClick={invalidateAll}>
            Refresh
          </button>
        </div>
      }
    >
      {/* Tabs */}
      <div className="page-tabs">
        {(["build", "releases", "rollouts"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`page-tab${tab === t ? " page-tab--active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "build" ? "Build & Upload" : t === "releases" ? "All Releases" : "Batched Rollout"}
          </button>
        ))}
      </div>

      {/* Feedback */}
      {feedback && (
        <div className={`feedback-banner ${feedback.ok ? "feedback-banner--success" : "feedback-banner--error"}`}>
          <span>{feedback.msg}</span>
          <button type="button" onClick={() => setFeedback(null)}>✕</button>
        </div>
      )}

      {/* ================================================================= */}
      {/* BUILD & UPLOAD TAB                                                  */}
      {/* ================================================================= */}
      {tab === "build" && (
        <div className="module-grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))" }}>

          {/* GitHub Actions trigger */}
          <div className="module-card">
            <p className="section-label">Windows .exe via GitHub Actions</p>
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Trigger Cloud Build</h3>
            <p style={{ fontSize: "0.88rem", color: "#475569", margin: "0 0 16px" }}>
              Cross-compiles a real Windows .exe on a <code>windows-latest</code> GitHub runner and
              auto-uploads it here — solving the Linux→Windows PyInstaller limitation.
            </p>

            <div className="form-field">
              <label className="form-label">
                Version{nextSuggestedVersion && (
                  <span className="version-chip" style={{ marginLeft: 8 }}>{nextSuggestedVersion}</span>
                )} <span style={{ color: "#94a3b8", fontWeight: 400 }}>auto-suggested</span>
              </label>
              <input
                className="form-input"
                value={githubVersion}
                onChange={(e) => setGithubVersion(e.target.value)}
                placeholder={nextSuggestedVersion || "e.g. 1.2.0"}
              />
            </div>

            <div style={{ marginTop: 12 }}>
              <button
                type="button"
                onClick={() => githubBuildM.mutate()}
                disabled={!githubVersion || githubBuildM.isPending || !canManage}
              >
                {githubBuildM.isPending ? "Triggering…" : "▶ Trigger GitHub Build"}
              </button>
            </div>

            <div className="setup-panel" style={{ marginTop: 14 }}>
              <strong>Required Replit Secrets</strong>
              <code>GITHUB_PERSONAL_ACCESS_TOKEN</code>
              <div style={{ marginTop: 8, fontSize: "0.82rem", color: "#64748b" }}>
                Already configured: <strong>GITHUB_OWNER</strong> = sahilk267 ·{" "}
                <strong>GITHUB_REPO</strong> = aaditech-ufo ·{" "}
                <strong>GITHUB_WORKFLOW_ID</strong> = agent-release-publish.yml
              </div>
            </div>
          </div>

          {/* Manual Upload */}
          <div className="module-card">
            <p className="section-label">Manual Upload</p>
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Upload .exe File</h3>
            <p style={{ fontSize: "0.88rem", color: "#475569", margin: "0 0 16px" }}>
              Upload a pre-built Windows .exe from your local machine or CI pipeline.
            </p>

            <form
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                if (uploadFile && uploadVersion && !uploadVersionErr && !uploadFileErr) uploadM.mutate();
              }}
            >
              <div className="form-field" style={{ marginBottom: 10 }}>
                <label className="form-label">
                  Version <span className="required-marker">*</span>
                  {nextSuggestedVersion && (
                    <span style={{ marginLeft: 8, fontSize: "0.8rem", color: "#0f766e", fontWeight: 400 }}>
                      (next suggested: {nextSuggestedVersion})
                    </span>
                  )}
                </label>
                <input
                  className={`form-input${uploadVersionErr ? " form-input--error" : ""}`}
                  value={uploadVersion}
                  onChange={(e) => setUploadVersion(e.target.value)}
                  placeholder={nextSuggestedVersion || "e.g. 1.0.0"}
                  required
                />
                {uploadVersionErr && <span className="form-error">{uploadVersionErr}</span>}
              </div>

              <div className="form-field" style={{ marginBottom: 14 }}>
                <label className="form-label">
                  EXE File <span className="required-marker">*</span>
                </label>
                <input
                  type="file"
                  accept=".exe"
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                  required
                />
                {uploadFile && (
                  <span className="form-helper">
                    {uploadFile.name} — {(uploadFile.size / 1048576).toFixed(1)} MB
                  </span>
                )}
                {uploadFileErr && <span className="form-error">{uploadFileErr}</span>}
              </div>

              <button
                type="submit"
                className="button--green"
                disabled={uploadM.isPending || !canManage || !!uploadVersionErr || !!uploadFileErr || !uploadFile || !uploadVersion}
              >
                {uploadM.isPending ? "Uploading…" : "↑ Upload Release"}
              </button>
            </form>
          </div>

          {/* Release Policy */}
          <div className="module-card">
            <p className="section-label">Update Policy</p>
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Global Target Version</h3>
            <p style={{ fontSize: "0.88rem", color: "#475569", margin: "0 0 16px" }}>
              All enrolled agents use this version as their update target unless overridden by an active rollout.
            </p>

            <div className="form-field" style={{ marginBottom: 10 }}>
              <label className="form-label">Target Version</label>
              <select
                className="form-input"
                value={targetVersion}
                onChange={(e) => setTargetVersion(e.target.value)}
                disabled={!canManage}
              >
                <option value="">— none —</option>
                {versions.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>

            <div className="form-field" style={{ marginBottom: 14 }}>
              <label className="form-label">Notes</label>
              <input
                className="form-input"
                value={policyNotes}
                onChange={(e) => setPolicyNotes(e.target.value)}
                placeholder="e.g. Security patch, stable release"
                disabled={!canManage}
              />
            </div>

            <button
              type="button"
              className="button--purple"
              onClick={() => policyM.mutate()}
              disabled={policyM.isPending || !canManage}
            >
              {policyM.isPending ? "Saving…" : "Save Policy"}
            </button>

            {policyQ.data?.policy?.updated_at && (
              <p className="form-helper" style={{ marginTop: 10 }}>
                Last updated: {new Date(policyQ.data.policy.updated_at).toLocaleString()}
              </p>
            )}
          </div>

          {/* Server Native Build */}
          <div className="module-card">
            <p className="section-label">Server Build</p>
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Native Binary (Linux only)</h3>

            <div className="setup-panel setup-panel--warn" style={{ margin: "0 0 14px" }}>
              ⚠ This server runs on Linux — the output binary will <strong>not</strong> be a Windows .exe.
              For a real Windows .exe use the GitHub Actions tab above.
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="button--secondary"
                onClick={() => buildM.mutate()}
                disabled={buildM.isPending || !canManage}
              >
                {buildM.isPending ? "Building…" : "Build Native Binary"}
              </button>
              <button
                type="button"
                className="button--secondary"
                onClick={downloadBuilt}
                disabled={!buildStatusQ.data?.build?.binary_available}
              >
                ↓ Download
              </button>
            </div>

            <p className="form-helper" style={{ marginTop: 10 }}>
              Runtime: <strong>{buildStatusQ.data?.build?.runtime_platform ?? "unknown"}</strong> ·
              Binary available: <strong>{buildStatusQ.data?.build?.binary_available ? "Yes" : "No"}</strong>
            </p>
          </div>

          {/* Guide Lookup */}
          <div className="module-card" style={{ gridColumn: "1 / -1" }}>
            <p className="section-label">Diagnostic</p>
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Release Guide Lookup</h3>
            <p style={{ fontSize: "0.88rem", color: "#475569", margin: "0 0 14px" }}>
              Check what version an agent should be running given its current version.
            </p>
            <form
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                setRequestedGuideVersion(guideVersion.trim());
              }}
              style={{ display: "flex", gap: 8, alignItems: "center" }}
            >
              <input
                className="form-input"
                style={{ maxWidth: 200 }}
                value={guideVersion}
                onChange={(e) => setGuideVersion(e.target.value)}
                placeholder="Current version (e.g. 1.0.0)"
              />
              <button type="submit">Get Guide</button>
            </form>
            {guideQ.data?.guide && (
              <Suspense fallback={<div className="module-status loading">Loading…</div>}>
                <JsonViewer data={guideQ.data.guide} />
              </Suspense>
            )}
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* ALL RELEASES TAB                                                    */}
      {/* ================================================================= */}
      {tab === "releases" && (
        <div className="module-card">
          <div className="row-between" style={{ marginBottom: 14 }}>
            <div>
              <h3 style={{ margin: 0 }}>
                Uploaded Releases
                <span style={{ marginLeft: 8, fontWeight: 400, color: "#64748b", fontSize: "0.9rem" }}>
                  ({releasesList.length})
                </span>
              </h3>
            </div>
            {nextSuggestedVersion && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.88rem", color: "#64748b" }}>
                Next suggested version:
                <span className="version-chip">{nextSuggestedVersion}</span>
              </div>
            )}
          </div>

          {releasesQ.isLoading ? (
            <div className="module-status loading">Loading releases…</div>
          ) : releasesList.length === 0 ? (
            <div className="empty-state">
              <p>No releases uploaded yet.</p>
              <p style={{ marginTop: 4, fontSize: "0.85rem" }}>
                Use the Build & Upload tab to add your first release.
              </p>
            </div>
          ) : (
            <table className="table-lite">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Filename</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>SHA-256</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {releasesList.map((r) => (
                  <tr key={r.filename}>
                    <td>
                      <span className="version-chip">{r.version}</span>
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.83rem" }}>{r.filename}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{(r.size_bytes / 1_048_576).toFixed(2)} MB</td>
                    <td style={{ fontSize: "0.83rem", color: "#64748b", whiteSpace: "nowrap" }}>
                      {r.modified_at ? new Date(r.modified_at).toLocaleDateString() : "—"}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "#94a3b8", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {r.sha256 ? `${r.sha256.slice(0, 14)}…` : "—"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button type="button" className="button--sm" onClick={() => downloadRelease(r.filename)}>
                          ↓ Download
                        </button>
                        <button
                          type="button"
                          className="button--sm button--purple"
                          onClick={() => { setRolloutVersion(r.version); setTab("rollouts"); }}
                        >
                          Deploy →
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ================================================================= */}
      {/* BATCHED ROLLOUT TAB                                                 */}
      {/* ================================================================= */}
      {tab === "rollouts" && (
        <div className="panel-split">

          {/* ── Left panel ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Create new rollout */}
            <div className="module-card">
              <p className="section-label">New Plan</p>
              <h3 style={{ margin: "0 0 4px", fontSize: "1rem" }}>Create Rollout</h3>
              <p style={{ fontSize: "0.83rem", color: "#475569", marginBottom: 14 }}>
                Agents are assigned to batches from the enrolled fleet. Each batch is deployed
                one at a time; agents report back via heartbeat to auto-complete each batch.
              </p>

              <div className="form-field" style={{ marginBottom: 10 }}>
                <label className="form-label">Target Version <span className="required-marker">*</span></label>
                <select
                  className="form-input"
                  value={rolloutVersion}
                  onChange={(e) => setRolloutVersion(e.target.value)}
                >
                  <option value="">— select a version —</option>
                  {versions.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>

              <div className="form-field" style={{ marginBottom: 10 }}>
                <label className="form-label">Notes</label>
                <input
                  className="form-input"
                  value={rolloutNotes}
                  onChange={(e) => setRolloutNotes(e.target.value)}
                  placeholder="e.g. Security hotfix for all agents"
                />
              </div>

              <div className="form-field" style={{ marginBottom: 14 }}>
                <label className="form-label">Batch Configuration</label>
                <div style={{ display: "flex", gap: 14 }}>
                  <label className="form-checkbox-label">
                    <input
                      type="radio"
                      className="form-checkbox"
                      checked={batchMode === "default"}
                      onChange={() => setBatchMode("default")}
                    />
                    Default (25% + 25% + 50%)
                  </label>
                  <label className="form-checkbox-label">
                    <input
                      type="radio"
                      className="form-checkbox"
                      checked={batchMode === "custom"}
                      onChange={() => setBatchMode("custom")}
                    />
                    Custom
                  </label>
                </div>
                {batchMode === "custom" && (
                  <div style={{ marginTop: 8 }}>
                    <input
                      className={`form-input${customBatchErr ? " form-input--error" : ""}`}
                      value={customBatches}
                      onChange={(e) => setCustomBatches(e.target.value)}
                      placeholder="e.g. 10,40,50"
                    />
                    {customBatchErr
                      ? <span className="form-error">{customBatchErr}</span>
                      : <span className="form-helper">Comma-separated percentages, must sum to 100.</span>
                    }
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => createRolloutM.mutate()}
                disabled={!rolloutVersion || !canManage || createRolloutM.isPending || !!customBatchErr}
                style={{ width: "100%" }}
              >
                {createRolloutM.isPending ? "Creating…" : "Create Rollout Plan"}
              </button>
            </div>

            {/* Rollout list */}
            <div className="module-card">
              <p className="section-label">History</p>
              <h3 style={{ margin: "0 0 12px", fontSize: "1rem" }}>
                All Rollouts ({rolloutsList.length})
              </h3>

              {rolloutsQ.isLoading ? (
                <div className="module-status loading">Loading…</div>
              ) : rolloutsList.length === 0 ? (
                <p className="form-helper">No rollouts yet. Create one above.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {rolloutsList.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      className={`rollout-list-item${selectedRolloutId === r.id ? " rollout-list-item--selected" : ""}`}
                      onClick={() => setSelectedRolloutId(r.id)}
                    >
                      <div className="row-between">
                        <span className="version-chip">v{r.version}</span>
                        <span className={badgeClass(r.status)}>{r.status.replace(/_/g, " ")}</span>
                      </div>
                      <div style={{ marginTop: 6, fontSize: "0.78rem", color: "#64748b" }}>
                        {r.total_batches} batches · Batch {r.current_batch}/{r.total_batches} ·{" "}
                        {new Date(r.created_at).toLocaleDateString()}
                      </div>
                      {r.notes && (
                        <div style={{ marginTop: 4, fontSize: "0.78rem", color: "#94a3b8" }}>{r.notes}</div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── Right panel (rollout detail) ── */}
          <div>
            {selectedRolloutId == null ? (
              <div className="module-card empty-state">
                <p>Select a rollout from the list to see details</p>
                <p style={{ marginTop: 4, fontSize: "0.85rem" }}>or create a new one above</p>
              </div>
            ) : rolloutDetailQ.isLoading ? (
              <div className="module-card"><div className="module-status loading">Loading rollout details…</div></div>
            ) : !selectedRollout ? (
              <div className="module-card"><p className="form-error-banner">Rollout not found.</p></div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

                {/* Header card */}
                <div className="module-card">
                  <div className="row-between" style={{ marginBottom: 12 }}>
                    <div>
                      <h3 style={{ margin: 0 }}>
                        Rollout{" "}
                        <span className="version-chip">v{selectedRollout.version}</span>
                      </h3>
                      {selectedRollout.notes && (
                        <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "#64748b" }}>
                          {selectedRollout.notes}
                        </p>
                      )}
                    </div>
                    <span className={badgeClass(selectedRollout.status)}>
                      {selectedRollout.status.replace(/_/g, " ")}
                    </span>
                  </div>

                  {/* Stats */}
                  <div className="grid-cards" style={{ gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
                    <div className="stat-card">
                      <span className="label">Batches</span>
                      <strong>{totalBatches}</strong>
                    </div>
                    <div className={`stat-card${batchesDone === totalBatches && totalBatches > 0 ? " stat-card--ok" : ""}`}>
                      <span className="label">Completed</span>
                      <strong>{batchesDone}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="label">Current</span>
                      <strong>{selectedRollout.current_batch || "—"}</strong>
                    </div>
                    <div className={`stat-card${selectedRollout.status === "completed" ? " stat-card--ok" : selectedRollout.status === "rolled_back" ? " stat-card--error" : ""}`}>
                      <span className="label">Status</span>
                      <strong style={{ fontSize: "1rem", textTransform: "capitalize" }}>
                        {selectedRollout.status.replace(/_/g, " ")}
                      </strong>
                    </div>
                  </div>

                  {/* Overall progress */}
                  {totalBatches > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <div className="row-between" style={{ marginBottom: 6, fontSize: "0.85rem" }}>
                        <span>Overall progress</span>
                        <span style={{ color: "#64748b" }}>{batchesDone} / {totalBatches} batches</span>
                      </div>
                      <ProgressBar
                        value={batchesDone}
                        max={totalBatches}
                        variant={selectedRollout.status === "completed" ? "done" : selectedRollout.status === "rolled_back" ? "error" : undefined}
                      />
                    </div>
                  )}

                  {/* Heartbeat note */}
                  {selectedRollout.status === "rolling_out" && (
                    <div className="setup-panel" style={{ marginBottom: 14 }}>
                      <strong>Auto-completion active</strong> — Agents in the current batch report their
                      version via heartbeat every minute. When all agents confirm the new version, the batch
                      completes automatically. Refresh to see live progress.
                    </div>
                  )}

                  {/* Action buttons */}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {selectedRollout.status === "draft" && (
                      <button
                        type="button"
                        onClick={() => testM.mutate(selectedRolloutId)}
                        disabled={testM.isPending || !canManage}
                      >
                        {testM.isPending ? "Marking…" : "✓ Mark as Tested"}
                      </button>
                    )}
                    {canAdvance && (
                      <button
                        type="button"
                        className="button--amber"
                        onClick={() => advanceM.mutate(selectedRolloutId)}
                        disabled={advanceM.isPending || !canManage}
                      >
                        {advanceM.isPending ? "Advancing…"
                          : selectedRollout.status === "testing"
                          ? "▶ Start Rollout (Batch 1)"
                          : `▶ Advance to Batch ${selectedRollout.current_batch + 1}`}
                      </button>
                    )}
                    {canRollback && (
                      <button
                        type="button"
                        className="button--danger"
                        onClick={() => {
                          if (window.confirm("Roll back this rollout? All pending batches will be cancelled.")) {
                            rollbackM.mutate(selectedRolloutId);
                          }
                        }}
                        disabled={rollbackM.isPending || !canManage}
                      >
                        {rollbackM.isPending ? "Rolling back…" : "↩ Rollback"}
                      </button>
                    )}
                  </div>

                  {selectedRollout.status === "draft" && (
                    <div className="setup-panel" style={{ marginTop: 12 }}>
                      <strong>Next step:</strong> Click "Mark as Tested" once you've validated this release
                      on a staging or test agent, then click "Start Rollout" to begin batch deployment.
                    </div>
                  )}

                  {/* Timestamps */}
                  <div style={{ marginTop: 14, fontSize: "0.78rem", color: "#94a3b8", display: "flex", gap: 14, flexWrap: "wrap" }}>
                    <span>Created: {new Date(selectedRollout.created_at).toLocaleString()}</span>
                    {selectedRollout.tested_at && <span>Tested: {new Date(selectedRollout.tested_at).toLocaleString()}</span>}
                    {selectedRollout.started_at && <span>Started: {new Date(selectedRollout.started_at).toLocaleString()}</span>}
                    {selectedRollout.completed_at && <span>Completed: {new Date(selectedRollout.completed_at).toLocaleString()}</span>}
                    {selectedRollout.created_by && <span>By: {selectedRollout.created_by}</span>}
                  </div>
                </div>

                {/* Batch cards */}
                {selectedRollout.batches && selectedRollout.batches.length > 0 && (
                  <div className="module-card">
                    <p className="section-label">Deployment Batches</p>
                    <h3 style={{ margin: "0 0 14px", fontSize: "1rem" }}>
                      Batch Progress
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {selectedRollout.batches.map((batch) => (
                        <BatchCard key={batch.id} batch={batch} rolloutVersion={selectedRollout.version} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </ModulePage>
  );
}
