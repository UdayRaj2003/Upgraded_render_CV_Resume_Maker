"""Shared prompt preamble for all AI stages."""

OUTPUT_CONTRACT = """=== OUTPUT CONTRACT ===
Return ONLY the requested format.
Never explain.
Never apologize.
Never use markdown fences.
Never output JSON unless requested.
Never output tagged text unless requested.
Never invent extra keys.
Unknown values must be empty.
=======================
"""
