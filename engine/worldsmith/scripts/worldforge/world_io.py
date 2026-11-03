"""Save and load finished worlds, so every stage works on the same planet.

A world is fully determined by its seed and parameters only until someone edits
it. After a coastal sculpt or a feature-editor change, the world is the seed
PLUS its edits, and anything that regenerates from the seed alone (the Saga
adapter, a later render) silently works on the unedited planet. Saving the
finished arrays, or replaying the edit manifest, closes that gap.

    from world_io import save_world, load_world
    save_world(editor.world, "world-bible/maps/world.npz", edits="edits.json")
    world = load_world("world-bible/maps/world.npz")

The file is a plain NumPy .npz: one array per layer plus a JSON header holding
the generator parameters, the terrain fingerprint and provenance. No pickles,
so loading a file someone else made cannot run code.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from world_fingerprint import baseline_fingerprint  # noqa: E402

SCHEMA = "worldsmith-world/v1"


def _params_kinds():
    import spherical as sp
    import worldforge_core as wf
    return {"SphereParams": sp.SphereParams, "WorldParams": wf.WorldParams}


def save_world(world: dict, path, *, edits=None, note=None):
    """Write every array layer plus parameters and provenance to `path` (.npz).

    `edits` is the edit-manifest path the world came from, if any; it is
    recorded so the bible can point at both the seed and the edits.
    """
    params = world.get("params")
    kinds = {v: k for k, v in _params_kinds().items()}
    if params is None or type(params) not in kinds:
        raise ValueError("world has no SphereParams/WorldParams; cannot save it reproducibly")
    arrays = {k: np.asarray(v) for k, v in world.items()
              if isinstance(v, np.ndarray)}
    header = {
        "schema": SCHEMA,
        "params_type": kinds[type(params)],
        "params": asdict(params),
        "sea_level": float(world["sea_level"]),
        "fingerprint": baseline_fingerprint(world),
        "edits": str(edits) if edits else None,
        "note": note,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, __header__=np.array(json.dumps(header)), **arrays)
    return path


def load_world(path) -> dict:
    """Read a world written by save_world. Verifies the terrain fingerprint."""
    with np.load(path, allow_pickle=False) as z:
        header = json.loads(str(z["__header__"]))
        if header.get("schema") != SCHEMA:
            raise ValueError(f"{path}: not a {SCHEMA} file")
        world = {k: z[k] for k in z.files if k != "__header__"}
    cls = _params_kinds()[header["params_type"]]
    known = {f.name for f in fields(cls)}
    world["params"] = cls(**{k: v for k, v in header["params"].items() if k in known})
    world["sea_level"] = header["sea_level"]
    if baseline_fingerprint(world) != header["fingerprint"]:
        raise ValueError(f"{path}: terrain fingerprint mismatch; the file is damaged or was altered")
    world["provenance"] = {k: header[k] for k in ("fingerprint", "edits", "note")}
    return world


# ------------------------------------------------------------ Atlas Studio

def atlas_bundle(world, path, *, editor=None, features=(), title=None, scale=3):
    """One JSON file Atlas Studio (editor/index.html) can open directly.

    It is an ordinary feature-editor manifest, so `WorldEditor.from_json` and
    `wf_adapter.py --edits` read it unchanged, plus display-only fields the
    browser uses: `background` (the map drawn at exactly grid x scale pixels,
    so feature coordinates line up), `projection` ("equirectangular" for
    planets, used for lat/lon in geography.md entries), `title`, and `world`
    (generator parameters, so the planet can be regenerated to replay edits).

    Pass `editor` to carry its features and full edit history. The background
    then shows the editor's current, edited world, while the manifest still
    replays from the untouched baseline that the fingerprint names.
    """
    import base64
    import io
    from PIL import Image
    import cartography as ct
    import spherical as sp
    from feature_editor import WorldEditor

    manifest = (editor if editor is not None else WorldEditor(world, list(features))).manifest()
    shown = editor.world if editor is not None else world
    rgb = ct.base_surface(shown)
    rgb = ct.contours(rgb, shown)
    rgb, _ = ct.lakes(rgb, shown)
    rgb = ct.graded_rivers(rgb, shown)
    rgb = ct.coastline(rgb, shown)
    h, w = shown["sea"].shape
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((w * scale, h * scale), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    params = shown["params"]
    kinds = {v: k for k, v in _params_kinds().items()}
    manifest.update({
        "title": title or f"Seed {params.seed}",
        "projection": "equirectangular" if sp.is_planet(shown) else "flat",
        "world": {"params_type": kinds[type(params)], "params": asdict(params)},
        "background": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
    })
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def regenerate(bundle_world):
    """Rebuild the world named by a bundle's `world` block (seed + parameters)."""
    import spherical as sp
    import worldforge_core as wf
    cls = _params_kinds()[bundle_world["params_type"]]
    known = {f.name for f in fields(cls)}
    p = cls(**{k: v for k, v in bundle_world["params"].items() if k in known})
    return sp.generate_sphere(p) if cls is sp.SphereParams else wf.generate(p)
