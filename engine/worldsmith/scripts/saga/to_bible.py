#!/usr/bin/env python3
"""
to_bible.py: draft a world-bible history.md from a saga chronicle.

Output follows the worldbuilder history format (calendar, era summary, era
sections with dated key events, genealogies, active grievances, lost or
suppressed history, open questions). Everything is marked proposed: the user
canonizes, the tool does not.

Eras are cut at the chronicle's own turning points (the highest-scoring
irreversible events), not at even intervals, so each era begins with the event
that changed the world. Only events that matter go in: seams above a score
floor, every collapse and revelation, and the successions needed for the
genealogies. A bible that lists every decade fails worldbuilder's
excess-precision test.

    python to_bible.py out/chronicle.json --eras 4 --genealogies 3 --out world-bible/history.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
from saga_sim import score_seams  # noqa: E402

PROPOSED = "*(proposed — not yet confirmed)*"
TURNING = {"collapse", "succession", "war", "rebellion", "union", "revelation", "schism"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chronicle")
    ap.add_argument("--eras", type=int, default=4)
    ap.add_argument("--genealogies", type=int, default=3, help="dynasties to chart")
    ap.add_argument("--floor", type=float, default=0.5, help="minimum seam score for a key event")
    ap.add_argument("--calendar", default="years since the first recorded count")
    ap.add_argument("--out", default="history.md")
    a = ap.parse_args()

    c = json.load(open(a.chronicle))
    ev = c["events"]
    idx = {e["id"]: e for e in ev}
    seams = {s["id"]: s for s in score_seams(c)}
    names = c["faction_names"]
    y0, ypt, T = c.get("start_year", 0), c["years_per_turn"], c["turns"]

    # --- era cuts at turning points, spaced at least T/(2*eras) turns apart
    cand = sorted((s for s in seams.values() if s["type"] in TURNING and s["irreversibility"] >= 0.6),
                  key=lambda s: -s["score"])
    gap = max(1, T // (2 * a.eras))
    cuts = []
    for s in cand:
        t = idx[s["id"]]["turn"]
        if t > gap and all(abs(t - x) >= gap for x in cuts):
            cuts.append(t)
        if len(cuts) == a.eras - 1:
            break
    cuts = sorted(cuts)
    bounds = [0] + cuts + [T + 1]
    eras = [(bounds[i], bounds[i + 1] - 1) for i in range(len(bounds) - 1)]

    keep = [e for e in ev if seams.get(e["id"], {}).get("score", 0) >= a.floor
            or e["type"] in ("collapse", "revelation") or e["id"] in {idx[s["id"]]["id"] for s in cand[:a.eras]}]
    keep = [e for e in keep if not (e["type"] == "succession" and e["outcome"] == "smooth")]

    L = [f"# History {PROPOSED}", "",
         f"Drafted from saga chronicle `{os.path.basename(a.chronicle)}` "
         f"(world {c['world']}, seed {c['seed']}, {T} turns of {ypt} years). "
         "Rename eras, people and places; strike anything that is not canon.", "",
         "## Calendar & dating", f"Year 0 is {a.calendar}. Dates are approximate to the decade.", "",
         "## Era summary"]
    for i, (s, e) in enumerate(eras, 1):
        opener = next((x for x in ev if x["turn"] == s and x["type"] in TURNING), None)
        L.append(f"- **Era {i}** (yr {y0 + s * ypt} to {y0 + e * ypt}): "
                 + (f"opens with: {opener['truth']}" if opener and i > 1 else "the starting order.")
                 + " *[name and flavor this era]*")
    L.append("")

    for i, (s, e) in enumerate(eras, 1):
        L += [f"## Era {i} *[name]* (yr {y0 + s * ypt} to {y0 + e * ypt})", "### Themes & feel",
              "*[what life was like; what people thought was happening]*", "", "### Key events"]
        for x in keep:
            if s <= x["turn"] <= e:
                tag = " *(no public record)*" if x["suppressed"] else ""
                L.append(f"- yr {x['year']}: {x['truth']}{tag} `[{x['id']}]`")
        L.append("")

    # --- genealogies, worldbuilder format
    succ = defaultdict(list)
    for x in ev:
        if x["type"] == "succession":
            succ[x["factions"][0]].append(x)
    top = sorted(succ, key=lambda f: -len(succ[f]))[: a.genealogies]
    if top:
        L += ["## Genealogies", ""]
        for f in top:
            L += [f"### {names.get(f, f)}", "```"]
            depth = 0
            for x in succ[f]:
                r0 = x["ruler_died"]
                note = {"smooth": "", "contested_heir_wins": " (contested; heir held)",
                        "contested_claimant_wins": f" (deposed line; {x.get('heir')} displaced)",
                        "split": " (realm split)"}.get(x["outcome"], "")
                succ_name = x.get("rival") if x["outcome"] == "contested_claimant_wins" else (
                    x.get("heir") or x["truth"].split("; ")[-1].split(" succeeded")[0])
                L.append(("   " * depth) + ("└─ " if depth else "") + f"{r0} (d. yr {x['year']}, aged {x['ruler_age']})")
                depth = min(depth + 1, 8)
                if note:
                    L.append(("   " * depth) + f"   {note.strip()} → {succ_name}")
            L += ["```", ""]

    # --- active grievances from the final era's wars and refusals
    last = [x for x in ev if x["turn"] >= eras[-1][0] and x["type"] in ("war", "union", "rebellion", "alliance")]
    L += ["## Active grievances & memory"]
    for x in last[-8:]:
        acc = "; ".join(f"{names.get(k, k)} remembers {v}" for k, v in x["accounts"].items())
        L.append(f"- {x['truth']} {acc}. `[{x['id']}]`")
    L.append("")

    sup = [x for x in ev if x["suppressed"]]
    L += ["## Lost or suppressed history"]
    L += [f"- yr {x['year']}: {x['truth']} (no public record) `[{x['id']}]`" for x in sup] or ["- none recorded"]
    L += ["", "## Open questions",
          "- Which of these events are canon? Strike or keep each line, then promote the pivotal ones "
          "to `00-overview.md`.",
          "- What do folk memory and myth say about the eras above? The chronicle holds only truth and "
          "official records."]
    for x in [x for x in ev if x["type"] == "succession" and x["outcome"] == "contested_claimant_wins"][:3]:
        L.append(f"- What became of {x.get('heir')}, displaced in yr {x['year']}? `[{x['id']}]`")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write("\n".join(L) + "\n")
    print(json.dumps({"out": a.out, "eras": [[y0 + s * ypt, y0 + e * ypt] for s, e in eras],
                      "key_events": len(keep), "genealogies": [names.get(f, f) for f in top],
                      "suppressed": len(sup)}, indent=1))


if __name__ == "__main__":
    main()
