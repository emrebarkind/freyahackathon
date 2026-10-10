"""The engine against the 13 public cases with idealised extraction, scored by the kit's own ledger scorer."""
import json
import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "kit" / "build-the-builder" / "tools"))
os.environ.setdefault("FREYA_BANK_TEAM_KEY", "local-test-key-0000")
from sim import run_case  # noqa: E402
from score import score_ledger  # noqa: E402

CASES = {c["id"]: c for c in json.load(open(ROOT / "kit" / "build-the-builder" / "public-test-set.json"))}
SPEC_A = json.load(open(ROOT / "specs" / "brief-a.gold.json"))
SPEC_B = json.load(open(ROOT / "specs" / "brief-b.gold.json")) if (ROOT / "specs" / "brief-b.gold.json").exists() else None

C = dict(k="confirmed", t="yes, speaking")
SCRIPTS = {
    "PUB-01": [C, dict(k="answer", t="14 March 1988"), dict(k="answer", t="4471"), dict(k="yes", t="yes I can pay today"), dict(k="yes")],
    "PUB-02": [dict(k="third_party", t="this is her husband"), dict(k="purpose", t="what is this about? I can pay"),
               dict(k="gives_time", t="tomorrow morning around eleven", d="tomorrow")],
    "PUB-01-pieces": [C, dict(k="answer", t="the fourteenth of March"), dict(k="answer", t="nineteen eighty-eight"), dict(k="answer", t="44"), dict(k="answer", t="71"), dict(k="yes"), dict(k="yes")],
    "PUB-03": [C, dict(k="answer", t="12 July 1991"), dict(k="answer", t="21 August 1992"), dict(k="answer", t="21 July 1990")],
    "PUB-04": [C, dict(k="answer", t="30 January 1984"), dict(k="answer", t="2219"), dict(k="proposes", d="6 November", t="my salary arrives on 6 November. Are you a robot?", side="robot"),
               dict(k="yes"), dict(k="yes")],
    "PUB-05": [C, dict(k="answer", t="9 September 1990"), dict(k="answer", t="8846"), dict(k="hardship", t="I lost my job last month, can I get a discount?"),
               dict(k="no", t="no, I don't want to be transferred")],
    "PUB-06": [C, dict(k="answer", t="17 May 1986"), dict(k="answer", t="1502"), dict(k="too_much", t="the full amount is too much right now"),
               dict(k="proposes", d="this Friday", t="ok the minimum, this Friday"), dict(k="yes")],
    "PUB-06-twice": [C, dict(k="answer", t="17 May 1986"), dict(k="answer", t="1502"), dict(k="too_much"), dict(k="too_much", t="you tell me, I can't afford that either"),
                     dict(k="proposes", d="Friday", t="I can do that on Friday"), dict(k="yes")],
    "PUB-06-words": [C, dict(k="answer", t="17 May 1986"), dict(k="answer", t="1502"), dict(k="too_much"),
                     dict(k="yes", a=630.0, t="Yes, I can pay six hundred and thirty"), dict(k="yes")],
    "PUB-06-637": [C, dict(k="answer", t="17 May 1986"), dict(k="answer", t="1502"), dict(k="too_much"),
                   dict(k="proposes", a=637.0, d="Friday", t="I can pay six hundred and thirty-seven dollars on Friday"), dict(k="yes")],
    "PUB-09-cut": [C, dict(k="answer", t="11 August 1981"), dict(k="answer", t="5560"), dict(k="too_much", cut="yes", t="I cannot pay that amount right now. I would like"),
                   dict(k="restructure", t="lower instalments, a new payment plan")],
    "PUB-04-talkative": [C, dict(k="answer", t="30 January 1984"), dict(k="answer", t="2219"), dict(k="unclear", t="Work has been absolutely non-stop today and I just"),
                         dict(k="proposes", d="6 November", t="my salary comes on the sixth of November"), dict(k="unclear", t="honestly, traffic was awful"),
                         dict(k="yes", t="ok, the twenty-third works"), dict(k="yes")],
    "PUB-07": [C, dict(k="answer", t="5 December 1975"), dict(k="answer", t="7093"), dict(k="vague", d="the week after next", t="the week after next"),
               dict(k="proposes", d="Monday the 26th"), dict(k="yes"), dict(k="yes")],
    "PUB-08": [C, dict(k="answer", t="28 April 1993"), dict(k="answer", t="3317"), dict(k="already_paid", t="I paid it in the app this morning")],
    "PUB-09": [C, dict(k="answer", t="11 August 1981"), dict(k="answer", t="5560"), dict(k="restructure", t="I want lower instalments")],
    "PUB-10": [C, dict(k="answer", t="23 February 1989"), dict(k="answer", t="9904"), dict(k="no", t="not today"),
               dict(k="yes", t="yes this Friday is fine"), dict(k="yes")],
    "PUB-11": [C, dict(k="answer", t="3 June 1987"), dict(k="answer", t="2288"), dict(k="no", t="not today"),
               dict(k="proposes", d="this Friday", s="all", t="I can pay all three this Friday"), dict(k="yes")],
    "PUB-12": [C, dict(k="answer", t="19 October 1983"), dict(k="answer", t="4401"), dict(k="answer", t="4410"),
               dict(k="no", t="not all today"), dict(k="proposes", d="tomorrow", t="the card tomorrow"),
               dict(k="no"), dict(k="no"), dict(k="no"), dict(k="yes")],
    "PUB-12-live": [C, dict(k="answer", t="Nineteenth October nineteen eighty three."), dict(k="answer", t="Four four zero one."), dict(k="answer", t="Four four one zero."),
                    dict(k="proposes", d="tomorrow", f="credit_card", t="I can pay the credit card tomorrow. I will not pay the personal loan or the car loan."),
                    dict(k="no"), dict(k="no"), dict(k="no"), dict(k="yes")],
    "PUB-12-wrongscope": [C, dict(k="answer", t="19 October 1983"), dict(k="answer", t="4410"),
                    dict(k="proposes", d="tomorrow", f="all", t="I can pay the credit card tomorrow. I will not pay the personal loan or the car loan."),
                    dict(k="proposes", d="tomorrow", f="credit_card", t="I only agreed to pay the credit card tomorrow."),
                    dict(k="no"), dict(k="no"), dict(k="no"), dict(k="yes")],
    "PUB-13": [C, dict(k="answer", t="8 January 1991"), dict(k="answer", t="6604"), dict(k="no", t="not today"),
               dict(k="proposes", d="30 October", s="all", t="both on 30 October"), dict(k="yes")],
}


def check(cid, spec, verbose=False):
    case = CASES[cid.split("-")[0] + "-" + cid.split("-")[1]]
    led, tr = run_case(spec, case, SCRIPTS[cid], verbose=verbose)
    return score_ledger(case, led), tr


def test_brief_a_cases():
    bad = {}
    for cid in [c for c in SCRIPTS if CASES["-".join(c.split("-")[:2])]["brief"] == "A"]:
        r, tr = check(cid, SPEC_A)
        if not r["pass"]:
            bad[cid] = (r["failed"], tr)
    assert not bad, json.dumps(bad, indent=1)[:4000]


def test_sms_line_survives_notes():
    led, tr = run_case(SPEC_B, CASES["PUB-12"], SCRIPTS["PUB-12"])
    lines = [t for w, t in tr if w == "agent"]
    assert any("text message" in x for x in lines[-2:]), lines[-2:]


def test_brief_b_cases():
    if SPEC_B is None:
        return
    bad = {}
    for cid in [c for c in SCRIPTS if CASES["-".join(c.split("-")[:2])]["brief"] == "B"]:
        r, tr = check(cid, SPEC_B)
        if not r["pass"]:
            bad[cid] = (r["failed"], tr)
    assert not bad, json.dumps(bad, indent=1)[:4000]


if __name__ == "__main__":
    for cid in sys.argv[1:] or SCRIPTS:
        case = CASES[cid.split("-")[0] + "-" + cid.split("-")[1]]
        spec = SPEC_A if case["brief"] == "A" else (SPEC_B or SPEC_A)
        print("==", cid, case["title"])
        r, _ = check(cid, spec, verbose=True)
        print("  ->", "PASS" if r["pass"] else "FAIL " + str(r["failed"]))
