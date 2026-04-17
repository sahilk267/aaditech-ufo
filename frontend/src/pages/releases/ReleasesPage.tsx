import { lazy, Suspense, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { PERMISSIONS } from "../../config/permissions";
import { extractErrorMessage } from "../../lib/errorUtils";
import {
  buildAgentBinary,
  downloadBuiltAgentBinary,
  getAgentBuildStatus,
  getAgentReleaseGuide,
  getAgentReleasePolicy,
  getAgentReleases,
  setAgentReleasePolicy,
  uploadAgentRelease,
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { useAuthStore } from "../../store/authStore";

const JsonViewer = lazy(() => import("../../components/common/JsonViewer").then((m) => ({ default: m.JsonViewer })));

export function ReleasesPage() {
  const queryClient = useQueryClient();
  const userPermissions = useAuthStore((state) => state.user?.permissions || []);
  const canManagePolicy = userPermissions.includes(PERMISSIONS.TENANT_MANAGE);
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [targetVersion, setTargetVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [currentVersionInput, setCurrentVersionInput] = useState("");
  const [requestedGuideVersion, setRequestedGuideVersion] = useState("");
  const [feedback, setFeedback] = useState("");

  const releasesQuery = useQuery({
    queryKey: queryKeys.releases,
    queryFn: getAgentReleases,
    staleTime: 60_000,
  });

  const buildStatusQuery = useQuery({
    queryKey: ["agent", "build", "status"],
    queryFn: getAgentBuildStatus,
    staleTime: 30_000,
  });

  const policyQuery = useQuery({
    queryKey: queryKeys.releasePolicy,
    queryFn: getAgentReleasePolicy,
    staleTime: 60_000,
  });

  const guideQuery = useQuery({
    queryKey: queryKeys.releaseGuide(requestedGuideVersion || "none"),
    queryFn: () => getAgentReleaseGuide(requestedGuideVersion),
    enabled: Boolean(requestedGuideVersion),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ uploadFile, uploadVersion }: { uploadFile: File; uploadVersion: string }) =>
      uploadAgentRelease(uploadFile, uploadVersion),
    onSuccess: () => {
      setFeedback("Release uploaded");
      setVersion("");
      setFile(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.releases });
    },
    onError: (err) => setFeedback(extractErrorMessage(err)),
  });

  const policyMutation = useMutation({
    mutationFn: setAgentReleasePolicy,
    onSuccess: () => {
      setFeedback("Release policy updated");
      queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    },
    onError: (err) => setFeedback(extractErrorMessage(err)),
  });

  const buildMutation = useMutation({
    mutationFn: buildAgentBinary,
    onSuccess: async () => {
      setFeedback("Agent build completed");
      await queryClient.invalidateQueries({ queryKey: ["agent", "build", "status"] });
    },
    onError: (err) => setFeedback(extractErrorMessage(err)),
  });

  async function handleDownloadBuiltBinary() {
    try {
      const blob = await downloadBuiltAgentBinary();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = buildStatusQuery.data?.build?.binary_name || "aaditech-agent";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(url);
      setFeedback("Built agent binary downloaded");
    } catch (err) {
      setFeedback(extractErrorMessage(err));
    }
  }

  const versions = useMemo(
    () => (releasesQuery.data?.releases || []).map((release) => release.version),
    [releasesQuery.data]
  );

  function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!file || !version) {
      setFeedback("Version and file are required");
      return;
    }
    uploadMutation.mutate({ uploadFile: file, uploadVersion: version });
  }

  function handlePolicy(event: FormEvent) {
    event.preventDefault();
    if (!canManagePolicy) {
      setFeedback(`Missing permission: ${PERMISSIONS.TENANT_MANAGE}`);
      return;
    }
    policyMutation.mutate({ target_version: targetVersion, notes });
  }

  function handleGuideLookup(event: FormEvent) {
    event.preventDefault();
    const nextVersion = currentVersionInput.trim();
    if (!nextVersion) {
      setFeedback("Current agent version is required for release guidance");
      return;
    }

    setFeedback("");
    setRequestedGuideVersion(nextVersion);
  }

  const releasesError = releasesQuery.isError ? extractErrorMessage(releasesQuery.error) : "";
  const policyError = policyQuery.isError ? extractErrorMessage(policyQuery.error) : "";
  const guideError = guideQuery.isError ? extractErrorMessage(guideQuery.error) : "";

  const refreshReleases = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.releases });
    void queryClient.invalidateQueries({ queryKey: queryKeys.releasePolicy });
    void queryClient.invalidateQueries({ queryKey: ["agent", "build", "status"] });
  };

  const resetReleasesView = () => {
    setVersion("");
    setFile(null);
    setTargetVersion("");
    setNotes("");
    setCurrentVersionInput("");
    setRequestedGuideVersion("");
    setFeedback("");
  };

  return (
    <ModulePage
      title="Agent Releases"
      description="Release upload, policy, and guide workflows are now API integrated."
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshReleases} disabled={releasesQuery.isFetching || policyQuery.isFetching || buildStatusQuery.isFetching}>
            Refresh releases
          </button>
          <button type="button" onClick={resetReleasesView}>
            Reset releases view
          </button>
        </div>
      }
    >
      <div className="module-grid">
        <form className="module-card" onSubmit={handleUpload}>
          <h3>Upload Release</h3>
          <label>
            Version
            <input value={version} onChange={(e) => setVersion(e.target.value)} required />
          </label>
          <label>
            EXE File
            <input
              type="file"
              accept=".exe"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </label>
          <button
            type="submit"
            disabled={uploadMutation.isPending || !canManagePolicy}
            title={!canManagePolicy ? `Missing permission: ${PERMISSIONS.TENANT_MANAGE}` : undefined}
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </button>
          {!canManagePolicy ? <small>Release uploads require {PERMISSIONS.TENANT_MANAGE}.</small> : null}
          <small>
            Download is available via legacy session route links shown below.
          </small>
          {uploadMutation.isError ? (
            <div className="error-text" style={{ marginTop: 8 }}>
              {extractErrorMessage(uploadMutation.error)}
            </div>
          ) : null}
        </form>

        <form className="module-card" onSubmit={handlePolicy}>
          <h3>Release Policy</h3>
          <small>
            Current target: {policyQuery.data?.policy?.target_version || "(not set)"}
          </small>
          <label>
            Target Version
            <select
              value={targetVersion}
              onChange={(e) => setTargetVersion(e.target.value)}
              disabled={!canManagePolicy}
            >
              <option value="">-- none --</option>
              {versions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Notes
            <input value={notes} onChange={(e) => setNotes(e.target.value)} disabled={!canManagePolicy} />
          </label>
          <button
            type="submit"
            disabled={policyMutation.isPending || !canManagePolicy}
            title={!canManagePolicy ? `Missing permission: ${PERMISSIONS.TENANT_MANAGE}` : undefined}
          >
            {policyMutation.isPending ? "Saving..." : "Save Policy"}
          </button>
          {!canManagePolicy ? <small>Release policy updates require {PERMISSIONS.TENANT_MANAGE}.</small> : null}
          {policyMutation.isError ? (
            <div className="error-text" style={{ marginTop: 8 }}>
              {extractErrorMessage(policyMutation.error)}
            </div>
          ) : null}
        </form>
      </div>

      <div className="module-card" style={{ marginTop: 12 }}>
        <h3>Release Workflow Notes</h3>
        <p>
          Primary release lifecycle is now API-backed in SPA (list/upload/policy/guide/download).
          Legacy portals remain optional for admin fallback only.
        </p>
        <div className="module-card" style={{ marginTop: 12 }}>
          <h4>Server Build Operations</h4>
          <p>
            Control-panel parity: trigger server-side PyInstaller build and download latest built binary directly from SPA.
          </p>
          <div className="row-between" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
            <button onClick={() => buildMutation.mutate()} disabled={buildMutation.isPending || !canManagePolicy}>
              {buildMutation.isPending ? "Building..." : "Build Agent Binary"}
            </button>
            <button
              onClick={handleDownloadBuiltBinary}
              disabled={!buildStatusQuery.data?.build?.binary_available}
            >
              Download Built Binary
            </button>
            <small>
              Built binary: {buildStatusQuery.data?.build?.binary_available ? "available" : "not available"}
            </small>
          </div>
        </div>
        <div className="row-between" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
          <a href="/agent/releases" className="button" target="_blank" rel="noreferrer">
            Fallback: Legacy Release Portal
          </a>
        </div>
      </div>

      <div className="module-grid" style={{ marginTop: 12 }}>
        <div className="module-card">
          <h3>Release Guide</h3>
          <form onSubmit={handleGuideLookup}>
            <label>
              Current Agent Version
              <input
                value={currentVersionInput}
                onChange={(e) => setCurrentVersionInput(e.target.value)}
                placeholder="e.g. 1.0.0"
              />
            </label>
            <button type="submit" disabled={guideQuery.isPending} style={{ marginTop: 8 }}>
              {guideQuery.isPending ? "Fetching..." : "Get Guidance"}
            </button>
          </form>
          {guideQuery.isPending ? (
            <div className="module-status loading">Fetching release guidance...</div>
          ) : guideError ? (
            <div className="error-text">{guideError}</div>
          ) : guideQuery.data?.guide ? (
            <Suspense fallback={<div className="module-status loading">Loading guidance viewer...</div>}>
              <JsonViewer data={guideQuery.data.guide} />
            </Suspense>
          ) : (
            <p>Enter current version and request guidance when needed.</p>
          )}
        </div>

        <div className="module-card">
          <h3>Releases ({releasesQuery.data?.count ?? 0})</h3>
          {releasesQuery.isPending ? (
            <div className="module-status loading">Loading releases...</div>
          ) : releasesError ? (
            <div className="error-text">{releasesError}</div>
          ) : (releasesQuery.data?.releases || []).length === 0 ? (
            <div className="module-status loading">No releases found yet.</div>
          ) : null}
          <table className="table-lite">
            <thead>
              <tr>
                <th>Version</th>
                <th>Filename</th>
                <th>Size</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              {(releasesQuery.data?.releases || []).map((release) => (
                <tr key={release.filename}>
                  <td>{release.version}</td>
                  <td>{release.filename}</td>
                  <td>{(release.size_bytes / (1024 * 1024)).toFixed(2)} MB</td>
                  <td>
                    <a href={release.download_url || `/api/agent/releases/download/${encodeURIComponent(release.filename)}`} target="_blank" rel="noreferrer">
                      Download EXE
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {policyError ? <small className="error-text">Policy load error: {policyError}</small> : null}
          {feedback ? <small>{feedback}</small> : null}
        </div>
      </div>
    </ModulePage>
  );
}
