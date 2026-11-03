#!/usr/bin/env python3
"""
saga_sim.py: deterministic history simulator for /saga.

History first, story second. This engine knows nothing about plot. It moves
factions through turns on a region graph, logs every event WITH ITS CAUSES,
keeps the true history separate from what each side's chroniclers recorded,
then scores events for story potential ("seams").

Files: the input is saga_world.json (named so it never collides with worldforge's
world.json); outputs are chronicle.json, timeline.md, seams.md, seams.json.

Subcommands
    template                       print a starter saga_world.json
    simulate WORLD --out DIR       run history, write chronicle.json + timeline.md
    seams CHRONICLE [--top N]      rank story seeds, write seams.md
    branch WORLD --override ID=OUTCOME --base CHRONICLE --out DIR
                                   re-run with one outcome changed, write a diff
    trace CHRONICLE EVENT_ID       print the cause chain behind and consequences after an event
    fit WORLD --target T.json      search seeds for a history that ARRIVES at your canon present

Determinism: every turn draws from default_rng([seed, turn]); all iteration is
over sorted ids. Same world + seed + turns = same history, forever. A branch is
identical to its base up to the overridden event, then diverges for real
reasons, not because the dice changed.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

# ------------------------------------------------------------------ constants

SUCCESSION_RISK = {          # base chance a ruler's death becomes a crisis
    "primogeniture": 0.15, "elective": 0.35, "tanistry": 0.45,
    "appointment": 0.25, "council": 0.10, "divine": 0.30, "none": 0.6,
    # aliases matching the worldbuilder politics reference vocabulary
    "ultimogeniture": 0.18, "agnatic": 0.2, "predecessor": 0.25, "trial": 0.4,
}
SCHEMA_VERSION = 1
OUTCOMES = {
    "war": ["attacker_wins", "defender_wins", "stalemate"],
    "succession": ["smooth", "contested_heir_wins", "contested_claimant_wins", "split"],
    "rebellion": ["rebels_win", "rebels_crushed", "concession"],
    "schism": ["schism_spreads", "schism_suppressed"],
    "alliance": ["alliance_holds", "alliance_betrayed"],
    "union": ["union_accepted", "union_refused"],
}
IRREVERSIBILITY = {
    "collapse": 1.0, "succession": 0.8, "rebellion": 0.75, "war": 0.6,
    "schism": 0.7, "alliance": 0.4, "union": 0.65, "disaster": 0.35, "reform": 0.3,
}
SPIN = {  # how a side records an event it won / lost / was outside of
    "won": ["a righteous victory", "the restoration of rightful order",
            "a liberation", "a sign of divine favor"],
    "lost": ["a betrayal", "a usurpation", "a martyrdom",
             "a temporary setback caused by traitors"],
    "omit": ["(not recorded)"],
}

SYL = {
    "default": (["ka", "ri", "to", "ve", "ma", "sel", "dor", "an", "is", "ul", "mer", "th"],
                ["n", "s", "r", "th", "l", "x", ""]),
}


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ------------------------------------------------------------------ naming

def make_name(rng, culture_syl=None, parts=2):
    syl, ends = culture_syl or SYL["default"]
    s = "".join(syl[int(rng.integers(len(syl)))] for _ in range(parts))
    s += ends[int(rng.integers(len(ends)))]
    return s.capitalize()


def culture_syllables(world, culture):
    c = world.get("cultures", {}).get(culture, {})
    if "syllables" in c:
        return (c["syllables"], c.get("endings", [""]))
    return None


# ------------------------------------------------------------------ world model

def template():
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {"name": "Example World", "start_year": 0, "years_per_turn": 10,
                 "notes": "Edit freely. Regions, factions and cultures are the only required blocks."},
        "cultures": {
            "vael": {"syllables": ["vae", "lin", "or", "sa", "rhen", "el"], "endings": ["", "n", "th"]},
            "kor": {"syllables": ["kor", "dra", "gun", "ba", "tor", "ek"], "endings": ["", "k", "r"]},
        },
        "religions": {"the_flame": {}, "the_deep": {}},
        "regions": [
            {"id": "r1", "name": "Ashvale", "terrain": "river plain", "wealth": 0.8, "population": 0.8,
             "defensibility": 0.2, "culture": "vael", "religion": "the_flame", "neighbors": ["r2", "r3"]},
            {"id": "r2", "name": "Highmarch", "terrain": "mountains", "wealth": 0.3, "population": 0.3,
             "defensibility": 0.9, "culture": "vael", "religion": "the_flame", "neighbors": ["r1", "r4"],
             "chokepoint": True},
            {"id": "r3", "name": "Saltreach", "terrain": "coast", "wealth": 0.7, "population": 0.6,
             "defensibility": 0.4, "culture": "kor", "religion": "the_deep", "neighbors": ["r1", "r4"]},
            {"id": "r4", "name": "Dun Kor", "terrain": "steppe", "wealth": 0.4, "population": 0.5,
             "defensibility": 0.3, "culture": "kor", "religion": "the_deep", "neighbors": ["r2", "r3"]},
        ],
        "factions": [
            {"id": "f1", "name": "Throne of Ashvale", "culture": "vael", "religion": "the_flame",
             "succession": "primogeniture", "regions": ["r1", "r2"], "legitimacy": 0.7,
             "cohesion": 0.6, "militarism": 0.4, "treasury": 0.5},
            {"id": "f2", "name": "Kor Hordes", "culture": "kor", "religion": "the_deep",
             "succession": "tanistry", "regions": ["r3", "r4"], "legitimacy": 0.5,
             "cohesion": 0.5, "militarism": 0.8, "treasury": 0.3,
             "grievances": {"f1": 0.5}},
        ],
        "secrets": [
            {"id": "s1", "about": "f1", "text": "The founding king was a Kor exile.", "potency": 0.7}
        ],
    }


def init_state(world, seed):
    rng = np.random.default_rng([seed, 0])
    regions = {r["id"]: {
        "id": r["id"], "name": r["name"], "terrain": r.get("terrain", "land"),
        "wealth": float(r.get("wealth", 0.5)), "population": float(r.get("population", 0.5)),
        "defensibility": float(r.get("defensibility", 0.4)), "culture": r.get("culture"),
        "religion": r.get("religion"), "neighbors": sorted(r.get("neighbors", [])),
        "chokepoint": bool(r.get("chokepoint", False)), "owner": None, "unrest": 0.1,
        "conquered_turn": None,
    } for r in world["regions"]}
    # make neighbor graph symmetric
    for rid, r in list(regions.items()):
        for n in r["neighbors"]:
            if n in regions and rid not in regions[n]["neighbors"]:
                regions[n]["neighbors"] = sorted(regions[n]["neighbors"] + [rid])
    factions = {}
    for f in world["factions"]:
        syl = culture_syllables(world, f.get("culture"))
        ruler = f.get("ruler") or {"name": make_name(rng, syl), "age": int(rng.integers(25, 55))}
        ruler.setdefault("heirs", int(f.get("heirs", rng.integers(0, 4))))
        factions[f["id"]] = {
            "id": f["id"], "name": f["name"], "culture": f.get("culture"),
            "religion": f.get("religion"), "succession": f.get("succession", "primogeniture"),
            "legitimacy": float(f.get("legitimacy", 0.6)), "cohesion": float(f.get("cohesion", 0.6)),
            "militarism": float(f.get("militarism", 0.5)), "treasury": float(f.get("treasury", 0.5)),
            "grievances": {k: float(v) for k, v in f.get("grievances", {}).items()},
            "allies": sorted(f.get("allies", [])), "claims": sorted(f.get("claims", [])),
            "ruler": ruler, "alive": True, "founded_turn": 0, "parent": f.get("parent"),
            "dynasty": f.get("dynasty", ruler["name"]),
        }
        for rid in f.get("regions", []):
            regions[rid]["owner"] = f["id"]
    return {"turn": 0, "regions": regions, "factions": factions,
            "secrets": copy.deepcopy(world.get("secrets", [])),
            "next_faction": len(factions) + 1, "next_religion": 1}


# ------------------------------------------------------------------ derived quantities

def owned(state, fid):
    return sorted(r for r, v in state["regions"].items() if v["owner"] == fid)


def strength(state, fid):
    f = state["factions"][fid]
    regs = owned(state, fid)
    if not regs:
        return 0.0
    base = sum(state["regions"][r]["population"] * 0.6 + state["regions"][r]["wealth"] * 0.4 for r in regs)
    return base * (0.4 + 0.6 * f["cohesion"]) * (0.6 + 0.4 * f["militarism"]) * (0.7 + 0.3 * f["treasury"]) \
        * (0.8 + 0.2 * f["legitimacy"])


def neighbors_of(state, fid):
    out = set()
    for r in owned(state, fid):
        for n in state["regions"][r]["neighbors"]:
            o = state["regions"][n]["owner"]
            if o and o != fid and state["factions"][o]["alive"]:
                out.add(o)
    return sorted(out)


def border_regions(state, a, b):
    """Regions owned by b that touch a."""
    out = set()
    for r in owned(state, a):
        for n in state["regions"][r]["neighbors"]:
            if state["regions"][n]["owner"] == b:
                out.add(n)
    return sorted(out)


def gauges(f):
    return {k: round(f[k], 3) for k in ("legitimacy", "cohesion", "militarism", "treasury")} | {
        "max_grievance": round(max(f["grievances"].values(), default=0.0), 3)}


def snapshot(state):
    return {
        "turn": state["turn"],
        "ownership": {r: v["owner"] for r, v in sorted(state["regions"].items())},
        "religion": {r: v["religion"] for r, v in sorted(state["regions"].items())},
        "unrest": {r: round(v["unrest"], 3) for r, v in sorted(state["regions"].items())},
        "factions": {fid: {"name": f["name"], "alive": f["alive"], "ruler": f["ruler"]["name"],
                           "dynasty": f["dynasty"], "regions": owned(state, fid),
                           "strength": round(strength(state, fid), 3), **gauges(f)}
                     for fid, f in sorted(state["factions"].items()) if f["alive"] or owned(state, fid)},
    }


# ------------------------------------------------------------------ the simulator

class Sim:
    def __init__(self, world, seed, overrides=None):
        self.world = world
        self.seed = seed
        self.ypt = int(world.get("meta", {}).get("years_per_turn", 10))
        self.y0 = int(world.get("meta", {}).get("start_year", 0))
        self.state = init_state(world, seed)
        self.events = []
        self.snapshots = [snapshot(self.state)]
        self.overrides = overrides or {}
        self.last_event = defaultdict(list)   # faction id -> recent event ids (cause linking)
        self.region_last = defaultdict(list)  # region id -> recent event ids
        self.reigns = defaultdict(list)       # faction id -> base names of rulers crowned
        for fid, f in sorted(self.state["factions"].items()):
            self.reigns[fid].append(f["ruler"]["name"].split(" ")[0])

    # -- rulers ----------------------------------------------------------
    ROMAN = ["", "", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"]

    def regnal(self, fid, base):
        """Display name with a regnal number if the dynasty reused the name."""
        n = self.reigns[fid].count(base) + 1
        return base + (self.ROMAN[n] if n < len(self.ROMAN) else f" {n}")

    def crown(self, fid, display, age, heirs):
        self.state["factions"][fid]["ruler"] = {"name": display, "age": age, "heirs": heirs}
        self.reigns[fid].append(display.split(" ")[0])

    # -- logging ---------------------------------------------------------
    def year(self):
        return self.y0 + self.state["turn"] * self.ypt

    def log(self, etype, factions, regions, truth, outcome, accounts=None, causes=None,
            contest=0.5, extra=None, suppressed=False):
        eid = f"T{self.state['turn']}-{self._n}"
        self._n += 1
        f_ids = sorted(set(factions))
        cause_ids = set(causes or [])
        for fid in f_ids:
            cause_ids.update(self.last_event[fid][-1:])
        for rid in regions:
            cause_ids.update(self.region_last[rid][-1:])
        ev = {
            "id": eid, "turn": self.state["turn"], "year": self.year(), "type": etype,
            "factions": f_ids, "faction_names": [self.state["factions"][f]["name"] for f in f_ids],
            "regions": sorted(regions), "outcome": outcome, "truth": truth,
            "accounts": accounts or {}, "suppressed": suppressed,
            "causes": sorted(c for c in cause_ids if c != eid),
            "gauges": {f: gauges(self.state["factions"][f]) for f in f_ids},
            "contest": round(contest, 3), "overridden": eid in self.overrides,
        }
        if ev["overridden"]:
            ev["natural_outcome"] = getattr(self, "_natural", None)
        if extra:
            ev.update(extra)
        self.events.append(ev)
        for fid in f_ids:
            self.last_event[fid].append(eid)
        for rid in regions:
            self.region_last[rid].append(eid)
        return ev

    def pick_outcome(self, etype, natural):
        """Peek the id this event is about to get; honor a branch override."""
        eid = f"T{self.state['turn']}-{self._n}"
        forced = self.overrides.get(eid)
        self._natural = natural
        if forced:
            if forced not in OUTCOMES.get(etype, []):
                sys.exit(f"override {eid}={forced} invalid for {etype}; options: {OUTCOMES.get(etype)}")
            return forced
        return natural

    def accounts_for(self, rng, winners, losers, distort=0.5):
        acc = {}
        for f in winners:
            acc[f] = SPIN["won"][int(rng.integers(len(SPIN["won"])))]
        for f in losers:
            acc[f] = SPIN["lost"][int(rng.integers(len(SPIN["lost"])))] if rng.random() < 0.6 + 0.4 * distort \
                else SPIN["omit"][0]
        return acc

    def name(self, fid):
        return self.state["factions"][fid]["name"]

    # -- run -------------------------------------------------------------
    def run(self, turns):
        for _ in range(turns):
            self.state["turn"] += 1
            self._n = 1
            rng = np.random.default_rng([self.seed, self.state["turn"]])
            self.step(rng)
            self.snapshots.append(snapshot(self.state))
        return self

    def alive(self):
        return sorted(f for f, v in self.state["factions"].items() if v["alive"] and owned(self.state, f))

    def step(self, rng):
        S = self.state
        # 1. slow drift: unrest, treasury, grievance decay, aging
        for rid, r in sorted(S["regions"].items()):
            if not r["owner"]:
                continue
            f = S["factions"][r["owner"]]
            foreign = (r["culture"] != f["culture"]) * 0.10 + (r["religion"] != f["religion"]) * 0.08
            recent = 0.10 if r["conquered_turn"] and S["turn"] - r["conquered_turn"] <= 2 else 0.0
            r["unrest"] = clamp(r["unrest"] * 0.8 + foreign + recent + 0.08 * (1 - f["legitimacy"])
                                - 0.05 * f["cohesion"] + rng.normal(0, 0.03))
        for fid in self.alive():
            f = S["factions"][fid]
            regs = owned(S, fid)
            income = sum(S["regions"][r]["wealth"] for r in regs) / max(1, len(regs))
            f["treasury"] = clamp(f["treasury"] * 0.85 + 0.15 * income + rng.normal(0, 0.02))
            avg_unrest = np.mean([S["regions"][r]["unrest"] for r in regs])
            f["cohesion"] = clamp(f["cohesion"] + 0.06 * (0.55 - f["cohesion"]) + 0.03 * (f["legitimacy"] - 0.5)
                                  - 0.06 * (avg_unrest - 0.3)
                                  - 0.005 * max(0, len(regs) - 6))
            f["grievances"] = {k: round(v * 0.9, 4) for k, v in sorted(f["grievances"].items()) if v * 0.9 > 0.02}
            f["ruler"]["age"] += self.ypt

        # 2. events, faction by faction in id order
        for fid in self.alive():
            if not S["factions"][fid]["alive"]:
                continue
            self.maybe_succession(rng, fid)
            self.maybe_war(rng, fid)
            self.maybe_alliance(rng, fid)
            self.maybe_schism(rng, fid)
            self.maybe_reform(rng, fid)
            self.maybe_union(rng, fid)
        self.maybe_rebellions(rng)
        for _ in range(max(1, len(S["regions"]) // 30)):
            self.maybe_disaster(rng)
        self.maybe_secrets(rng)
        for fid in self.alive():
            self.maybe_collapse(rng, fid)

    # -- event generators -----------------------------------------------
    def maybe_succession(self, rng, fid):
        S = self.state
        f = S["factions"][fid]
        age = f["ruler"]["age"]
        p_death = clamp(0.04 + max(0, age - 40) * 0.02 + 0.04 * (f["militarism"] > 0.7))
        if rng.random() >= p_death * self.ypt / 10:
            return
        old = f["ruler"]["name"]
        heirs = f["ruler"].get("heirs", 0)
        claimants = [c for c in self.alive() if fid in S["factions"][c]["claims"]]
        risk = SUCCESSION_RISK.get(f["succession"], 0.3) + 0.15 * (1 - f["legitimacy"]) \
            + 0.15 * (heirs == 0) + 0.1 * len(claimants) + 0.05 * (heirs >= 3)
        syl = culture_syllables(self.world, f["culture"])
        heir_name = self.regnal(fid, make_name(rng, syl))
        rival_name = self.regnal(fid, make_name(rng, syl))
        if rng.random() >= clamp(risk):
            natural = "smooth"
        else:
            # who wins a contested succession: the heir if legitimacy holds
            p_heir = clamp(0.35 + 0.5 * f["legitimacy"] - 0.15 * len(claimants))
            r = rng.random()
            natural = "contested_heir_wins" if r < p_heir else (
                "split" if r > 1 - 0.35 * (1 - f["cohesion"]) else "contested_claimant_wins")
        outcome = self.pick_outcome("succession", natural)
        contest = 0.2 if outcome == "smooth" else 0.85
        extra = {"ruler_died": old, "ruler_age": age}
        if outcome == "smooth":
            self.crown(fid, heir_name, int(rng.integers(18, 40)), int(rng.integers(0, 4)))
            f["legitimacy"] = clamp(f["legitimacy"] - 0.02)
            truth = f"{old} of {f['name']} died at {age}; {heir_name} succeeded without dispute."
            self.log("succession", [fid], [], truth, outcome, {fid: "an orderly succession"},
                     contest=contest, extra=extra)
            return
        backer = claimants[int(rng.integers(len(claimants)))] if claimants else None
        involved = [fid] + ([backer] if backer else [])
        if outcome == "contested_heir_wins":
            self.crown(fid, heir_name, int(rng.integers(16, 35)), 0)
            f["legitimacy"] = clamp(f["legitimacy"] - 0.08)
            f["cohesion"] = clamp(f["cohesion"] - 0.12)
            truth = (f"{old} died at {age}. {rival_name} contested the throne"
                     + (f" with backing from {self.name(backer)}" if backer else "")
                     + f"; {heir_name} prevailed after bloodshed.")
            acc = {fid: "the defeat of a pretender"}
        elif outcome == "contested_claimant_wins":
            self.crown(fid, rival_name, int(rng.integers(25, 50)), int(rng.integers(0, 3)))
            f["dynasty"] = rival_name
            f["legitimacy"] = clamp(f["legitimacy"] - 0.22)
            f["cohesion"] = clamp(f["cohesion"] - 0.15)
            if backer:
                S["factions"][backer]["claims"] = [c for c in S["factions"][backer]["claims"] if c != fid]
                f["allies"] = sorted(set(f["allies"]) | {backer})
            truth = (f"{old} died at {age}. The heir {heir_name} was displaced by {rival_name}"
                     + (f", installed with {self.name(backer)}'s support" if backer else "")
                     + f". A new dynasty, {rival_name}, holds {f['name']}. {heir_name}'s fate is unrecorded.")
            acc = {fid: "the throne passed to the worthier claimant",
                   "loyalists": "a usurpation; the true heir lives"}
        else:  # split
            regs = owned(S, fid)
            if len(regs) < 2:
                outcome = "contested_heir_wins"
                f["cohesion"] = clamp(f["cohesion"] - 0.2)
                self.crown(fid, heir_name, int(rng.integers(16, 35)), 0)
                truth = (f"{old} died at {age}; a civil war between {heir_name} and {rival_name} wrecked "
                         f"{f['name']} but did not divide it. {heir_name} held the throne.")
                acc = {fid: "the suppression of rebels"}
            else:
                half = regs[len(regs) // 2:]
                nid = self.new_faction(rng, fid, half, f"{S['regions'][half[0]]['name']} under {rival_name}",
                                       ruler=rival_name)
                involved.append(nid)
                truth = (f"{old} died at {age}. The realm split: {heir_name} kept "
                         f"{', '.join(S['regions'][x]['name'] for x in regs[:len(regs)//2])}; "
                         f"{rival_name} took {', '.join(S['regions'][x]['name'] for x in half)} "
                         f"as {S['factions'][nid]['name']}.")
                acc = {fid: "rebellion by a pretender", nid: "the rightful line endures in us"}
                self.crown(fid, heir_name, int(rng.integers(16, 35)), 0)
                f["cohesion"] = clamp(f["cohesion"] - 0.1)
                f["grievances"][nid] = 0.9
                S["factions"][nid]["grievances"][fid] = 0.9
                S["factions"][nid]["claims"] = [fid]
        self.log("succession", involved, owned(S, fid), truth, outcome, acc,
                 contest=contest, extra=extra | {"heir": heir_name, "rival": rival_name})

    def maybe_war(self, rng, fid):
        S = self.state
        f = S["factions"][fid]
        nbs = neighbors_of(S, fid)
        if not nbs:
            return
        scores = []
        for n in nbs:
            if n in f["allies"]:
                continue
            ratio = strength(S, fid) / (strength(S, n) + 1e-6)
            g = f["grievances"].get(n, 0.0) + 0.4 * (n in f["claims"])
            p = 0.03 + 0.25 * f["militarism"] * (0.3 + g) * clamp(ratio, 0.3, 2.0) / 2 + 0.05 * f["treasury"]
            scores.append((p, n, ratio))
        if not scores:
            return
        p, target, ratio = max(scores)
        if rng.random() >= clamp(p) * self.ypt / 10:
            return
        T = S["factions"][target]
        fronts = border_regions(S, fid, target)
        if not fronts:
            return
        front = fronts[int(rng.integers(len(fronts)))]
        defense = S["regions"][front]["defensibility"]
        allies_t = [a for a in T["allies"] if a in self.alive() and a != fid]
        sa = strength(S, fid)
        sd = strength(S, target) * (1 + 0.6 * defense) + 0.5 * sum(strength(S, a) for a in allies_t)
        share = sa / (sa + sd + 1e-9)
        r = rng.random()
        natural = "attacker_wins" if r < share * 0.85 else ("stalemate" if r < share * 0.85 + 0.25 else "defender_wins")
        outcome = self.pick_outcome("war", natural)
        contest = 1 - abs(share - 0.5) * 2
        rname = S["regions"][front]["name"]
        for x in (fid, target):
            S["factions"][x]["treasury"] = clamp(S["factions"][x]["treasury"] - 0.15)
        if outcome == "attacker_wins":
            taken = [front] + ([n for n in fronts if n != front][:1] if share > 0.65 else [])
            for rid in taken:
                S["regions"][rid]["owner"] = fid
                S["regions"][rid]["conquered_turn"] = S["turn"]
                S["regions"][rid]["unrest"] = clamp(S["regions"][rid]["unrest"] + 0.3)
            f["legitimacy"] = clamp(f["legitimacy"] + 0.06)
            T["legitimacy"] = clamp(T["legitimacy"] - 0.12)
            T["grievances"][fid] = clamp(T["grievances"].get(fid, 0) + 0.6)
            f["grievances"].pop(target, None)
            names = ", ".join(S["regions"][x]["name"] for x in taken)
            truth = f"{f['name']} invaded {T['name']} through {rname} and seized {names}."
            acc = self.accounts_for(rng, [fid], [target])
            regs = taken
        elif outcome == "defender_wins":
            f["legitimacy"] = clamp(f["legitimacy"] - 0.1)
            f["cohesion"] = clamp(f["cohesion"] - 0.08)
            T["legitimacy"] = clamp(T["legitimacy"] + 0.08)
            f["grievances"][target] = clamp(f["grievances"].get(target, 0) + 0.3)
            truth = f"{f['name']} attacked {T['name']} at {rname} and was thrown back."
            acc = self.accounts_for(rng, [target], [fid])
            regs = [front]
        else:
            for x in (fid, target):
                S["factions"][x]["cohesion"] = clamp(S["factions"][x]["cohesion"] - 0.05)
            f["grievances"][target] = clamp(f["grievances"].get(target, 0) + 0.15)
            T["grievances"][fid] = clamp(T["grievances"].get(fid, 0) + 0.25)
            truth = f"War between {f['name']} and {T['name']} over {rname} ended in exhaustion, nothing gained."
            acc = {fid: "a punitive campaign that taught the enemy respect",
                   target: "the invader broken on our walls"}
            regs = [front]
        self.log("war", [fid, target] + allies_t, regs, truth, outcome, acc, contest=contest,
                 extra={"attacker": fid, "defender": target, "front": front,
                        "attacker_share": round(share, 3)})

    def maybe_alliance(self, rng, fid):
        S = self.state
        f = S["factions"][fid]
        enemies = {k for k, v in f["grievances"].items() if v > 0.4}
        if not enemies:
            return
        for cand in self.alive():
            if cand == fid or cand in f["allies"] or cand in enemies:
                continue
            c = S["factions"][cand]
            shared = enemies & {k for k, v in c["grievances"].items() if v > 0.3}
            if not shared or rng.random() >= 0.25:
                continue
            enemy = sorted(shared)[0]
            marriage = rng.random() < 0.5
            natural = "alliance_holds" if rng.random() < 0.75 else "alliance_betrayed"
            outcome = self.pick_outcome("alliance", natural)
            if outcome == "alliance_holds":
                f["allies"] = sorted(set(f["allies"]) | {cand})
                c["allies"] = sorted(set(c["allies"]) | {fid})
                if marriage:  # a marriage plants a claim that can detonate later
                    f["claims"] = sorted(set(f["claims"]) | {cand})
                truth = (f"{f['name']} and {c['name']} allied against {self.name(enemy)}"
                         + (f", sealed by a marriage that gives {f['name']} a claim on {c['name']}'s throne." if marriage else "."))
                acc = {fid: "a union of the faithful", cand: "a union of the faithful"}
            else:
                c["grievances"][fid] = clamp(c["grievances"].get(fid, 0) + 0.5)
                f["legitimacy"] = clamp(f["legitimacy"] - 0.05)
                truth = f"{f['name']} courted {c['name']} against {self.name(enemy)}, then sold the negotiations to the enemy."
                acc = {fid: "(not recorded)", cand: "a betrayal"}
            self.log("alliance", [fid, cand], [], truth, outcome, acc, contest=0.4,
                     extra={"against": enemy, "marriage": marriage},
                     suppressed=(outcome == "alliance_betrayed" and rng.random() < 0.5))
            return

    def maybe_schism(self, rng, fid):
        S = self.state
        f = S["factions"][fid]
        regs = owned(S, fid)
        if len(regs) < 2 or f["cohesion"] > 0.45 or rng.random() >= 0.12 * (1 - f["cohesion"]):
            return
        natural = "schism_spreads" if rng.random() < 0.6 else "schism_suppressed"
        outcome = self.pick_outcome("schism", natural)
        hot = sorted(regs, key=lambda r: -S["regions"][r]["unrest"])[: max(1, len(regs) // 3)]
        newrel = f"{f['religion']}_reformed_{S['next_religion']}"
        S["next_religion"] += 1
        if outcome == "schism_spreads":
            for r in hot:
                S["regions"][r]["religion"] = newrel
                S["regions"][r]["unrest"] = clamp(S["regions"][r]["unrest"] + 0.2)
            f["cohesion"] = clamp(f["cohesion"] - 0.1)
            truth = f"A reform movement ({newrel}) took hold in {', '.join(S['regions'][r]['name'] for r in hot)}, splitting {f['name']}'s faithful."
            acc = {fid: "heresy, which the crown tolerates for now", "reformers": "an awakening"}
        else:
            for r in hot:
                S["regions"][r]["unrest"] = clamp(S["regions"][r]["unrest"] + 0.15)
            f["legitimacy"] = clamp(f["legitimacy"] - 0.05)
            truth = f"Reformers in {', '.join(S['regions'][r]['name'] for r in hot)} were purged by {f['name']}."
            acc = {fid: "the cleansing of heresy", "reformers": "the martyrdom of the faithful"}
        self.log("schism", [fid], hot, truth, outcome, acc, contest=0.6, extra={"new_religion": newrel})

    def maybe_reform(self, rng, fid):
        f = self.state["factions"][fid]
        if f["legitimacy"] > 0.65 and f["treasury"] > 0.55 and rng.random() < 0.15:
            f["cohesion"] = clamp(f["cohesion"] + 0.12)
            f["treasury"] = clamp(f["treasury"] - 0.1)
            for r in owned(self.state, fid):
                self.state["regions"][r]["unrest"] = clamp(self.state["regions"][r]["unrest"] - 0.1)
            self.log("reform", [fid], [], f"Under {f['ruler']['name']}, {f['name']} reformed its law and treasury.",
                     "reform", {fid: "a golden age"}, contest=0.1)

    def maybe_union(self, rng, fid):
        """Small states fold into strong kin. Without this, history only fragments."""
        S = self.state
        f = S["factions"][fid]
        regs = owned(S, fid)
        if len(regs) > 2 or not f["alive"]:
            return
        kin = [n for n in neighbors_of(S, fid) if S["factions"][n]["culture"] == f["culture"]
               and strength(S, n) > 2 * strength(S, fid)]
        if not kin:
            return
        big = max(kin, key=lambda n: (strength(S, n), n))
        B = S["factions"][big]
        p = 0.1 + 0.2 * (big in f["allies"]) + 0.2 * (fid in B["claims"]) + 0.15 * (1 - f["legitimacy"])
        if rng.random() >= p:
            return
        natural = "union_accepted" if rng.random() < 0.6 + 0.3 * B["legitimacy"] - 0.3 * f["grievances"].get(big, 0) \
            else "union_refused"
        outcome = self.pick_outcome("union", natural)
        if outcome == "union_accepted":
            for r in regs:
                S["regions"][r]["owner"] = big
            f["alive"] = False
            B["legitimacy"] = clamp(B["legitimacy"] + 0.05)
            B["cohesion"] = clamp(B["cohesion"] - 0.03)
            truth = f"{f['name']} was absorbed into {B['name']} by treaty under {B['ruler']['name']}."
            acc = {big: "the reunion of a divided people", fid: "(the archive was carried off to the capital)"}
        else:
            f["grievances"][big] = clamp(f["grievances"].get(big, 0) + 0.4)
            B["grievances"][fid] = clamp(B["grievances"].get(fid, 0) + 0.3)
            truth = f"{B['name']} demanded the submission of {f['name']}, and was refused."
            acc = {big: "an ungrateful refusal", fid: "our freedom defended"}
        self.log("union", [fid, big], regs, truth, outcome, acc, contest=0.55)

    def maybe_rebellions(self, rng):
        S = self.state
        for rid, r in sorted(S["regions"].items()):
            if not r["owner"] or r["unrest"] < 0.6 or rng.random() >= 0.8 * (r["unrest"] - 0.5):
                continue
            fid = r["owner"]
            f = S["factions"][fid]
            kin = [n for n in self.alive() if n != fid and S["factions"][n]["culture"] == r["culture"]
                   and any(S["regions"][x]["owner"] == n for x in r["neighbors"])]
            p_win = clamp(0.25 + 0.4 * r["unrest"] - 0.3 * f["cohesion"] + 0.2 * bool(kin))
            x = rng.random()
            natural = "rebels_win" if x < p_win else ("concession" if x < p_win + 0.2 else "rebels_crushed")
            outcome = self.pick_outcome("rebellion", natural)
            involved = [fid]
            if outcome == "rebels_win":
                if kin:
                    r["owner"] = kin[0]
                    involved.append(kin[0])
                    truth = f"{r['name']} rose against {f['name']} and went over to its kin in {self.name(kin[0])}."
                    acc = {fid: "treason incited from abroad", kin[0]: "our people came home"}
                else:
                    nid = self.new_faction(rng, fid, [rid], f"Free {r['name']}")
                    involved.append(nid)
                    truth = f"{r['name']} threw off {f['name']} and declared itself free."
                    acc = {fid: "a bandit uprising", nid: "the day of liberation"}
                r["unrest"] = 0.15
                f["legitimacy"] = clamp(f["legitimacy"] - 0.1)
            elif outcome == "concession":
                r["unrest"] = clamp(r["unrest"] - 0.3)
                f["legitimacy"] = clamp(f["legitimacy"] - 0.04)
                truth = f"{r['name']} revolted; {f['name']} bought peace with charters and tax relief."
                acc = {fid: "the crown's mercy", "locals": "rights won in blood"}
            else:
                r["unrest"] = clamp(r["unrest"] - 0.2)
                r["population"] = clamp(r["population"] - 0.12)
                truth = f"{f['name']} crushed a rising in {r['name']}; the reprisals emptied villages."
                acc = {fid: "order restored", "locals": "(remembered only in songs)"}
            self.log("rebellion", involved, [rid], truth, outcome, acc, contest=0.5 + 0.4 * (p_win - 0.5),
                     suppressed=(outcome == "rebels_crushed" and rng.random() < 0.4))

    def maybe_disaster(self, rng):
        S = self.state
        if rng.random() >= 0.25:
            return
        rid = sorted(S["regions"])[int(rng.integers(len(S["regions"])))]
        r = S["regions"][rid]
        kind = ["famine", "plague", "flood", "earthquake"][int(rng.integers(4))]
        spread = [rid] + (r["neighbors"][:2] if kind == "plague" else [])
        for x in spread:
            S["regions"][x]["population"] = clamp(S["regions"][x]["population"] - 0.15)
            S["regions"][x]["unrest"] = clamp(S["regions"][x]["unrest"] + 0.2)
            S["regions"][x]["wealth"] = clamp(S["regions"][x]["wealth"] - 0.08)
        owners = sorted({S["regions"][x]["owner"] for x in spread if S["regions"][x]["owner"]})
        truth = f"{kind.capitalize()} struck {', '.join(S['regions'][x]['name'] for x in spread)}."
        acc = {o: ("a trial sent to test the faithful" if S["factions"][o]["religion"] else "a hard year")
               for o in owners}
        self.log("disaster", owners, spread, truth, kind, acc, contest=0.0, extra={"kind": kind})

    def maybe_secrets(self, rng):
        """Secrets from the world file can surface; exposure is a story engine."""
        S = self.state
        for s in S["secrets"]:
            if s.get("exposed") or s.get("about") not in S["factions"]:
                continue
            f = S["factions"][s["about"]]
            if not f["alive"]:
                continue
            # Weight by how much enemies hate you, not how many grudges exist: a
            # dozen trivial border grievances must not make exposure near-certain.
            p = 0.04 + 0.1 * (1 - f["cohesion"]) + 0.08 * min(1.0, sum(f["grievances"].values()))
            if rng.random() < p:
                s["exposed"] = S["turn"]
                f["legitimacy"] = clamp(f["legitimacy"] - 0.25 * s.get("potency", 0.5))
                f["cohesion"] = clamp(f["cohesion"] - 0.1 * s.get("potency", 0.5))
                self.log("revelation", [s["about"]], [], f"Exposed: {s['text']}", "exposed",
                         {s["about"]: "slander by enemies"}, contest=0.7,
                         extra={"secret": s["id"]})

    def maybe_collapse(self, rng, fid):
        S = self.state
        f = S["factions"][fid]
        regs = owned(S, fid)
        if not regs:
            if f["alive"]:
                f["alive"] = False
                self.log("collapse", [fid], [], f"{f['name']} ceased to exist, its last lands lost.", "extinct",
                         {fid: "(no chroniclers remained)"}, contest=0.0)
            return
        if f["cohesion"] >= 0.12 or len(regs) < 2:
            return
        by_cult = defaultdict(list)
        for r in regs:
            by_cult[S["regions"][r]["culture"]].append(r)
        pieces = sorted(by_cult.values(), key=len, reverse=True)
        if len(pieces) == 1:
            pieces = [regs[: len(regs) // 2 or 1], regs[len(regs) // 2 or 1:]]
        kept = pieces[0]
        new = []
        for p in pieces[1:]:
            if p:
                new.append(self.new_faction(rng, fid, p, f"{S['regions'][p[0]]['name']} Successor"))
        f["cohesion"] = 0.35
        f["legitimacy"] = clamp(f["legitimacy"] - 0.1)
        truth = f"{f['name']} fragmented; it holds only {', '.join(S['regions'][r]['name'] for r in kept)}."
        acc = {fid: "the shedding of disloyal provinces"} | {n: "independence" for n in new}
        self.log("collapse", [fid] + new, regs, truth, "fragmented", acc, contest=0.3)

    def new_faction(self, rng, parent, regions, name, ruler=None):
        S = self.state
        P = S["factions"][parent]
        nid = f"f{S['next_faction']}"
        S["next_faction"] += 1
        cult = S["regions"][regions[0]]["culture"]
        rel = S["regions"][regions[0]]["religion"]
        syl = culture_syllables(self.world, cult)
        rn = ruler or make_name(rng, syl)
        S["factions"][nid] = {
            "id": nid, "name": name, "culture": cult, "religion": rel, "succession": P["succession"],
            "legitimacy": 0.4, "cohesion": 0.55, "militarism": P["militarism"], "treasury": 0.3,
            "grievances": {parent: 0.6}, "allies": [], "claims": [],
            "ruler": {"name": rn, "age": int(rng.integers(25, 50)), "heirs": int(rng.integers(0, 3))},
            "alive": True, "founded_turn": S["turn"], "parent": parent, "dynasty": rn,
        }
        for r in regions:
            S["regions"][r]["owner"] = nid
            S["regions"][r]["unrest"] = clamp(S["regions"][r]["unrest"] - 0.2)
        P["grievances"][nid] = 0.7
        self.reigns[nid].append(rn.split(" ")[0])
        return nid


# ------------------------------------------------------------------ outputs

def consequences(events):
    out = defaultdict(list)
    for e in events:
        for c in e["causes"]:
            out[c].append(e["id"])
    return out


def score_seams(chron):
    events = chron["events"]
    cons = consequences(events)
    nreg = max(1, len(chron["snapshots"][0]["ownership"]))

    def downstream(eid, depth=3):
        seen, frontier = set(), [eid]
        for _ in range(depth):
            frontier = [c for f in frontier for c in cons.get(f, []) if c not in seen]
            seen.update(frontier)
        return seen

    seams = []
    for e in events:
        if e["type"] in ("reform",):
            continue
        stakes = clamp((len(e["regions"]) / nreg) * 2 + 0.15 * len(e["factions"]))
        acc_vals = [v for v in e["accounts"].values()]
        distinct = len(set(acc_vals))
        ambiguity = clamp(0.2 * distinct + 0.4 * e["suppressed"] + 0.2 * ("(not recorded)" in acc_vals))
        ds = downstream(e["id"])
        cascade = clamp(len(ds) / max(4, 0.15 * len(events)))
        irr = IRREVERSIBILITY.get(e["type"], 0.3)
        if e["type"] == "succession" and e["outcome"] == "smooth":
            irr = 0.1
        score = 0.25 * e["contest"] + 0.2 * stakes + 0.2 * ambiguity + 0.2 * cascade + 0.15 * irr
        seams.append({"id": e["id"], "year": e["year"], "type": e["type"], "score": round(score, 3),
                      "contest": e["contest"], "stakes": round(stakes, 3), "ambiguity": round(ambiguity, 3),
                      "cascade": round(cascade, 3), "irreversibility": irr,
                      "truth": e["truth"], "accounts": {chron["faction_names"].get(k, k): v for k, v in e["accounts"].items()},
                      "factions": e["faction_names"],
                      "downstream": sorted(ds, key=lambda x: (int(x[1:].split('-')[0]), int(x.split('-')[1]))),
                      "branch_options": OUTCOMES.get(e["type"], [])})
    seams.sort(key=lambda s: -s["score"])
    # diversify: each repeat of a type in the ranking costs a little, so the top
    # list offers different kinds of story, not five successions in a row
    seen, ranked = defaultdict(int), []
    pool = seams[:]
    while pool:
        best = max(pool, key=lambda s: s["score"] - 0.06 * seen[s["type"]])
        pool.remove(best)
        seen[best["type"]] += 1
        ranked.append(best)
    return ranked


def write_timeline(chron, path):
    lines = [f"# Chronicle: {chron['world']}", "",
             f"Seed {chron['seed']} · {chron['turns']} turns of {chron['years_per_turn']} years", ""]
    by_turn = defaultdict(list)
    for e in chron["events"]:
        by_turn[e["turn"]].append(e)
    for t in sorted(by_turn):
        snap = chron["snapshots"][t]
        lines.append(f"## Year {by_turn[t][0]['year']}")
        for e in by_turn[t]:
            flag = " *(suppressed: no public record)*" if e["suppressed"] else ""
            lines.append(f"- **{e['id']}** [{e['type']}] {e['truth']}{flag}")
            for k, v in e["accounts"].items():
                who = chron["faction_names"].get(k, k)
                lines.append(f"  - *{who} records:* {v}")
        alive = [f"{v['name']} ({len(v['regions'])})" for v in snap["factions"].values() if v["alive"] and v["regions"]]
        lines.append(f"  - *Powers:* {', '.join(alive)}")
        lines.append("")
    open(path, "w").write("\n".join(lines))


def write_seams(seams, path, top):
    lines = ["# Story seams", "", "Ranked by contest, stakes, gap between truth and record, "
             "downstream consequences, and irreversibility.", ""]
    for i, s in enumerate(seams[:top], 1):
        lines += [f"## {i}. {s['id']} · year {s['year']} · {s['type']} · score {s['score']}",
                  f"**What happened:** {s['truth']}", "",
                  f"**Who:** {', '.join(s['factions'])}",
                  f"**Contest** {s['contest']} · **Stakes** {s['stakes']} · **Ambiguity** {s['ambiguity']} "
                  f"· **Cascade** {s['cascade']} ({len(s['downstream'])} later events)", ""]
        if s["accounts"]:
            lines.append("**The records disagree:** " + "; ".join(f"{k}: {v}" for k, v in s["accounts"].items()))
        if s["branch_options"]:
            lines.append(f"**Branchable outcomes:** {', '.join(s['branch_options'])}")
        lines.append("")
    open(path, "w").write("\n".join(lines))


def simulate(world, seed, turns, overrides=None):
    sim = Sim(world, seed, overrides).run(turns)
    unknown = sorted({f.get("succession") for f in world["factions"]
                      if f.get("succession") and f.get("succession") not in SUCCESSION_RISK})
    if unknown:
        print(f"warning: unknown succession law(s) {unknown}; treated as risk 0.3. "
              f"Known: {sorted(SUCCESSION_RISK)}", file=sys.stderr)
    return {
        "schema_version": SCHEMA_VERSION,
        "world": world.get("meta", {}).get("name", "world"), "seed": seed, "turns": turns,
        "years_per_turn": sim.ypt, "start_year": sim.y0, "overrides": overrides or {},
        "faction_names": {k: v["name"] for k, v in sorted(sim.state["factions"].items())},
        "region_names": {k: v["name"] for k, v in sorted(sim.state["regions"].items())},
        "events": sim.events, "snapshots": sim.snapshots,
        "final_secrets": sim.state["secrets"],
    }


def diff_chronicles(base, branch):
    be, ce = base["events"], branch["events"]
    first = None
    for a, b in zip(be, ce):
        if a["id"] != b["id"] or a["truth"] != b["truth"] or a["outcome"] != b["outcome"]:
            first = b["id"]
            break
    end_a, end_b = base["snapshots"][-1], branch["snapshots"][-1]
    owner_changes = {r: {"base": base["faction_names"].get(end_a["ownership"][r], end_a["ownership"][r]),
                         "branch": branch["faction_names"].get(end_b["ownership"][r], end_b["ownership"][r])}
                     for r in end_a["ownership"] if end_a["ownership"][r] != end_b["ownership"].get(r)}
    alive_a = {v["name"] for v in end_a["factions"].values() if v["alive"] and v["regions"]}
    alive_b = {v["name"] for v in end_b["factions"].values() if v["alive"] and v["regions"]}
    return {"first_divergence": first, "regions_changed_hands": owner_changes,
            "powers_only_in_base": sorted(alive_a - alive_b), "powers_only_in_branch": sorted(alive_b - alive_a),
            "base_events": len(be), "branch_events": len(ce)}


def fit_score(chron, target):
    """Fraction of canon constraints a simulated history satisfies."""
    end = chron["snapshots"][-1]
    hits, total = 0, 0
    for rid, fid in target.get("ownership", {}).items():
        total += 1
        hits += end["ownership"].get(rid) == fid
    alive = {f for f, v in end["factions"].items() if v["alive"] and v["regions"]}
    for f in target.get("alive", []):
        total += 1
        hits += f in alive
    for f in target.get("dead", []):
        total += 1
        hits += f not in alive
    for req in target.get("require_events", []):
        total += 1
        hits += any(e["type"] == req.get("type") and
                    (not req.get("outcome") or e["outcome"] == req["outcome"]) and
                    (not req.get("faction") or req["faction"] in e["factions"]) for e in chron["events"])
    for req in target.get("forbid_events", []):
        total += 1
        hits += not any(e["type"] == req.get("type") and
                        (not req.get("outcome") or e["outcome"] == req["outcome"]) and
                        (not req.get("faction") or req["faction"] in e["factions"]) for e in chron["events"])
    return hits / max(1, total)


# ------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template")
    s = sub.add_parser("simulate")
    s.add_argument("world"); s.add_argument("--seed", type=int, default=1); s.add_argument("--turns", type=int, default=30)
    s.add_argument("--out", default="saga_out"); s.add_argument("--top", type=int, default=10)
    q = sub.add_parser("seams")
    q.add_argument("chronicle"); q.add_argument("--top", type=int, default=10); q.add_argument("--out")
    b = sub.add_parser("branch")
    b.add_argument("world"); b.add_argument("--base", required=True)
    b.add_argument("--override", action="append", required=True, help="EVENT_ID=OUTCOME, repeatable")
    b.add_argument("--turns", type=int); b.add_argument("--out", default="saga_branch")
    fi = sub.add_parser("fit")
    fi.add_argument("world"); fi.add_argument("--target", required=True)
    fi.add_argument("--seeds", type=int, default=200); fi.add_argument("--turns", type=int, default=30)
    fi.add_argument("--start", type=int, default=1)
    t = sub.add_parser("trace")
    t.add_argument("chronicle"); t.add_argument("event")
    a = ap.parse_args()

    if a.cmd == "template":
        print(json.dumps(template(), indent=2)); return
    if a.cmd == "simulate":
        world = json.load(open(a.world))
        chron = simulate(world, a.seed, a.turns)
        os.makedirs(a.out, exist_ok=True)
        json.dump(chron, open(os.path.join(a.out, "chronicle.json"), "w"), indent=1)
        write_timeline(chron, os.path.join(a.out, "timeline.md"))
        seams = score_seams(chron)
        write_seams(seams, os.path.join(a.out, "seams.md"), a.top)
        json.dump(seams, open(os.path.join(a.out, "seams.json"), "w"), indent=1)
        end = chron["snapshots"][-1]
        alive = [v["name"] for v in end["factions"].values() if v["alive"] and v["regions"]]
        print(json.dumps({"events": len(chron["events"]), "final_powers": alive,
                          "top_seams": [(s["id"], s["type"], s["score"]) for s in seams[:5]],
                          "out": a.out}, indent=1))
    elif a.cmd == "seams":
        chron = json.load(open(a.chronicle))
        seams = score_seams(chron)
        out = a.out or os.path.join(os.path.dirname(a.chronicle) or ".", "seams.md")
        write_seams(seams, out, a.top)
        print(json.dumps([(s["id"], s["type"], s["score"], s["truth"]) for s in seams[:a.top]], indent=1))
    elif a.cmd == "branch":
        world = json.load(open(a.world))
        base = json.load(open(a.base))
        ov = dict(o.split("=", 1) for o in a.override)
        chron = simulate(world, base["seed"], a.turns or base["turns"], ov)
        missing = [k for k in ov if not any(e["id"] == k and e["overridden"] for e in chron["events"])]
        if missing:
            sys.exit(f"override target(s) never occurred in the branch: {missing}. "
                     "Branch on an event id from the base chronicle.")
        same = [e["id"] for e in chron["events"] if e["overridden"] and e.get("natural_outcome") == e["outcome"]]
        if same:
            sys.exit(f"{same}: that outcome is what already happened. Pick a different one.")
        os.makedirs(a.out, exist_ok=True)
        json.dump(chron, open(os.path.join(a.out, "chronicle.json"), "w"), indent=1)
        write_timeline(chron, os.path.join(a.out, "timeline.md"))
        d = diff_chronicles(base, chron)
        json.dump(d, open(os.path.join(a.out, "diff.json"), "w"), indent=1)
        print(json.dumps(d, indent=1))
    elif a.cmd == "fit":
        world = json.load(open(a.world))
        target = json.load(open(a.target))
        res = []
        for sd in range(a.start, a.start + a.seeds):
            res.append((round(fit_score(simulate(world, sd, a.turns), target), 3), sd))
        res.sort(key=lambda x: (-x[0], x[1]))
        print(json.dumps({"best": [{"seed": sd, "fit": sc} for sc, sd in res[:10]],
                          "note": "simulate the best seed with the same --turns to get its chronicle"}, indent=1))
    elif a.cmd == "trace":
        chron = json.load(open(a.chronicle))
        idx = {e["id"]: e for e in chron["events"]}
        if a.event not in idx:
            sys.exit(f"no event {a.event}")
        cons = consequences(chron["events"])

        def up(eid, d=0, seen=None):
            seen = seen if seen is not None else set()
            if eid in seen or d > 4:
                return
            seen.add(eid)
            e = idx[eid]
            print("  " * d + f"{'<-' if d else '*'} {eid} ({e['year']}) {e['truth']}")
            for c in e["causes"]:
                up(c, d + 1, seen)
        print("CAUSES"); up(a.event)
        print("\nCONSEQUENCES")
        frontier, seen = [a.event], {a.event}
        for depth in range(1, 4):
            nxt = []
            for f in frontier:
                for c in cons.get(f, []):
                    if c not in seen:
                        seen.add(c)
                        nxt.append(c)
                        print(f"  [{depth}] {c} ({idx[c]['year']}) via {f}: {idx[c]['truth']}")
            frontier = nxt


if __name__ == "__main__":
    main()
