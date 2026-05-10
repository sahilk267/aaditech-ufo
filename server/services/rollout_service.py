"""Agent rollout service — batched, safe, rollback-capable update distribution."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from ..extensions import db
from ..models import Agent, AgentRollout, AgentRolloutBatch


class RolloutService:
    """Manages the full lifecycle of batched agent update rollouts."""

    VALID_STATUSES = {'draft', 'testing', 'rolling_out', 'completed', 'rolled_back'}
    DEFAULT_BATCH_PERCENTAGES = [25, 25, 50]

    @classmethod
    def suggest_next_version(cls, current_versions: list[str]) -> str:
        """Given list of existing versions, suggest the next patch version."""
        best = (0, 0, 0)
        for v in current_versions:
            parts = v.lstrip('v').split('.')
            try:
                major = int(parts[0]) if len(parts) > 0 else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
                if (major, minor, patch) > best:
                    best = (major, minor, patch)
            except (ValueError, IndexError):
                pass
        return f"{best[0]}.{best[1]}.{best[2] + 1}"

    @classmethod
    def create_rollout(
        cls,
        org_id: int,
        version: str,
        notes: str,
        batch_percentages: list[int] | None,
        created_by: str,
    ) -> AgentRollout:
        """Create a new rollout plan in 'draft' status."""
        percentages = batch_percentages or cls.DEFAULT_BATCH_PERCENTAGES
        if sum(percentages) != 100:
            raise ValueError("batch_percentages_must_sum_to_100")

        rollout = AgentRollout(
            organization_id=org_id,
            version=version,
            status='draft',
            total_batches=len(percentages),
            current_batch=0,
            batch_config=percentages,
            notes=notes or '',
            created_at=datetime.utcnow(),
            created_by=created_by,
        )
        db.session.add(rollout)
        db.session.flush()

        # Pre-compute agent assignments
        agents = Agent.query.filter_by(
            organization_id=org_id,
            enrollment_state='enrolled',
        ).order_by(Agent.id).all()

        all_serials = [a.serial_number for a in agents]
        total = len(all_serials)
        offset = 0

        for i, pct in enumerate(percentages):
            count = math.ceil(total * pct / 100) if i < len(percentages) - 1 else (total - offset)
            batch_serials = all_serials[offset: offset + count]
            offset += count

            batch = AgentRolloutBatch(
                rollout_id=rollout.id,
                batch_num=i + 1,
                percentage=pct,
                agent_serials=batch_serials,
                status='pending',
                agents_total=len(batch_serials),
            )
            db.session.add(batch)

        db.session.commit()
        return rollout

    @classmethod
    def mark_tested(cls, rollout_id: int, org_id: int) -> AgentRollout:
        """Mark a draft rollout as tested and ready to start."""
        rollout = cls._get_rollout(rollout_id, org_id)
        if rollout.status != 'draft':
            raise ValueError("rollout_must_be_in_draft")
        rollout.status = 'testing'
        rollout.tested_at = datetime.utcnow()
        db.session.commit()
        return rollout

    @classmethod
    def advance_batch(cls, rollout_id: int, org_id: int) -> dict[str, Any]:
        """Advance rollout to the next batch. Returns updated rollout + batch info."""
        rollout = cls._get_rollout(rollout_id, org_id)

        if rollout.status == 'draft':
            raise ValueError("rollout_not_tested_yet")
        if rollout.status not in {'testing', 'rolling_out'}:
            raise ValueError(f"cannot_advance_from_{rollout.status}")

        batches = AgentRolloutBatch.query.filter_by(rollout_id=rollout_id).order_by(AgentRolloutBatch.batch_num).all()

        # Complete the current in-progress batch if any
        current_in_progress = next((b for b in batches if b.status == 'in_progress'), None)
        if current_in_progress:
            current_in_progress.status = 'completed'
            current_in_progress.completed_at = datetime.utcnow()
            current_in_progress.agents_updated = current_in_progress.agents_total

        # Find next pending batch
        next_batch = next((b for b in batches if b.status == 'pending'), None)

        if next_batch is None:
            # All batches done
            rollout.status = 'completed'
            rollout.completed_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'completed', 'rollout': rollout.to_dict(), 'batch': None}

        # Start next batch
        next_batch.status = 'in_progress'
        next_batch.started_at = datetime.utcnow()
        rollout.status = 'rolling_out'
        rollout.current_batch = next_batch.batch_num

        if not rollout.started_at:
            rollout.started_at = datetime.utcnow()

        db.session.commit()
        return {
            'status': 'batch_started',
            'rollout': rollout.to_dict(),
            'batch': next_batch.to_dict(),
        }

    @classmethod
    def rollback(cls, rollout_id: int, org_id: int) -> AgentRollout:
        """Roll back a rollout — stops all pending/in-progress batches."""
        rollout = cls._get_rollout(rollout_id, org_id)
        if rollout.status not in {'testing', 'rolling_out', 'draft'}:
            raise ValueError(f"cannot_rollback_from_{rollout.status}")

        batches = AgentRolloutBatch.query.filter_by(rollout_id=rollout_id).all()
        for batch in batches:
            if batch.status in {'pending', 'in_progress'}:
                batch.status = 'cancelled'
                batch.completed_at = datetime.utcnow()

        rollout.status = 'rolled_back'
        rollout.completed_at = datetime.utcnow()
        db.session.commit()
        return rollout

    @classmethod
    def list_rollouts(cls, org_id: int) -> list[dict[str, Any]]:
        rollouts = AgentRollout.query.filter_by(organization_id=org_id).order_by(AgentRollout.created_at.desc()).all()
        return [r.to_dict() for r in rollouts]

    @classmethod
    def get_rollout_detail(cls, rollout_id: int, org_id: int) -> dict[str, Any]:
        rollout = cls._get_rollout(rollout_id, org_id)
        batches = AgentRolloutBatch.query.filter_by(rollout_id=rollout_id).order_by(AgentRolloutBatch.batch_num).all()
        d = rollout.to_dict()
        d['batches'] = [b.to_dict() for b in batches]
        return d

    @classmethod
    def get_rollout_version_for_agent(cls, serial_number: str, org_id: int, default_version: str | None) -> str | None:
        """Return which version an agent should be on based on active rollout batches."""
        active_rollout = AgentRollout.query.filter_by(
            organization_id=org_id,
            status='rolling_out',
        ).order_by(AgentRollout.created_at.desc()).first()

        if not active_rollout:
            return default_version

        in_progress_batch = AgentRolloutBatch.query.filter_by(
            rollout_id=active_rollout.id,
            status='in_progress',
        ).first()

        completed_batches = AgentRolloutBatch.query.filter_by(
            rollout_id=active_rollout.id,
            status='completed',
        ).all()

        # Agents in completed batches always get the new version
        completed_serials: set[str] = set()
        for b in completed_batches:
            completed_serials.update(b.agent_serials or [])

        if serial_number in completed_serials:
            return active_rollout.version

        # Agents in the current in-progress batch get the new version
        if in_progress_batch and serial_number in (in_progress_batch.agent_serials or []):
            return active_rollout.version

        return default_version

    @classmethod
    def process_agent_checkin(cls, serial_number: str, agent_version: str, org_id: int) -> dict[str, Any]:
        """
        Called every time an agent heartbeats / checks in.
        - Finds any active rolling_out rollout for this org.
        - If this agent is in the current in-progress batch AND its version
          matches the rollout target, increments agents_updated.
        - Auto-completes the batch when every agent has reported the new version.
        - Auto-completes the whole rollout if no pending batches remain.
        Returns a dict describing what happened (for logging / response).
        """
        active_rollout = AgentRollout.query.filter_by(
            organization_id=org_id,
            status='rolling_out',
        ).order_by(AgentRollout.created_at.desc()).first()

        if not active_rollout:
            return {'rollout_active': False}

        in_progress_batch = AgentRolloutBatch.query.filter_by(
            rollout_id=active_rollout.id,
            status='in_progress',
        ).first()

        if not in_progress_batch:
            return {'rollout_active': True, 'in_batch': False}

        if serial_number not in (in_progress_batch.agent_serials or []):
            return {'rollout_active': True, 'in_batch': False}

        # Count how many agents in this batch now report the rollout version
        if in_progress_batch.agents_total > 0:
            from ..models import Agent  # local import to avoid circular
            updated_count = Agent.query.filter(
                Agent.organization_id == org_id,
                Agent.serial_number.in_(in_progress_batch.agent_serials),
                Agent.agent_version == active_rollout.version,
            ).count()
            in_progress_batch.agents_updated = updated_count

            # Auto-complete batch when all agents have the new version
            if updated_count >= in_progress_batch.agents_total:
                in_progress_batch.status = 'completed'
                in_progress_batch.completed_at = datetime.utcnow()
                active_rollout.current_batch = in_progress_batch.batch_num

                # Check if any pending batches remain — if not, complete the rollout
                pending_next = AgentRolloutBatch.query.filter_by(
                    rollout_id=active_rollout.id,
                    status='pending',
                ).first()

                if pending_next is None:
                    active_rollout.status = 'completed'
                    active_rollout.completed_at = datetime.utcnow()

                db.session.commit()
                return {
                    'rollout_active': True,
                    'in_batch': True,
                    'batch_num': in_progress_batch.batch_num,
                    'batch_auto_completed': True,
                    'rollout_completed': active_rollout.status == 'completed',
                    'agents_updated': updated_count,
                    'agents_total': in_progress_batch.agents_total,
                }

        db.session.commit()
        return {
            'rollout_active': True,
            'in_batch': True,
            'batch_num': in_progress_batch.batch_num,
            'batch_auto_completed': False,
            'agents_updated': in_progress_batch.agents_updated,
            'agents_total': in_progress_batch.agents_total,
            'version_match': agent_version == active_rollout.version,
        }

    @classmethod
    def _get_rollout(cls, rollout_id: int, org_id: int) -> AgentRollout:
        rollout = AgentRollout.query.filter_by(id=rollout_id, organization_id=org_id).first()
        if not rollout:
            raise ValueError("rollout_not_found")
        return rollout
