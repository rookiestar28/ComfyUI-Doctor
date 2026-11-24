"""Scalar node identity shared by diagnostic target producers."""
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

NodeId: TypeAlias = int | str
MAX_NODE_ID_LENGTH = 1024
MAX_SAFE_INTEGER = (1 << 53) - 1


def valid_node_id(value: Any) -> NodeId | None:
    """Keep the original scalar; do not turn opaque or leading-zero IDs into numbers."""
    if type(value) is int:
        return value if 0 <= value <= MAX_SAFE_INTEGER else None
    if isinstance(value, str) and 0 < len(value) <= MAX_NODE_ID_LENGTH:
        if value.strip() != value or any(
            ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
            for char in value
        ):
            return None
        return value
    return None


def safe_execution_id_component(value: Any) -> str:
    """Keep provenance identifiers content-free and bounded."""
    value = valid_node_id(value)
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            return value
        # IMPORTANT: opaque IDs must not collapse to "unknown" or become path components.
        # The ~ namespace cannot collide with legacy safe IDs; source_node keeps the raw mapping.
        return "sha256~" + hashlib.sha256(value.encode("utf-8")).hexdigest()
    return "unknown"


IdentityState: TypeAlias = Literal["valid", "malformed", "duplicate"]


@dataclass(frozen=True)
class NodeIdentity:
    """One node of a serialized workflow list together with what its identity can safely be used for.

    ``node_id`` is set only when the id is valid AND unique in the list, so it is the only value a
    finding may use as a Locate/fix target. ``discriminator`` is empty for such nodes (their issue ids
    stay exactly as they were) and ``pos~<position>`` otherwise, so two corrupt nodes with otherwise
    identical findings still get distinct, deterministic issue ids.
    """

    node: dict[str, Any]
    position: int
    node_id: NodeId | None
    state: IdentityState
    discriminator: str
    label: str

    @property
    def actionable(self) -> bool:
        return self.node_id is not None


def resolve_node_identities(nodes: Any) -> list[NodeIdentity]:
    """Classify every dict entry of ``nodes`` as valid-unique, malformed or duplicate.

    IMPORTANT: a malformed or duplicate id must never select a node (Locate or fix could land on the
    wrong one) but its findings must not disappear either. The duplicate key is ``str(node_id)`` so
    ``5`` and ``"5"`` collide while ``"05"`` and ``5`` stay distinct, exactly as the workflow lint has
    always compared them. Non-dict entries are skipped but still occupy their list position. The input
    is never mutated; time and memory are linear in the list length.
    """
    if not isinstance(nodes, list):
        return []
    entries: list[tuple[int, dict[str, Any], NodeId | None]] = []
    occurrences: dict[str, int] = {}
    for position, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = valid_node_id(node.get("id"))
        entries.append((position, node, node_id))
        if node_id is not None:
            key = str(node_id)
            occurrences[key] = occurrences.get(key, 0) + 1

    identities: list[NodeIdentity] = []
    for position, node, node_id in entries:
        if node_id is None:
            state: IdentityState = "malformed"
        elif occurrences[str(node_id)] > 1:
            state = "duplicate"
        else:
            state = "valid"
        actionable_id = node_id if state == "valid" else None
        identities.append(NodeIdentity(
            node=node,
            position=position,
            node_id=actionable_id,
            state=state,
            discriminator="" if state == "valid" else f"pos~{position}",
            label=(
                f"#{actionable_id}"
                if state == "valid"
                else f"unidentified node at nodes[{position}]"
            ),
        ))
    return identities


def with_discriminator(content_hash: str, identity: NodeIdentity) -> str:
    """Append the identity discriminator to an issue-id content string (unchanged for actionable nodes)."""
    return f"{content_hash}:{identity.discriminator}" if identity.discriminator else content_hash
