import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
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

const JsonViewer = lazy(() => import("../../components/common/JsonViewer").then((m) => ({ default: m.JsonViewer })));

type Tab = "build" | "releases" | "rollouts";

type RolloutStatus = "draft" | "testing" | "rolling_out" | "completed" | "rolled_back";

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
  status: RolloutStatus;
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

const STATUS_COLORS: Record<string, string> = {
  draft: "#6b7280",
  testing: "#2563eb",
  rolling_out: "#d97706",
  completed: "#16a34a",
  rolled_back: "#dc2626",
  pending: "#9ca3af",
  in_progress: "#d97706",
  cancelled: "#dc2626",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 600,
      background: (STATUS_COLORS[status] || "#6b7280") + "22",
      color: STATUS_COLORS[status] || "#6b7280",
      border: `1px solid ${STATUS_COLORS[status] || "#6b7280"}44`,
      textTransform: "capitalize",
    }}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function ProgressBar({ value, max, color }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div style={{ background: "#e5e7eb", borderRadius: 6, height: 8, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, background: color || "#2563eb", height: "100%", borderRadius: 6, transition: "width 0.4s" }} />
    </div>
  );
}

export function ReleasesPage() {
  const queryClient = useQueryClient();
  const userPermissions = useAuthStore((state) => state.user?.permissions || []);
  const canManage = userPermissions.includes(PERMISSIONS.TENANT_MANAGE);

  const [tab, setTab] = useState<Tab>("build");
  const [feedback, setFeedback] = useState("");

  // Build tab state
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [githubBuildVersion, setGithubBuildVersion] = useState("");
  const [targetVersion, setTargetVersion] = useState("");
  const [policyNotes, setPolicyNotes] = useState("");
  const [guideVersion, setGuideVersion] = useState("");
  const [requestedGuideVersion, setRequestedGuideVersion] = useState("");

  // Rollout tab state
  const [rolloutVersion, setRolloutVersion] = useState("");
  const [rolloutNotes, setRolloutNotes] = useState("");
  const [batchMode, setBatchMode] = useState<"default" | "custom">("default");
  const [customBatches, setCustomBatches] = useState("25,25,50");
  const [selectedRolloutId, setSelectedRolloutId] = useState<number | null>(null);

  const VERSION_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
  const versionError = version.length > 0 && !VERSION_PATTERN.test(version)
    ? "Version chacters: letters, numbers, dot, underscore, hyphen (max 64)."
    : "";
  const fileError = file && !file.name.toLowerCase().endsWith(".exe")
    ? "Sirf .exe files accept hote hain." : "";

  // Queries
  const releasesQuery = useQuery({ queryKey: queryKeys.releases, queryFn: getAgentReleases, staleTime: 60_000 });
  const buildStatusQuery = useQuery({ queryKey: ["agent", "build", "status"], queryFn: getAgentBuildStatus, staleTime: 30_000 });
  const policyQuery = useQuery({ queryKey: queryKeys.releasePolicy, queryFn: getAgentReleasePolicy, staleTime: 60_000 });
  const nextVersionQuery = useQuery({ queryKey: queryKeys.releaseNextVersion, queryFn: getNextReleaseVersion, staleTime: 30_000, enabled: canManage });
  const rolloutsQuery = useQuery({ queryKey: queryKeys.rollouts, queryFn: listRollouts, staleTime: 15_000 });
  const selectedRolloutQuery = useQuery({
    queryKey: selectedRolloutId != null ? queryKeys.rollout(selectedRolloutId) : ["rollouts", "none"],
    queryFn: () => import("../../lib/api").then(m => m.getRollout(selectedRolloutId!)),
    enabled: selectedRolloutId != null,
    refetchInterval: 5000,
  });
  const guideQuery = useQuery({
    queryKey: queryKeys.releaseGuide(requestedGuideVersion || "none"),
    queryFn: () => getAgentReleaseGuide(requestedGuideVersion),
    enabled: Boolean(requestedGuideVersion),
  });

  // Auto-fill suggested version
  useEffect(() => {
    if (nextVersionQuery.data?.next_version && !version) {
      setVersion(nextVersionQuery.data.next_version);
      setGithubBuildVersion(nextVersionQuery.data.next_version);
    }
  }, [nextVersionQuery.data, version]);

  useEffect(() => {
    const policy = policyQuery.data?.policy;
    if (policy && !targetVersion) {
      setTargetVersion(policy.target_version || "");
      setPolicyNotes(policy.notes || "");
    }
  }, [policyQuery.data, targetVersion]);

  const versions = useMemo(
    () => (releasesQuery.data?.releases || []).map((r: { version: string }) => r.version),
    [releasesQuery.data]
  );

  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.releases });
    void queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    void queryClient.invalidateQueries({ queryKey: ["agent", "build", "status"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
    void queryClient.invalidateQueries({ queryKey: queryKeys.releaseNextVersion });
    if (selectedRolloutId) void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(selectedRolloutId) });
  };

  // Mutations
  const uploadMutation = useMutation({
    mutationFn: () => uploadAgentRelease(file!, version),
    onSuccess: () => {
      setFeedback(`✓ Release ${version} upload ho gaya`);
      setVersion(""); setFile(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.releases });
      void queryClient.invalidateQueries({ queryKey: queryKeys.releaseNextVersion });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const githubBuildMutation = useMutation({
    mutationFn: () => triggerGithubBuild(githubBuildVersion),
    onSuccess: (data) => {
      setFeedback(`✓ GitHub build trigger ho gaya for v${githubBuildVersion}. Actions: ${data.actions_url}`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.releaseNextVersion });
    },
    onError: (e) => {
      const msg = extractErrorMessage(e);
      if (msg.includes("github_not_configured")) {
        setFeedback("✗ GitHub secrets set nahi hain. GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO set karo.");
      } else {
        setFeedback(`✗ ${msg}`);
      }
    },
  });

  const buildMutation = useMutation({
    mutationFn: buildAgentBinary,
    onSuccess: () => {
      setFeedback("✓ Native binary build complete");
      void queryClient.invalidateQueries({ queryKey: ["agent", "build", "status"] });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const policyMutation = useMutation({
    mutationFn: () => setAgentReleasePolicy({ target_version: targetVersion, notes: policyNotes }),
    onSuccess: () => {
      setFeedback("✓ Release policy save ho gayi");
      void queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const createRolloutMutation = useMutation({
    mutationFn: () => {
      let batchPercentages: number[] | undefined;
      if (batchMode === "custom") {
        batchPercentages = customBatches.split(",").map(s => parseInt(s.trim(), 10));
      }
      return createRollout({ version: rolloutVersion, notes: rolloutNotes, batch_percentages: batchPercentages });
    },
    onSuccess: (data) => {
      const r = data.rollout as Rollout;
      setFeedback(`✓ Rollout plan create ho gaya for v${r.version} (ID: ${r.id})`);
      setSelectedRolloutId(r.id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const testRolloutMutation = useMutation({
    mutationFn: (id: number) => markRolloutTested(id),
    onSuccess: (_, id) => {
      setFeedback("✓ Rollout tested mark ho gaya — ab deploy kar sakte ho");
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const advanceMutation = useMutation({
    mutationFn: (id: number) => advanceRolloutBatch(id),
    onSuccess: (data, id) => {
      const r = data as { status: string; batch?: RolloutBatch };
      if (r.status === "completed") setFeedback("✓ Rollout complete ho gaya! Saare agents update.");
      else setFeedback(`✓ Batch ${(r.batch as RolloutBatch)?.batch_num} start ho gaya`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  const rollbackMutation = useMutation({
    mutationFn: (id: number) => rollbackRollout(id),
    onSuccess: (_, id) => {
      setFeedback("✓ Rollout rollback ho gaya — saare pending batches cancel");
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollouts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.rollout(id) });
    },
    onError: (e) => setFeedback(`✗ ${extractErrorMessage(e)}`),
  });

  async function handleDownloadRelease(filename: string) {
    try {
      const blob = await downloadAgentReleaseBinary(filename);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) { setFeedback(`✗ ${extractErrorMessage(e)}`); }
  }

  async function handleDownloadBuilt() {
    try {
      const blob = await downloadBuiltAgentBinary();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = buildStatusQuery.data?.build?.binary_name || "aaditech-agent";
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) { setFeedback(`✗ ${extractErrorMessage(e)}`); }
  }

  const selectedRollout = selectedRolloutQuery.data?.rollout as Rollout | undefined;
  const rolloutsList = (rolloutsQuery.data?.rollouts || []) as Rollout[];

  const canAdvance = selectedRollout && ["testing", "rolling_out"].includes(selectedRollout.status);
  const canRollback = selectedRollout && ["draft", "testing", "rolling_out"].includes(selectedRollout.status);

  return (
    <ModulePage
      title="Agent Releases"
      description="Windows .exe build, versioned release management, and batched rollout control."
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshAll}>Refresh</button>
        </div>
      }
    >
      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "2px solid #e5e7eb" }}>
        {(["build", "releases", "rollouts"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            style={{
              padding: "8px 20px",
              border: "none",
              borderBottom: tab === t ? "3px solid #2563eb" : "3px solid transparent",
              background: "none",
              fontWeight: tab === t ? 700 : 400,
              color: tab === t ? "#2563eb" : "#374151",
              cursor: "pointer",
              fontSize: 14,
              marginBottom: -2,
              textTransform: "capitalize",
            }}
          >
            {t === "build" ? "Build & Upload" : t === "releases" ? "Releases" : "Batched Rollout"}
          </button>
        ))}
      </div>

      {feedback && (
        <div style={{
          padding: "10px 16px",
          borderRadius: 8,
          marginBottom: 12,
          background: feedback.startsWith("✓") ? "#f0fdf4" : "#fef2f2",
          color: feedback.startsWith("✓") ? "#166534" : "#991b1b",
          border: `1px solid ${feedback.startsWith("✓") ? "#bbf7d0" : "#fecaca"}`,
          fontWeight: 500,
          fontSize: 14,
        }}>
          {feedback}
          <button
            type="button"
            onClick={() => setFeedback("")}
            style={{ float: "right", background: "none", border: "none", cursor: "pointer", fontWeight: 700 }}
          >×</button>
        </div>
      )}

      {/* ===== BUILD & UPLOAD TAB ===== */}
      {tab === "build" && (
        <div className="module-grid">

          {/* GitHub Actions build (solve cross-compilation) */}
          <div className="module-card" style={{ borderLeft: "4px solid #2563eb" }}>
            <h3>Build Windows .exe via GitHub Actions</h3>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              Web se directly Windows .exe build trigger karo — server pe run hone wala PyInstaller Linux binary banata hai, isliye
              GitHub Actions (windows-latest runner) se real .exe banta hai. Build automatically is server pe upload ho jaata hai.
            </p>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>
                  Version (auto-suggested)
                </label>
                <input
                  value={githubBuildVersion}
                  onChange={(e) => setGithubBuildVersion(e.target.value)}
                  placeholder={nextVersionQuery.data?.next_version || "e.g. 1.2.0"}
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
                />
              </div>
              <button
                type="button"
                onClick={() => githubBuildMutation.mutate()}
                disabled={!githubBuildVersion || githubBuildMutation.isPending || !canManage}
                style={{
                  padding: "9px 20px",
                  background: "#2563eb",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  fontWeight: 600,
                  cursor: canManage && githubBuildVersion ? "pointer" : "not-allowed",
                  opacity: canManage && githubBuildVersion ? 1 : 0.6,
                  fontSize: 14,
                }}
              >
                {githubBuildMutation.isPending ? "Triggering..." : "Trigger GitHub Build"}
              </button>
            </div>
            <div style={{ marginTop: 12, padding: "8px 12px", background: "#f8fafc", borderRadius: 6, fontSize: 12, color: "#475569" }}>
              <strong>Setup required:</strong> Replit Secrets mein ye set karo:
              <code style={{ display: "block", marginTop: 4 }}>GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO</code>
              <span style={{ opacity: 0.8 }}>Optional: GITHUB_WORKFLOW_ID (default: agent-release-publish.yml)</span>
            </div>
          </div>

          {/* Manual Upload */}
          <div className="module-card">
            <h3>Upload .exe (Manual)</h3>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              Windows machine ya CI/CD se build ki hui .exe yahan upload karo.
            </p>
            <form onSubmit={(e: FormEvent) => { e.preventDefault(); if (file && version && !versionError && !fileError) uploadMutation.mutate(); }}>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>
                  Version{nextVersionQuery.data?.next_version && <span style={{ color: "#2563eb", fontWeight: 400 }}> (suggested: {nextVersionQuery.data.next_version})</span>}
                </label>
                <input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder={nextVersionQuery.data?.next_version || "e.g. 1.0.0"}
                  required
                  style={{ width: "100%", padding: "8px 12px", border: `1px solid ${versionError ? "#ef4444" : "#d1d5db"}`, borderRadius: 6, fontSize: 14 }}
                />
                {versionError && <span style={{ color: "#ef4444", fontSize: 12 }}>{versionError}</span>}
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>EXE File</label>
                <input type="file" accept=".exe" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
                {file && <span style={{ fontSize: 12, color: "#6b7280" }}>{file.name} — {(file.size / 1048576).toFixed(1)} MB</span>}
                {fileError && <span style={{ color: "#ef4444", fontSize: 12, display: "block" }}>{fileError}</span>}
              </div>
              <button
                type="submit"
                disabled={uploadMutation.isPending || !canManage || !!versionError || !!fileError || !file || !version}
                style={{ padding: "8px 20px", background: "#16a34a", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
              >
                {uploadMutation.isPending ? "Uploading..." : "Upload .exe"}
              </button>
            </form>
          </div>

          {/* Release Policy */}
          <div className="module-card">
            <h3>Release Policy</h3>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              Ye target version sabhi enrolled agents ko batata hai ki unhe kaunsa version chahiye.
            </p>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Target Version</label>
              <select
                value={targetVersion}
                onChange={(e) => setTargetVersion(e.target.value)}
                disabled={!canManage}
                style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
              >
                <option value="">-- koi nahi --</option>
                {versions.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>Notes</label>
              <input
                value={policyNotes}
                onChange={(e) => setPolicyNotes(e.target.value)}
                disabled={!canManage}
                style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
              />
            </div>
            <button
              type="button"
              onClick={() => policyMutation.mutate()}
              disabled={policyMutation.isPending || !canManage}
              style={{ padding: "8px 20px", background: "#7c3aed", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
            >
              {policyMutation.isPending ? "Saving..." : "Save Policy"}
            </button>
            {policyQuery.data?.policy?.updated_at && (
              <p style={{ fontSize: 12, color: "#6b7280", marginTop: 8 }}>
                Last updated: {new Date(policyQuery.data.policy.updated_at).toLocaleString()}
              </p>
            )}
          </div>

          {/* Server Native Build */}
          <div className="module-card">
            <h3>Server Native Build</h3>
            <p style={{ fontSize: 13, color: "#dc2626", marginBottom: 8 }}>
              ⚠ Ye server Linux pe run karta hai — yahan build hone wali binary Windows .exe nahi hogi.
              Windows .exe ke liye GitHub Actions tab use karo.
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button
                type="button"
                onClick={() => buildMutation.mutate()}
                disabled={buildMutation.isPending || !canManage}
                style={{ padding: "8px 16px", background: "#9ca3af", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 13 }}
              >
                {buildMutation.isPending ? "Building..." : "Build Native Binary"}
              </button>
              <button
                type="button"
                onClick={handleDownloadBuilt}
                disabled={!buildStatusQuery.data?.build?.binary_available}
                style={{ padding: "8px 16px", background: "#374151", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 13 }}
              >
                Download Built Binary
              </button>
            </div>
            <p style={{ fontSize: 12, color: "#6b7280", marginTop: 8 }}>
              Runtime: {buildStatusQuery.data?.build?.runtime_platform || "unknown"} |
              Binary: {buildStatusQuery.data?.build?.binary_available ? "available" : "not available"}
            </p>
          </div>

          {/* Guide lookup */}
          <div className="module-card">
            <h3>Release Guide Lookup</h3>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              Kisi agent ke current version se check karo ki use upgrade chahiye ya nahi.
            </p>
            <form onSubmit={(e: FormEvent) => { e.preventDefault(); setRequestedGuideVersion(guideVersion.trim()); }}>
              <input
                value={guideVersion}
                onChange={(e) => setGuideVersion(e.target.value)}
                placeholder="e.g. 1.0.0"
                style={{ padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, marginRight: 8 }}
              />
              <button type="submit" style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}>
                Get Guide
              </button>
            </form>
            {guideQuery.data?.guide && (
              <Suspense fallback={<div>Loading...</div>}>
                <JsonViewer data={guideQuery.data.guide} />
              </Suspense>
            )}
          </div>
        </div>
      )}

      {/* ===== RELEASES TAB ===== */}
      {tab === "releases" && (
        <div className="module-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Releases ({releasesQuery.data?.count ?? 0})</h3>
            <span style={{ fontSize: 13, color: "#6b7280" }}>
              Next suggested: <strong style={{ color: "#2563eb" }}>{nextVersionQuery.data?.next_version || "..."}</strong>
            </span>
          </div>
          {releasesQuery.isLoading ? (
            <div className="module-status loading">Loading releases...</div>
          ) : (releasesQuery.data?.releases || []).length === 0 ? (
            <div className="module-status loading">Koi release nahi mili abhi tak.</div>
          ) : (
            <table className="table-lite" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Filename</th>
                  <th>Size</th>
                  <th>Date</th>
                  <th>SHA256</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(releasesQuery.data?.releases || []).map((r: { version: string; filename: string; size_bytes: number; modified_at: string; sha256?: string; download_url?: string }) => (
                  <tr key={r.filename}>
                    <td><strong>{r.version}</strong></td>
                    <td><code style={{ fontSize: 12 }}>{r.filename}</code></td>
                    <td>{(r.size_bytes / 1048576).toFixed(2)} MB</td>
                    <td style={{ fontSize: 12, color: "#6b7280" }}>{r.modified_at ? new Date(r.modified_at).toLocaleString() : "-"}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 11, color: "#9ca3af", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {r.sha256 ? r.sha256.substring(0, 16) + "..." : "-"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button type="button" onClick={() => handleDownloadRelease(r.filename)} style={{ padding: "4px 10px", fontSize: 12, background: "#2563eb", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
                          Download
                        </button>
                        <button type="button" onClick={() => { setRolloutVersion(r.version); setTab("rollouts"); }} style={{ padding: "4px 10px", fontSize: 12, background: "#7c3aed", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
                          Deploy Rollout
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

      {/* ===== ROLLOUTS TAB ===== */}
      {tab === "rollouts" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}>

          {/* Left: create + list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Create Rollout */}
            <div className="module-card">
              <h3>Create Rollout Plan</h3>
              <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
                Ek version choose karo — agents batch-by-batch update honge.
              </p>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Version</label>
                <select
                  value={rolloutVersion}
                  onChange={(e) => setRolloutVersion(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
                >
                  <option value="">-- version select karo --</option>
                  {versions.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Notes</label>
                <input
                  value={rolloutNotes}
                  onChange={(e) => setRolloutNotes(e.target.value)}
                  placeholder="e.g. Security patch rollout"
                  style={{ width: "100%", padding: "8px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>Batch Configuration</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="radio" checked={batchMode === "default"} onChange={() => setBatchMode("default")} />
                    Default (25% + 25% + 50%)
                  </label>
                  <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
                    <input type="radio" checked={batchMode === "custom"} onChange={() => setBatchMode("custom")} />
                    Custom
                  </label>
                </div>
                {batchMode === "custom" && (
                  <div style={{ marginTop: 6 }}>
                    <input
                      value={customBatches}
                      onChange={(e) => setCustomBatches(e.target.value)}
                      placeholder="e.g. 10,40,50"
                      style={{ width: "100%", padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 13 }}
                    />
                    <span style={{ fontSize: 11, color: "#9ca3af" }}>Comma-separated percentages (total = 100)</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => createRolloutMutation.mutate()}
                disabled={!rolloutVersion || !canManage || createRolloutMutation.isPending}
                style={{ width: "100%", padding: "10px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
              >
                {createRolloutMutation.isPending ? "Creating..." : "Create Rollout Plan"}
              </button>
            </div>

            {/* Rollout list */}
            <div className="module-card">
              <h3>All Rollouts ({rolloutsList.length})</h3>
              {rolloutsQuery.isLoading ? (
                <div className="module-status loading">Loading...</div>
              ) : rolloutsList.length === 0 ? (
                <p style={{ fontSize: 13, color: "#9ca3af" }}>Koi rollout nahi abhi tak.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {rolloutsList.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setSelectedRolloutId(r.id)}
                      style={{
                        textAlign: "left",
                        padding: "10px 12px",
                        border: `2px solid ${selectedRolloutId === r.id ? "#2563eb" : "#e5e7eb"}`,
                        borderRadius: 8,
                        background: selectedRolloutId === r.id ? "#eff6ff" : "#fff",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <strong style={{ fontSize: 14 }}>v{r.version}</strong>
                        <StatusBadge status={r.status} />
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
                        {r.total_batches} batches | Batch {r.current_batch}/{r.total_batches} | {new Date(r.created_at).toLocaleDateString()}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right: rollout detail */}
          <div>
            {selectedRolloutId == null ? (
              <div className="module-card" style={{ textAlign: "center", padding: 40, color: "#9ca3af" }}>
                <p style={{ fontSize: 16 }}>Koi rollout select karo ya naya banao</p>
              </div>
            ) : selectedRolloutQuery.isLoading ? (
              <div className="module-card"><div className="module-status loading">Loading detail...</div></div>
            ) : !selectedRollout ? (
              <div className="module-card"><p style={{ color: "#ef4444" }}>Rollout nahi mila.</p></div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {/* Header */}
                <div className="module-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div>
                      <h3 style={{ margin: 0 }}>Rollout v{selectedRollout.version}</h3>
                      <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>{selectedRollout.notes || "No notes"}</p>
                    </div>
                    <StatusBadge status={selectedRollout.status} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
                    <div style={{ textAlign: "center", padding: 12, background: "#f8fafc", borderRadius: 8 }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#2563eb" }}>{selectedRollout.current_batch}</div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Current Batch</div>
                    </div>
                    <div style={{ textAlign: "center", padding: 12, background: "#f8fafc", borderRadius: 8 }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#374151" }}>{selectedRollout.total_batches}</div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Total Batches</div>
                    </div>
                    <div style={{ textAlign: "center", padding: 12, background: "#f8fafc", borderRadius: 8 }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: "#16a34a" }}>
                        {selectedRollout.batches ? selectedRollout.batches.filter(b => b.status === "completed").length : 0}
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>Completed</div>
                    </div>
                  </div>

                  {/* Overall progress */}
                  {selectedRollout.batches && selectedRollout.batches.length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>Overall Progress</span>
                        <span style={{ fontSize: 13, color: "#6b7280" }}>
                          {selectedRollout.batches.filter(b => b.status === "completed").length}/{selectedRollout.total_batches} batches
                        </span>
                      </div>
                      <ProgressBar
                        value={selectedRollout.batches.filter(b => b.status === "completed").length}
                        max={selectedRollout.total_batches}
                        color="#16a34a"
                      />
                    </div>
                  )}

                  {/* Action buttons */}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {selectedRollout.status === "draft" && (
                      <button
                        type="button"
                        onClick={() => testRolloutMutation.mutate(selectedRolloutId)}
                        disabled={testRolloutMutation.isPending || !canManage}
                        style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
                      >
                        {testRolloutMutation.isPending ? "Marking..." : "Mark as Tested ✓"}
                      </button>
                    )}
                    {canAdvance && (
                      <button
                        type="button"
                        onClick={() => advanceMutation.mutate(selectedRolloutId)}
                        disabled={advanceMutation.isPending || !canManage}
                        style={{ padding: "8px 16px", background: "#d97706", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
                      >
                        {advanceMutation.isPending ? "Advancing..." :
                          selectedRollout.status === "testing" ? "Start Rollout (Batch 1)" :
                            `Advance to Batch ${selectedRollout.current_batch + 1}`}
                      </button>
                    )}
                    {canRollback && (
                      <button
                        type="button"
                        onClick={() => { if (window.confirm("Rollback karo? Saare pending batches cancel ho jayenge.")) rollbackMutation.mutate(selectedRolloutId); }}
                        disabled={rollbackMutation.isPending || !canManage}
                        style={{ padding: "8px 16px", background: "#dc2626", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, cursor: "pointer", fontSize: 14 }}
                      >
                        {rollbackMutation.isPending ? "Rolling back..." : "Rollback ↩"}
                      </button>
                    )}
                  </div>

                  {selectedRollout.status === "draft" && (
                    <div style={{ marginTop: 12, padding: "8px 12px", background: "#eff6ff", borderRadius: 6, fontSize: 13, color: "#1d4ed8" }}>
                      💡 Pehle "Mark as Tested" karo — release ko staging/test agents pe validate karo, phir deploy karo.
                    </div>
                  )}
                </div>

                {/* Batch details */}
                {selectedRollout.batches && selectedRollout.batches.length > 0 && (
                  <div className="module-card">
                    <h3>Batch Details</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {selectedRollout.batches.map((batch) => (
                        <div
                          key={batch.id}
                          style={{
                            padding: 12,
                            border: `2px solid ${STATUS_COLORS[batch.status] || "#e5e7eb"}44`,
                            borderRadius: 8,
                            background: batch.status === "in_progress" ? "#fffbeb" : "#f9fafb",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                            <div style={{ fontWeight: 600, fontSize: 14 }}>
                              Batch {batch.batch_num} — {batch.percentage}% of agents
                            </div>
                            <StatusBadge status={batch.status} />
                          </div>
                          <ProgressBar
                            value={batch.agents_updated}
                            max={batch.agents_total || 1}
                            color={batch.status === "failed" ? "#dc2626" : "#16a34a"}
                          />
                          <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 12, color: "#6b7280" }}>
                            <span>Total: {batch.agents_total}</span>
                            <span style={{ color: "#16a34a" }}>Updated: {batch.agents_updated}</span>
                            <span style={{ color: "#dc2626" }}>Failed: {batch.agents_failed}</span>
                            {batch.agent_serials.length > 0 && (
                              <span>Agents: {batch.agent_serials.slice(0, 3).join(", ")}{batch.agent_serials.length > 3 ? ` +${batch.agent_serials.length - 3}` : ""}</span>
                            )}
                          </div>
                          {batch.started_at && (
                            <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>
                              Started: {new Date(batch.started_at).toLocaleString()}
                              {batch.completed_at && ` → Completed: ${new Date(batch.completed_at).toLocaleString()}`}
                            </div>
                          )}
                        </div>
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
