"""
music.piece: from a recipe to Standard MIDI bytes / de una receta a los bytes de un MIDI.
"""
from __future__ import annotations

from . import composer, smf


def piece(seed, params) -> bytes:
    """Generator music.piece: compose from the chosen sequence and return the Standard MIDI File bytes."""
    if params["kind"] == "night" and composer.ENSEMBLES[params["ensemble"]][7] is None:
        raise ValueError(f"ensemble {params['ensemble']!r} has no night voicing: use kind 'day' or 'combat'")
    spec = {
        "seed": seed,
        "title": params["title"],
        "math": params["text"] or f"{params['source']} (exactfig)",
        "source": params["source"],
        "args": dict(params["args"]),
        "mode": params["mode"],
        "tonic": params["tonic"],
        "bpm": params["bpm"],
        "meter": params["meter"],
        "bars": params["bars"],
        "ensemble": params["ensemble"],
        "density": params["density"],
        "lush": params["lush"],
        "perc": params["perc"],
    }
    args, _ = composer.compose(spec, params["kind"])
    return smf.encode(copyright=params["copyright"], **args)
