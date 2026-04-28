import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { PERMISSIONS } from "../../config/permissions";
import { extractErrorMessage } from "../../lib/errorUtils";
import {
  buildAgentBinary,
  downloadBuiltAgentBinary,
  downloadAgentReleaseBinary,
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

  const VERSION_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
  const MAX_UPLOAD_MB = 256;
  const versionError = version.length > 0 && !VERSION_PATTERN.test(version)
    ? "Version may only contain letters, numbers, dot, underscore, hyphen (1-64 chars)."
    : "";
  const fileError = (() => {
    if (!file) return "";
    if (!file.name.toLowerCase().endsWith(".exe")) {
      return "Selected file is not a .exe — only Windows executables are accepted.";
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return `File is larger than ${MAX_UPLOAD_MB} MB.`;
    }
    return "";
  })();

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

  useEffect(() => {
    const policy = policyQuery.data?.policy;
    if (policy && targetVersion === "" && notes === "") {
      setTargetVersion(policy.target_version || "");
      setNotes(policy.notes || "");
    }
  }, [policyQuery.data?.policy, targetVersion, notes]);

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

  async function handleDownloadRelease(filename: string) {
    try {
      const blob = await downloadAgentReleaseBinary(filename);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(url);
      setFeedback(`Release downloaded: ${filename}`);
    } catch (err) {
      setFeedback(extractErrorMessage(err));
    }
  }

  async function handleCopyReleaseUrl(downloadUrl: string | undefined) {
    if (!downloadUrl) {
      setFeedback("No download URL available for this release.");
      return;
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(downloadUrl);
        setFeedback("Release download URL copied to clipboard.");
      } else {
        setFeedback("Clipboard copy is not supported by this browser.");
      }
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
    if (versionError) {
      setFeedback(versionError);
      return;
    }
    if (fileError) {
      setFeedback(fileError);
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
      <div className="module-card" style={{ marginTop: 8, borderLeft: "4px solid #2563eb" }}>
        <h3>How to obtain a Windows .exe</h3>
        <p style={{ marginBottom: 8 }}>
          PyInstaller cannot cross-compile a Windows executable from a Linux server. Pick one of the
          three supported paths below to produce a real <code>.exe</code>, then upload it here.
        </p>
        <ol style={{ marginLeft: 18 }}>
          <li>
            <strong>GitHub Actions (recommended).</strong> Push a tag matching{" "}
            <code>agent-v&lt;version&gt;</code> (e.g. <code>git tag agent-v1.0.0 &amp;&amp; git push --tags</code>),
            or trigger the <em>Agent Release Build and Publish</em> workflow manually from the
            Actions tab. The workflow runs on <code>windows-latest</code>, attaches the{" "}
            <code>.exe</code> to a GitHub Release, and (if{" "}
            <code>AGENT_RELEASE_UPLOAD_URL</code> + <code>AGENT_RELEASE_API_KEY</code> secrets are
            set) auto-uploads it to this server.
          </li>
          <li>
            <strong>Local Windows machine.</strong> Run{" "}
            <code>powershell -ExecutionPolicy Bypass -File .\scripts\build_agent_windows.ps1 -Version 1.0.0</code>{" "}
            on a Windows host with Python 3.12 installed. The output appears in{" "}
            <code>agent\dist\aaditech-agent-1.0.0.exe</code>.
          </li>
          <li>
            <strong>Manual upload.</strong> Use the <em>Upload Release</em> form below. The file is
            renamed to <code>aaditech-agent-&lt;version&gt;.exe</code> and becomes immediately
            downloadable by enrolled agents.
          </li>
        </ol>
        <small>
          See <code>docs/AGENT_RELEASE_BUILD.md</code> for full build/upload documentation.
        </small>
      </div>

      <div className="module-grid">
        <form className="module-card" onSubmit={handleUpload}>
          <h3>Upload Release (.exe)</h3>
          <label>
            Version
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g. 1.0.0 or 1.2.0-beta"
              required
            />
          </label>
          {versionError ? <small className="error-text">{versionError}</small> : null}
          <label>
            EXE File
            <input
              type="file"
              accept=".exe,application/x-msdownload,application/octet-stream"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </label>
          {file ? (
            <small>
              Selected: <code>{file.name}</code> — {(file.size / (1024 * 1024)).toFixed(2)} MB
            </small>
          ) : null}
          {fileError ? <small className="error-text">{fileError}</small> : null}
          <button
            type="submit"
            disabled={
              uploadMutation.isPending ||
              !canManagePolicy ||
              !!versionError ||
              !!fileError ||
              !file ||
              !version
            }
            title={!canManagePolicy ? `Missing permission: ${PERMISSIONS.TENANT_MANAGE}` : undefined}
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload .exe"}
          </button>
          {!canManagePolicy ? <small>Release uploads require {PERMISSIONS.TENANT_MANAGE}.</small> : null}
          <small>
            Uploaded files are normalized to <code>aaditech-agent-&lt;version&gt;.exe</code> and
            served to enrolled agents via the authenticated download endpoint. Max size:{" "}
            {MAX_UPLOAD_MB} MB.
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
            {policyQuery.data?.policy?.updated_at ? ` | Updated: ${new Date(policyQuery.data.policy.updated_at).toLocaleString()}` : ""}
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
          <h4>Server Build Operations (advanced)</h4>
          <p>
            Triggers a PyInstaller build on this server. On a non-Windows server this produces a
            native Linux/macOS binary, <strong>not</strong> a Windows <code>.exe</code>. For
            production Windows rollout use the GitHub Actions workflow above and then upload here.
          </p>
          {buildStatusQuery.data?.build?.runtime_platform &&
          buildStatusQuery.data.build.runtime_platform !== "windows" ? (
            <div
              className="error-text"
              style={{
                background: "#fef3c7",
                color: "#78350f",
                padding: "8px 12px",
                borderRadius: 6,
                marginBottom: 8,
              }}
            >
              ⚠ This server runs <strong>{buildStatusQuery.data.build.runtime_platform}</strong>.
              The <em>Build Agent Binary</em> button will produce a{" "}
              <code>{buildStatusQuery.data.build.artifact_kind || "native_binary"}</code> artifact —
              not a deployable Windows <code>.exe</code>.
            </div>
          ) : null}
          <div className="row-between" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
            <button
              onClick={() => buildMutation.mutate()}
              disabled={buildMutation.isPending || !canManagePolicy}
              title={!canManagePolicy ? `Missing permission: ${PERMISSIONS.TENANT_MANAGE}` : undefined}
            >
              {buildMutation.isPending
                ? "Building..."
                : buildStatusQuery.data?.build?.runtime_platform === "windows"
                ? "Build Windows .exe"
                : "Build Native Binary (non-Windows)"}
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
            <small>
              Runtime: {buildStatusQuery.data?.build?.runtime_platform || "unknown"} | Artifact:{" "}
              {buildStatusQuery.data?.build?.artifact_kind || "native_binary"}
              {buildStatusQuery.data?.build?.binary_name
                ? ` | File: ${buildStatusQuery.data.build.binary_name}`
                : ""}
            </small>
            {buildStatusQuery.data?.build?.guidance ? (
              <small style={{ display: "block" }}>{buildStatusQuery.data.build.guidance}</small>
            ) : null}
            {buildMutation.data?.build?.guidance ? (
              <small style={{ display: "block" }}>
                Last build: {buildMutation.data.build.guidance}
              </small>
            ) : null}
            {!canManagePolicy ? <small>Build operation requires {PERMISSIONS.TENANT_MANAGE}.</small> : null}
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
                <th>Link</th>
              </tr>
            </thead>
            <tbody>
              {(releasesQuery.data?.releases || []).map((release) => (
                <tr key={release.filename}>
                  <td>{release.version}</td>
                  <td>{release.filename}</td>
                  <td>{(release.size_bytes / (1024 * 1024)).toFixed(2)} MB</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => handleDownloadRelease(release.filename)}
                      disabled={!release.filename}
                    >
                      Download EXE
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => handleCopyReleaseUrl(release.download_url)}
                      disabled={!release.download_url}
                    >
                      Copy URL
                    </button>
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
