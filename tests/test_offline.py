"""Offline checks of the item set, the rule layer and the prompts. No model calls, no network."""
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from judgecal import prompts, rules  # noqa: E402
from judgecal.items import load, load_all  # noqa: E402

PUBLIC = ("review", "claim", "suggest", "jv", "mqm")
RULE_DIMS = {"review": {"quote", "format"}, "claim": {"figure", "quote", "foreign"}}


def qc_records():
    return [json.loads(l) for l in (ROOT / "data" / "items" / "qc.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


class ItemSet(unittest.TestCase):
    def test_public_families_present_and_ids_unique(self):
        items = load_all(PUBLIC)
        self.assertEqual(Counter(i["family"] for i in items),
                         Counter({"review": 570, "claim": 200, "suggest": 136, "jv": 200, "mqm": 240}))
        self.assertEqual(len({i["id"] for i in items}), len(items))

    def test_every_item_has_the_fields_the_scorer_reads(self):
        for i in load_all(PUBLIC):
            for k in ("id", "family", "reference", "lang", "split", "cluster", "dimension", "truth", "material"):
                self.assertIn(k, i, i["id"])
            self.assertIn(i["reference"], ("constructed", "regulator", "human"))

    def test_no_human_reference_except_published_ratings(self):
        for i in load_all(PUBLIC):
            if i["reference"] == "human":
                self.assertIn(i["family"], ("jv", "summeval", "mqm"))

    def test_image_files_exist(self):
        for i in load("review"):
            if i["material"]["image"]:
                self.assertTrue((ROOT / "data" / i["material"]["image"]).exists(), i["id"])


class RuleLayer(unittest.TestCase):
    def test_planted_rule_checkable_errors_fail_and_right_candidates_pass(self):
        for fam in ("review", "claim"):
            for i in load(fam):
                p = rules.problems(i)
                if i["truth"] == "pass":
                    self.assertEqual(p, [], i["id"])
                elif i["dimension"] in RULE_DIMS[fam]:
                    self.assertNotEqual(p, [], i["id"])
                else:
                    self.assertEqual(p, [], i["id"])   # judge-only errors are invisible to the script

    def test_qc_records(self):
        import qc as Q

        for r in qc_records():
            bad = bool(rules.review_problems(r["material"], Q.as_review(r["candidate"])))
            self.assertEqual(bad, r["dimension"] in Q.RULE_CHECKABLE, r["id"])

    def test_quote_matching_is_exact_enough(self):
        self.assertTrue(rules.found("文案：护眼效果全国第一，孩子写作业不再眼累。", "护眼效果全国第一"))
        self.assertFalse(rules.found("文案：护眼效果全国第一，孩子写作业不再眼累。", "护眼效果全国弟一"))
        self.assertFalse(rules.found("Caption: Get cash in 10 seconds.", "Get cash in 11 seconds"))


class Prompts(unittest.TestCase):
    def test_every_family_and_version_builds_a_request(self):
        items = {i["family"]: i for i in load_all(PUBLIC)}
        for fam, it in items.items():
            versions = prompts.VERSIONS if fam in prompts.BINARY else ("fixed",)
            for v in versions:
                for wording in (("r0", "r1", "r2") if fam in prompts.BINARY else ("r0",)):
                    system, content, schema = prompts.request(it, v, wording=wording)
                    self.assertTrue(system and content and schema["required"])
                    self.assertFalse(schema["additionalProperties"])

    def test_wordings_ask_the_same_criteria(self):
        for fam in prompts.BINARY:
            keys = {k for k, *_ in prompts.criteria(fam)}
            for w in ("r1", "r2"):
                self.assertEqual({k for k, *_ in prompts.criteria(fam, w)}, keys)

    def test_verdict_from_checks(self):
        ok = {"contradicts": "no", "invents": "no", "drops_confirmed": "n/a", "absence_as_false": "n/a", "actionable": "yes"}
        self.assertEqual(prompts.verdict_from_checks("suggest", ok), "pass")
        self.assertEqual(prompts.verdict_from_checks("suggest", {**ok, "invents": "yes"}), "fail")
        self.assertEqual(prompts.verdict_from_checks("suggest", {**ok, "actionable": "no"}), "fail")
        self.assertEqual(prompts.verdict_from_checks("claim", {"fact_true": "yes", "quotes_verbatim": "n/a", "requirement_met": "no"}), "fail")

    def test_swap_reverses_the_options_only(self):
        it = load("claim")[0]
        a = prompts.schema_binary("claim", "v2")
        b = prompts.schema_binary("claim", "v2", swap=True)
        self.assertEqual(a["properties"]["verdict"]["enum"], list(reversed(b["properties"]["verdict"]["enum"])))
        self.assertNotEqual(prompts.request(it, "v2")[0], prompts.request(it, "v2", swap=True)[0])

    def test_content_free_additions_keep_the_claims(self):
        for fam in prompts.BINARY:
            it = load(fam)[0]
            for how in ("verbose", "assertive"):
                c = prompts.perturb_candidate(it, how)
                key = prompts.FREE_TEXT[fam]
                self.assertTrue(c[key].startswith((it["candidate"].get(key) or "").rstrip()))
                for k in it["candidate"]:
                    if k != key:
                        self.assertEqual(c[k], it["candidate"][k])


class Scoring(unittest.TestCase):
    def test_majority(self):
        import score as S

        self.assertEqual(S.majority(["pass", "fail", "pass"]), "pass")
        self.assertEqual(S.majority([1.0, 0.5, 0.0]), 0.5)
        self.assertEqual(S.majority(["none", "major", "minor"]), "minor")

    def test_recall_pair(self):
        import score as S

        r = S.recall_pair([("pass", "pass"), ("pass", "fail"), ("fail", "fail"), ("fail", "fail")])
        self.assertEqual((r["pass_recall"]["k"], r["fail_recall"]["k"]), (1, 2))
        self.assertAlmostEqual(r["ba"], 0.75)


if __name__ == "__main__":
    unittest.main()


class StoredResults(unittest.TestCase):
    """The headline numbers are rebuilt from the stored answers, not read from summary.json."""

    @classmethod
    def setUpClass(cls):
        import score as S

        cls.S = S
        cls.items = load_all()
        cls.st = S.store("main")
        cls.summary = json.loads((ROOT / "eval" / "results" / "summary.json").read_text(encoding="utf-8"))

    def test_constructed_agreement(self):
        res, J = self.S.binary_section(self.items, self.st, "v2")
        self.assertEqual((res["pooled"]["agreement"]["k"], res["pooled"]["agreement"]["n"]), (699, 711))
        self.assertEqual(res["pooled"]["agreement"]["k"], self.summary["binary"]["pooled"]["agreement"]["k"])

    def test_combination(self):
        res, J = self.S.binary_section(self.items, self.st, "v2")
        c = self.S.combination(self.items, self.st, "v2", J)
        self.assertEqual((c["A"]["missed"]["k"], c["B"]["missed"]["k"], c["B"]["queue"]["k"]), (7, 2, 49))

    def test_adoption_rule_picks_v2(self):
        self.assertEqual(self.S.adopt(self.items)["version"], "v2")

    def test_every_test_item_has_three_judgments(self):
        test = [i for i in self.items if i["split"] == "test" and i["family"] not in ("qc",)]
        for i in test:
            ver = "v2" if i["family"] in prompts.BINARY else "fixed"
            for k in (1, 2, 3):
                self.assertIn(f"main|{i['id']}|{ver}|r{k}", self.st, i["id"])
