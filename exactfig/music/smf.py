"""
Standard MIDI File (SMF) without dependencies / sin dependencias: writes type 1 (a conductor track + one track per instrument)
and reads back what is needed to validate. No timestamps and no host data: the same notes always give the same bytes.

Una nota es (tick, duración, canal, nota, velocidad). Todas las pistas acaban EXACTAMENTE en el tick del bucle: así la
duración del archivo es la del bucle y un reproductor lo repite sin costura.
"""
import struct

TPB = 480


def _varlen(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def _meta(kind, data):
    return bytes([0xFF, kind]) + _varlen(len(data)) + data


def _track(events, end_tick):
    """events: (tick, orden, bytes). En el mismo tick: metas y programas, luego note off, luego note on."""
    events = sorted(events, key=lambda e: (e[0], e[1]))
    out, last = bytearray(), 0
    for tick, _, data in events:
        out += _varlen(tick - last) + data
        last = tick
    out += _varlen(max(0, end_tick - last)) + b"\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(out)) + bytes(out)


def encode(*, title, text, bpm, beats_per_bar, beat_unit, length_ticks, tracks, copyright=None) -> bytes:
    """
    tracks: lista de dicts {name, channel, program (None en el canal 10), volume, pan, notes: [(tick, dur, note, vel)]}.
    Un solo tempo y un solo compás (un bucle sin costura). `copyright`: texto opcional del meta 0x02.
    """
    us = round(60_000_000 / bpm)
    denom_pow = {2: 1, 4: 2, 8: 3}[beat_unit]
    cond = ([(0, -1, _meta(0x02, copyright.encode("latin-1", "replace")))] if copyright else []) + [
        (0, 0, _meta(0x03, title.encode("ascii", "replace"))),
        (0, 0, _meta(0x01, text.encode("ascii", "replace"))),
        (0, 1, _meta(0x58, bytes([beats_per_bar, denom_pow, 24, 8]))),
        (0, 2, _meta(0x51, us.to_bytes(3, "big"))),
    ]
    chunks = [_track(cond, length_ticks)]
    for t in tracks:
        ch = t["channel"] & 15
        ev = [(0, 0, _meta(0x03, t["name"].encode("ascii", "replace"))),
              (0, 1, bytes([0xB0 | ch, 7, max(0, min(127, t.get("volume", 100)))])),
              (0, 1, bytes([0xB0 | ch, 10, max(0, min(127, t.get("pan", 64)))]))]
        if t.get("program") is not None:
            ev.append((0, 2, bytes([0xC0 | ch, t["program"] & 127])))
        for tick, dur, note, vel in t["notes"]:
            end = min(length_ticks, tick + max(1, dur))
            if tick >= length_ticks or end <= tick:
                continue
            ev.append((tick, 4, bytes([0x90 | ch, note & 127, max(1, min(127, vel))])))
            ev.append((end, 3, bytes([0x80 | ch, note & 127, 0])))
        chunks.append(_track(ev, length_ticks))
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), TPB) + b"".join(chunks)


def read(b: bytes) -> dict:
    """Parse Standard MIDI File bytes into what the tests check: format, tempos, time signatures, programs, notes, track
    names, texts and the end of each track. Takes bytes, never a path: reading files is the caller's job."""
    if b[:4] != b"MThd":
        raise ValueError("no es un archivo MIDI")
    fmt, ntracks, tpb = struct.unpack(">HHH", b[8:14])
    if tpb & 0x8000:
        raise ValueError("división SMPTE no soportada")
    res = {"format": fmt, "tpb": tpb, "tempos": [], "timesigs": [], "programs": {}, "notes": [], "names": [],
           "texts": [], "ends": [], "size": len(b)}
    p = 14
    for _ in range(ntracks):
        if b[p:p + 4] != b"MTrk":
            raise ValueError("pista mal formada")
        ln = struct.unpack(">I", b[p + 4:p + 8])[0]
        q, stop, tick, status, open_ = p + 8, p + 8 + ln, 0, 0, {}

        def vl():
            nonlocal q
            v = 0
            while True:
                c = b[q]; q += 1
                v = (v << 7) | (c & 0x7F)
                if not c & 0x80:
                    return v
        while q < stop:
            tick += vl()
            if b[q] & 0x80:
                status = b[q]; q += 1
            if status == 0xFF:
                kind = b[q]; q += 1
                n = vl(); data = b[q:q + n]; q += n
                if kind == 0x51: res["tempos"].append((tick, 60_000_000 / int.from_bytes(data, "big")))
                elif kind == 0x58: res["timesigs"].append((tick, data[0], 2 ** data[1]))
                elif kind == 0x03: res["names"].append(data.decode("ascii", "replace"))
                elif kind == 0x01: res["texts"].append(data.decode("ascii", "replace"))
                elif kind == 0x2F: break
            elif status in (0xF0, 0xF7):
                n = vl(); q += n
            else:
                kind, ch = status & 0xF0, status & 15
                if kind in (0x80, 0x90):
                    note, vel = b[q], b[q + 1]; q += 2
                    if kind == 0x90 and vel > 0:
                        open_[(ch, note)] = (tick, vel)
                    elif (ch, note) in open_:
                        t0, v0 = open_.pop((ch, note))
                        res["notes"].append((t0, tick - t0, ch, note, v0))
                elif kind == 0xC0:
                    res["programs"][ch] = b[q]; q += 1
                elif kind == 0xD0:
                    q += 1
                else:
                    q += 2
        res["ends"].append(tick)
        p = stop
    res["length"] = max(res["ends"]) if res["ends"] else 0
    return res
