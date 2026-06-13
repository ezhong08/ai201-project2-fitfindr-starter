"""
style_profile.py

Stores user style preferences across interactions so the second query
can use what was learned from the first — without the user re-entering
anything.

Storage approach:
    A module-level singleton ``StyleProfile`` instance holds in-memory
    state.  ``record_interaction()`` is called after every successful
    agent run and accumulates style tags, categories, sizes, and search
    history.  ``summary()`` returns a compact string suitable for
    injecting into LLM prompts so later interactions can reference past
    preferences.

    For the Gradio UI the singleton is wrapped in a ``gr.State()`` so it
    survives across button clicks within one browser session.
"""


class StyleProfile:
    """Accumulated style preferences learned from past interactions."""

    def __init__(self):
        self.style_tags: list[str] = []       # unique tags from items the user viewed
        self.categories: list[str] = []       # unique categories browsed
        self.search_history: list[str] = []   # past queries (most recent last)
        self.item_titles: list[str] = []      # titles of selected items
        self.preferred_size: str | None = None

    # ── recording ──────────────────────────────────────────────────────────

    def record_interaction(
        self,
        query: str,
        parsed: dict,
        selected_item: dict,
    ) -> None:
        """Update the profile from one successful agent interaction."""
        # Deduplicated history
        if query not in self.search_history:
            self.search_history.append(query)

        title = selected_item.get("title", "")
        if title and title not in self.item_titles:
            self.item_titles.append(title)

        for tag in selected_item.get("style_tags", []):
            if tag not in self.style_tags:
                self.style_tags.append(tag)

        cat = selected_item.get("category", "")
        if cat and cat not in self.categories:
            self.categories.append(cat)

        size = parsed.get("size")
        if size:
            self.preferred_size = size

    # ── querying ───────────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """True if no interactions have been recorded yet."""
        return (
            not self.style_tags
            and not self.categories
            and not self.search_history
        )

    def summary(self) -> str:
        """One-line summary suitable for injecting into an LLM prompt.

        Returns an empty string when no preferences have been learned yet.
        """
        parts: list[str] = []
        if self.style_tags:
            parts.append(
                f"Style preferences (from past searches): "
                f"{', '.join(self.style_tags)}"
            )
        if self.categories:
            parts.append(f"Browses: {', '.join(self.categories)}")
        if self.preferred_size:
            parts.append(f"Typical size: {self.preferred_size}")
        if self.search_history:
            parts.append(
                f"Past searches: {'; '.join(self.search_history)}"
            )
        return " | ".join(parts) if parts else ""

    def __repr__(self) -> str:
        return (
            f"StyleProfile(tags={self.style_tags}, "
            f"categories={self.categories}, "
            f"searches={len(self.search_history)})"
        )


# ── module-level singleton ──────────────────────────────────────────────────

_profile = StyleProfile()


def get_profile() -> StyleProfile:
    """Return the global (in-memory) style profile singleton."""
    return _profile


def reset_profile() -> None:
    """Reset the global profile (useful between demo runs)."""
    global _profile
    _profile = StyleProfile()
