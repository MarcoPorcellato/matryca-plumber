"""Private one-capture composition edge; never an in-process public read facade."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .bootstrap import GatewayError
from .profile import _Profile
from .wire import _snapshot_document


def _snapshot(graph_root: Path, profile: _Profile, versions: Mapping[str, str]) -> dict[str, Any]:
    """Map one immutable capture/session, never two independent source reads."""
    from src.agent import og_topology_session_composition as composition
    from src.agent.og_parser_identity_adapter import _OgSnapshotReadError

    try:
        captured = composition.create_og_topology_session_reader(graph_root)
        session = captured.session
        identity = captured.reader.identify(session_id=session.id, graph_id=session.graph_id)
        topology = captured.reader.topology_snapshot(
            session_id=session.id, graph_id=session.graph_id
        )
        return _snapshot_document(
            profile,
            versions,
            session.model_dump(mode="json"),
            identity.model_dump(mode="json"),
            topology.model_dump(mode="json"),
        )
    except _OgSnapshotReadError as error:
        raise GatewayError(error.code) from None
    except GatewayError:
        raise
    except Exception:
        raise GatewayError("internal") from None
