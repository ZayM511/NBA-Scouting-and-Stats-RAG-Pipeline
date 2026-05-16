"""Player entity normalization.

Maps every name variant ("Steph", "Curry", "the Chef", "Wardell") to a
canonical `player_id`. Builds an alias table at season start, refreshes
weekly during the regular season and daily during the playoffs.

See `.claude/skills/nba-entity-normalization.md` for the full approach.
"""
