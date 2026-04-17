import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ModulePage } from "../../components/common/ModulePage";
import { ActionPanel } from "../../components/common/ActionPanel";
import { JsonViewer } from "../../components/common/JsonViewer";
import { MutationFeedback } from "../../components/common/MutationFeedback";
import { createIncidentComment, getIncident, getIncidentComments, getIncidents, updateIncident } from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import type { IncidentCaseComment, IncidentDetailResponse, IncidentRecordSummary, IncidentsResponse } from "../../types/api";

const INCIDENT_STATUSES = ["open", "acknowledged", "resolved"] as const;

type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export function IncidentsPage() {
  const queryClient = useQueryClient();
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [status, setStatus] = useState<IncidentStatus>("open");
  const [assignedUserId, setAssignedUserId] = useState<string>("");
  const [commentBody, setCommentBody] = useState("");
  const [feedback, setFeedback] = useState("");

  const incidentsQuery = useQuery<IncidentsResponse>({
    queryKey: queryKeys.incidents,
    queryFn: () => getIncidents(),
    staleTime: 60_000,
  });

  const incidentQuery = useQuery<IncidentDetailResponse>({
    queryKey: selectedIncidentId != null ? queryKeys.incident(selectedIncidentId) : ["incidents", "current", "none"],
    queryFn: () => getIncident(selectedIncidentId as number),
    enabled: selectedIncidentId != null,
    staleTime: 60_000,
  });

  const commentsQuery = useQuery<{ comments: IncidentCaseComment[] }>({
    queryKey: selectedIncidentId != null ? queryKeys.incidentComments(selectedIncidentId) : ["incidents", "none", "comments"],
    queryFn: () => getIncidentComments(selectedIncidentId as number),
    enabled: selectedIncidentId != null,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (incidentQuery.data?.incident) {
      const incomingStatus = incidentQuery.data.incident.status as IncidentStatus;
      setStatus(INCIDENT_STATUSES.includes(incomingStatus) ? incomingStatus : "open");
      setAssignedUserId(String(incidentQuery.data.incident.assigned_to_user_id ?? ""));
    }
  }, [incidentQuery.data]);

  const updateIncidentMutation = useMutation({
    mutationFn: () =>
      updateIncident(selectedIncidentId as number, {
        status: status || undefined,
        assigned_to_user_id: assignedUserId.trim() ? Number(assignedUserId.trim()) : null,
      }),
    onSuccess: () => {
      setFeedback("Incident updated successfully.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.incidents });
      if (selectedIncidentId != null) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.incident(selectedIncidentId) });
      }
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      setFeedback(`Error updating incident: ${String(err)}`);
    },
  });

  const createCommentMutation = useMutation({
    mutationFn: () =>
      createIncidentComment(selectedIncidentId as number, {
        body: commentBody,
        comment_type: "note",
      }),
    onSuccess: () => {
      setFeedback("Comment saved.");
      setCommentBody("");
      if (selectedIncidentId != null) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.incidentComments(selectedIncidentId) });
      }
      setTimeout(() => setFeedback(""), 4000);
    },
    onError: (err) => {
      setFeedback(`Error saving comment: ${String(err)}`);
    },
  });

  const refreshIncidents = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.incidents });
    if (selectedIncidentId != null) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.incident(selectedIncidentId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.incidentComments(selectedIncidentId) });
    }
  };

  const resetIncidentView = () => {
    setSelectedIncidentId(null);
    setStatus("open");
    setAssignedUserId("");
    setCommentBody("");
    setFeedback("");
  };

  const incidents = Array.isArray(incidentsQuery.data?.incidents) ? incidentsQuery.data.incidents : ([] as IncidentRecordSummary[]);
  const selectedIncident = incidentQuery.data?.incident;
  const comments = Array.isArray(commentsQuery.data?.comments) ? commentsQuery.data.comments : ([] as IncidentCaseComment[]);
  const isPending = updateIncidentMutation.isPending || createCommentMutation.isPending;

  const selectedIncidentClass = (incident: IncidentRecordSummary) =>
    selectedIncidentId === incident.id ? "selected-row" : undefined;

  return (
    <ModulePage
      title="Incidents"
      description="Investigate incident summaries, update status, and collaborate via case comments."
      isLoading={incidentsQuery.isLoading}
      error={incidentsQuery.isError ? "Could not load incident list." : ""}
      actions={
        <div className="module-page-actions-group">
          <button type="button" onClick={refreshIncidents} disabled={incidentsQuery.isFetching}>
            Refresh incidents
          </button>
          <button type="button" onClick={resetIncidentView}>
            Reset incident view
          </button>
        </div>
      }
    >
      <div className="module-grid">
        <ActionPanel title="Incident List">
          {incidents.length ? (
            <table className="table-lite">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident: IncidentRecordSummary) => (
                  <tr
                    key={incident.id}
                    className={selectedIncidentClass(incident)}
                    onClick={() => setSelectedIncidentId(incident.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{incident.id}</td>
                    <td>{incident.title}</td>
                    <td>{incident.severity}</td>
                    <td>{incident.status}</td>
                    <td>{incident.last_seen_at ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="module-status loading">No incidents found.</div>
          )}
        </ActionPanel>

        <ActionPanel title="Incident Details">
          {selectedIncidentId == null ? (
            <div className="module-status loading">Select an incident to inspect its details.</div>
          ) : incidentQuery.isLoading ? (
            <div className="module-status loading">Loading incident details...</div>
          ) : incidentQuery.error ? (
            <div className="module-status error-text">Failed to load incident details.</div>
          ) : selectedIncident ? (
            <>
              <div className="form-field">
                <label className="form-label">Status</label>
                <select className="form-input" value={status} onChange={(e) => setStatus(e.target.value as IncidentStatus)}>
                  {INCIDENT_STATUSES.map((candidate) => (
                    <option key={candidate} value={candidate}>
                      {candidate}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label className="form-label">Assigned User ID</label>
                <input
                  className="form-input"
                  type="number"
                  value={assignedUserId}
                  onChange={(e) => setAssignedUserId(e.target.value)}
                  placeholder="User ID"
                />
              </div>
              <button className="button button--primary" type="button" onClick={() => updateIncidentMutation.mutate()} disabled={isPending}>
                {updateIncidentMutation.isPending ? "Updating..." : "Save incident"}
              </button>
              <MutationFeedback error={updateIncidentMutation.error} />
              <JsonViewer data={selectedIncident} title="Selected incident payload" maxHeight={280} />
            </>
          ) : null}
        </ActionPanel>
      </div>

      <div className="module-grid" style={{ marginTop: 16 }}>
        <ActionPanel title="Case Comments">
          {selectedIncidentId == null ? (
            <div className="module-status loading">Select an incident to view or add comments.</div>
          ) : commentsQuery.isLoading ? (
            <div className="module-status loading">Loading comments...</div>
          ) : commentsQuery.error ? (
            <div className="module-status error-text">Failed to load comments.</div>
          ) : (
            <>
              {comments.length ? (
                <div className="comment-list">
                  {comments.map((comment: IncidentCaseComment) => (
                    <div key={comment.id} className="comment-item">
                      <div className="comment-meta">
                        <strong>{comment.comment_type}</strong> · {comment.created_at ?? "unknown"}
                      </div>
                      <div>{comment.body}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="module-status loading">No comments have been created for this incident yet.</div>
              )}

              <div className="form-field" style={{ marginTop: 12 }}>
                <label className="form-label">Add comment</label>
                <textarea
                  className="form-input"
                  rows={4}
                  value={commentBody}
                  onChange={(e) => setCommentBody(e.target.value)}
                  placeholder="Add your investigation note or remediation guidance"
                />
              </div>
              <button className="button button--primary" type="button" onClick={() => createCommentMutation.mutate()} disabled={isPending || !commentBody.trim()}>
                {createCommentMutation.isPending ? "Saving..." : "Save comment"}
              </button>
              <MutationFeedback error={createCommentMutation.error} />
              {feedback ? <div className="module-status success-text" style={{ marginTop: 12 }}>{feedback}</div> : null}
            </>
          )}
        </ActionPanel>
      </div>
    </ModulePage>
  );
}
