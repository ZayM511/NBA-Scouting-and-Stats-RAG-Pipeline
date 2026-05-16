"""Hybrid retrieval: SQL filter, then vector search inside the filtered set.

Example: "Which guards shooting above 40% from three are getting praised
for off-ball movement?" Step 1: SQL pulls the player_ids matching the
stats filter. Step 2: vector search on `articles_chunks` filtered by
`player_ids && <step_1_result>`.
"""
