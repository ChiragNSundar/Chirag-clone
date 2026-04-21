"""
Entity Resolution Service - Cross-platform identity linking.

Merges identities across platforms (WhatsApp, Discord, Gmail, Telegram, etc.)
into a unified entity graph. Recognizes that "John" on WhatsApp, "john_doe"
on Discord, and "john.doe@company.com" on Gmail are the same person.

Builds on top of the existing GraphService (NetworkX) for storage.

Usage:
    from services.entity_resolution_service import get_entity_resolution_service
    er = get_entity_resolution_service()
    er.register_identity("discord", "john_doe#1234", display_name="John Doe")
    er.register_identity("gmail", "john.doe@company.com", display_name="John Doe")
    er.link_identities("discord:john_doe#1234", "gmail:john.doe@company.com")
"""
import os
import json
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PlatformIdentity:
    """A single identity on a specific platform."""
    platform: str           # "discord", "whatsapp", "gmail", "telegram", etc.
    platform_id: str        # Platform-specific ID
    display_name: str       # Human-readable name
    metadata: Dict = field(default_factory=dict)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0


@dataclass
class UnifiedEntity:
    """A unified person/entity across all platforms."""
    entity_id: str                                    # UUID
    canonical_name: str                               # Best-guess display name
    identities: Dict[str, PlatformIdentity] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)     # "friend", "colleague", etc.
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def get_identity_keys(self) -> List[str]:
        """Get all platform:id keys for this entity."""
        return list(self.identities.keys())


class EntityResolutionService:
    """
    Cross-platform entity resolution and relationship management.

    Features:
    - Register identities from any platform
    - Link identities that belong to the same person
    - Auto-suggest merges based on name similarity
    - Query unified context across all platforms
    - Relationship tracking (who knows whom, interaction frequency)
    - Persisted to disk as JSON
    """

    SUPPORTED_PLATFORMS = {
        "discord", "telegram", "whatsapp", "gmail", "slack",
        "twitter", "linkedin", "manual",
    }

    def __init__(self):
        self.data_path = os.path.join(Config.DATA_DIR, "entity_graph.json")
        self.entities: Dict[str, UnifiedEntity] = {}
        self._identity_index: Dict[str, str] = {}  # "platform:id" -> entity_id
        self._name_index: Dict[str, Set[str]] = {}  # normalized_name -> {entity_ids}
        self._load()

        logger.info(
            "Entity resolution service initialized",
            entities=len(self.entities),
        )

    # ============= Persistence =============

    def _load(self):
        """Load entity data from disk."""
        if not os.path.exists(self.data_path):
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for eid, edata in data.get("entities", {}).items():
                identities = {}
                for key, idata in edata.get("identities", {}).items():
                    identities[key] = PlatformIdentity(**idata)

                entity = UnifiedEntity(
                    entity_id=eid,
                    canonical_name=edata.get("canonical_name", "Unknown"),
                    identities=identities,
                    tags=edata.get("tags", []),
                    notes=edata.get("notes", ""),
                    created_at=edata.get("created_at", time.time()),
                    updated_at=edata.get("updated_at", time.time()),
                )
                self.entities[eid] = entity

            self._rebuild_indices()
            logger.info(f"Loaded {len(self.entities)} entities from disk")
        except Exception as e:
            logger.error(f"Failed to load entity data: {e}")

    def _save(self):
        """Save entity data to disk."""
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            data = {"entities": {}}

            for eid, entity in self.entities.items():
                identities = {}
                for key, ident in entity.identities.items():
                    identities[key] = {
                        "platform": ident.platform,
                        "platform_id": ident.platform_id,
                        "display_name": ident.display_name,
                        "metadata": ident.metadata,
                        "first_seen": ident.first_seen,
                        "last_seen": ident.last_seen,
                        "interaction_count": ident.interaction_count,
                    }

                data["entities"][eid] = {
                    "canonical_name": entity.canonical_name,
                    "identities": identities,
                    "tags": entity.tags,
                    "notes": entity.notes,
                    "created_at": entity.created_at,
                    "updated_at": entity.updated_at,
                }

            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save entity data: {e}")

    def _rebuild_indices(self):
        """Rebuild in-memory indices from entity data."""
        self._identity_index.clear()
        self._name_index.clear()

        for eid, entity in self.entities.items():
            for key in entity.identities:
                self._identity_index[key] = eid

            norm_name = self._normalize_name(entity.canonical_name)
            if norm_name not in self._name_index:
                self._name_index[norm_name] = set()
            self._name_index[norm_name].add(eid)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a name for fuzzy matching."""
        return name.lower().strip().replace("_", " ").replace("-", " ").replace(".", " ")

    @staticmethod
    def _make_key(platform: str, platform_id: str) -> str:
        """Create a unique key for a platform identity."""
        return f"{platform}:{platform_id}"

    # ============= Core Operations =============

    def register_identity(
        self,
        platform: str,
        platform_id: str,
        display_name: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Register a new identity. If it already exists, update last_seen.

        Args:
            platform: Platform name (e.g. "discord", "gmail")
            platform_id: Platform-specific user ID
            display_name: Human-readable name

        Returns:
            entity_id of the entity this identity belongs to
        """
        key = self._make_key(platform, platform_id)

        # Already registered — update
        if key in self._identity_index:
            eid = self._identity_index[key]
            entity = self.entities[eid]
            identity = entity.identities[key]
            identity.last_seen = time.time()
            identity.interaction_count += 1
            if display_name:
                identity.display_name = display_name
            entity.updated_at = time.time()
            self._save()
            return eid

        # Check for name-based auto-link
        norm_name = self._normalize_name(display_name)
        matched_eid = None
        if norm_name in self._name_index:
            candidates = self._name_index[norm_name]
            if len(candidates) == 1:
                matched_eid = next(iter(candidates))

        identity = PlatformIdentity(
            platform=platform,
            platform_id=platform_id,
            display_name=display_name,
            metadata=metadata or {},
            interaction_count=1,
        )

        if matched_eid and matched_eid in self.entities:
            # Auto-link to existing entity with same name
            entity = self.entities[matched_eid]
            entity.identities[key] = identity
            entity.updated_at = time.time()
            self._identity_index[key] = matched_eid
            logger.info(
                "Auto-linked identity to existing entity",
                key=key,
                entity=entity.canonical_name,
            )
            self._save()
            return matched_eid
        else:
            # Create new entity
            eid = str(uuid.uuid4())[:12]
            entity = UnifiedEntity(
                entity_id=eid,
                canonical_name=display_name,
                identities={key: identity},
            )
            self.entities[eid] = entity
            self._identity_index[key] = eid

            if norm_name not in self._name_index:
                self._name_index[norm_name] = set()
            self._name_index[norm_name].add(eid)

            self._save()
            return eid

    def link_identities(self, key_a: str, key_b: str) -> Optional[str]:
        """
        Merge two identities into one entity.

        Args:
            key_a: First identity key (e.g. "discord:john#1234")
            key_b: Second identity key (e.g. "gmail:john@example.com")

        Returns:
            entity_id of the merged entity, or None if not found.
        """
        eid_a = self._identity_index.get(key_a)
        eid_b = self._identity_index.get(key_b)

        if not eid_a or not eid_b:
            logger.warning("Cannot link: one or both identities not found")
            return None

        if eid_a == eid_b:
            return eid_a  # Already linked

        # Merge B into A
        entity_a = self.entities[eid_a]
        entity_b = self.entities[eid_b]

        # Move all identities from B to A
        for key, ident in entity_b.identities.items():
            entity_a.identities[key] = ident
            self._identity_index[key] = eid_a

        # Merge tags
        entity_a.tags = list(set(entity_a.tags + entity_b.tags))

        # Merge notes
        if entity_b.notes:
            entity_a.notes = (entity_a.notes + "\n" + entity_b.notes).strip()

        entity_a.updated_at = time.time()

        # Remove entity B
        del self.entities[eid_b]

        # Update name index
        self._rebuild_indices()
        self._save()

        logger.info(
            "Linked identities",
            entity=entity_a.canonical_name,
            merged_from=entity_b.canonical_name,
        )
        return eid_a

    def record_interaction(
        self, platform: str, platform_id: str,
        display_name: Optional[str] = None,
    ) -> str:
        """
        Record an interaction with a contact (auto-registers if new).

        Returns:
            entity_id of the contact.
        """
        return self.register_identity(
            platform=platform,
            platform_id=platform_id,
            display_name=display_name or platform_id,
        )

    # ============= Queries =============

    def get_entity(self, entity_id: str) -> Optional[UnifiedEntity]:
        """Get an entity by its ID."""
        return self.entities.get(entity_id)

    def get_entity_by_identity(self, platform: str, platform_id: str) -> Optional[UnifiedEntity]:
        """Get the unified entity for a platform identity."""
        key = self._make_key(platform, platform_id)
        eid = self._identity_index.get(key)
        if eid:
            return self.entities.get(eid)
        return None

    def search_entities(self, query: str, limit: int = 10) -> List[UnifiedEntity]:
        """Search entities by name (fuzzy)."""
        query_norm = self._normalize_name(query)
        results = []

        for entity in self.entities.values():
            name_norm = self._normalize_name(entity.canonical_name)
            if query_norm in name_norm or name_norm in query_norm:
                results.append(entity)

            # Also check platform display names
            for ident in entity.identities.values():
                ident_norm = self._normalize_name(ident.display_name)
                if query_norm in ident_norm and entity not in results:
                    results.append(entity)

            if len(results) >= limit:
                break

        return results

    def get_context_for_message(self, platform: str, sender_id: str) -> str:
        """
        Get cross-platform context string for a message sender.
        Designed to be injected into LLM system prompts.

        Returns:
            A text block summarizing what we know about this person.
        """
        entity = self.get_entity_by_identity(platform, sender_id)
        if not entity:
            return ""

        lines = [f"CROSS-PLATFORM CONTEXT for {entity.canonical_name}:"]

        # List all known identities
        for key, ident in entity.identities.items():
            lines.append(
                f"  - {ident.platform}: {ident.display_name} "
                f"(interactions: {ident.interaction_count})"
            )

        if entity.tags:
            lines.append(f"  Tags: {', '.join(entity.tags)}")

        if entity.notes:
            lines.append(f"  Notes: {entity.notes[:200]}")

        return "\n".join(lines)

    def suggest_merges(self) -> List[Tuple[str, str, str]]:
        """
        Suggest potential entity merges based on name similarity.

        Returns:
            List of (entity_id_a, entity_id_b, reason) tuples.
        """
        suggestions = []
        seen_pairs = set()

        for norm_name, eids in self._name_index.items():
            if len(eids) > 1:
                eid_list = list(eids)
                for i in range(len(eid_list)):
                    for j in range(i + 1, len(eid_list)):
                        pair = tuple(sorted([eid_list[i], eid_list[j]]))
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            name_a = self.entities[eid_list[i]].canonical_name
                            name_b = self.entities[eid_list[j]].canonical_name
                            suggestions.append((
                                eid_list[i], eid_list[j],
                                f"Same normalized name: '{name_a}' / '{name_b}'"
                            ))

        return suggestions

    def get_stats(self) -> Dict:
        """Get entity resolution statistics."""
        platform_counts: Dict[str, int] = {}
        total_interactions = 0

        for entity in self.entities.values():
            for ident in entity.identities.values():
                platform_counts[ident.platform] = (
                    platform_counts.get(ident.platform, 0) + 1
                )
                total_interactions += ident.interaction_count

        return {
            "total_entities": len(self.entities),
            "total_identities": len(self._identity_index),
            "platform_breakdown": platform_counts,
            "total_interactions": total_interactions,
            "merge_suggestions": len(self.suggest_merges()),
        }


# Singleton
_entity_resolution_service = None


def get_entity_resolution_service() -> EntityResolutionService:
    """Get the singleton entity resolution service instance."""
    global _entity_resolution_service
    if _entity_resolution_service is None:
        _entity_resolution_service = EntityResolutionService()
    return _entity_resolution_service
