"""exactfig: scientific figures that check their data before they draw it, and that anyone can re-run bit for bit.

A recipe (generator, parameters, seed, pinned input files) becomes a PNG, GIF/APNG or MIDI file; the manifest records how,
and `exactfig verify` re-runs it and compares pixels, frames and bytes. See README.md and docs/ARCHITECTURE.md.
"""
__version__ = "0.15.0"
