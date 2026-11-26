"""Unit tests for vision.py's parsing and gates. Synthetic text only: the repo
is public, so no MATHCOUNTS content goes here.

    python3 -I -m unittest discover -s scripts/mathcounts -p 'test_*.py'
"""

import tempfile
import unittest
from pathlib import Path

import vision as v


class ParseAnswers(unittest.TestCase):
    def test_rounds_continue_across_pages(self):
        pages = [
            ("answers-p1.png", "NONE"),
            ("answers-p2.png", "sprint 1: 14\n? 2: \\frac{2}{5}\nnoise line"),
            ("answers-p3.png", "? 3: 18,050\ntarget 1: 12 || 12.00\ncountdown 7: Blue || B"),
        ]
        answers, alts, source, warnings = v.assemble_answers(pages)
        self.assertEqual(answers, {"sprint-01": "14", "sprint-02": "$\\frac{2}{5}$",
                                   "sprint-03": "18,050", "target-01": "12", "countdown-07": "Blue"})
        self.assertEqual(alts, {"target-01": ["12.00"], "countdown-07": ["B"]})
        self.assertEqual(source["sprint-03"], "answers-p3.png")
        self.assertEqual(warnings, [])

    def test_answer_without_any_round_is_reported(self):
        _, _, _, warnings = v.assemble_answers([("answers-p1.png", "? 1: 5")])
        self.assertEqual(len(warnings), 1)


class ParseSolutions(unittest.TestCase):
    def test_continued_text_joins_previous_solution(self):
        pages = [
            ("solutions-p1.png", "=== sprint 1\nAdd them: $\\mathbf{3}$.\n=== ? 2\nFirst half"),
            ("solutions-p2.png", "=== continued\nsecond half, $\\mathbf{4}$.\n=== target 1\n[DIAGRAM]\nSee it."),
        ]
        sols, source, warnings = v.assemble_solutions(pages, {"target-01"})
        self.assertEqual(sols["sprint-02"], "First half second half, $\\mathbf{4}$.")
        self.assertEqual(source["sprint-02"], ["solutions-p1.png", "solutions-p2.png"])
        self.assertTrue(sols["target-01"].startswith("[DIAGRAM: figures/solution-target-01.png]"))
        self.assertEqual(warnings, [])

    def test_restarted_numbering_moves_to_next_round(self):
        pages = [("p1", "=== sprint 29\nA.\n=== ? 30\nB."), ("p2", "=== ? 1\nC.\n=== ? 2\nD.\n=== team 1\nE.")]
        sols, _, warnings = v.assemble_solutions(pages, set())
        self.assertEqual(sorted(sols), ["sprint-29", "sprint-30", "target-01", "target-02", "team-01"])
        self.assertEqual(warnings, [])

    def test_diagram_without_rectangle_warns_and_is_dropped(self):
        sols, _, warnings = v.assemble_solutions([("p1", "=== team 3\nLook [DIAGRAM] here.")], set())
        self.assertEqual(sols["team-03"], "Look here.")
        self.assertEqual(len(warnings), 1)


class Values(unittest.TestCase):
    def test_equivalent_forms_normalise_alike(self):
        same = [("$\\frac{2}{5}$", "\\mathbf{2/5}"), ("$\\frac{3}{88}$", "\\mathbf{\\dfrac{3}{88}}"),
                ("18,050", "18{,}050"), ("12", "\\$12"), ("$2\\sqrt{3}$", "2\\sqrt3"),
                ("9", "9\\text{ cm}"), ("1:30 p.m.", "1{:}30\\text{ p.m.}")]
        for a, b in same:
            self.assertEqual(v.norm_value(a), v.norm_value(b), (a, b))
        self.assertNotEqual(v.norm_value("$\\frac{2}{5}$"), v.norm_value("5/2"))

    def test_bold_values_balance_braces(self):
        self.assertEqual(v.bold_values("so $x = \\mathbf{\\frac{1}{2}}$ and $\\mathbf{7}$"),
                         ["\\frac{1}{2}", "7"])


class FinalValues(unittest.TestCase):
    def test_pre_2021_ans_layout(self):
        for sol, ans in [("so $x + y = 7 + 3 = 20$ Ans.", "20"),
                         ("$\\frac{8}{5\\pi} \\approx 0.509 \\approx 0.51$ Ans.", "0.51"),
                         ("$\\frac{1}{4} = \\mathbf{25\\%}$ Ans.", "25"),
                         ("The answer is 12 Ans.", "12"),
                         ("$$\\frac{4}{30} = \\frac{2}{15}$$ $\\textbf{Ans.}$", "$\\frac{2}{15}$"),
                         ("So $n$ must be 63. $\\textbf{Ans.}$", "63"),
                         ("So the point is (6, 4) $\\textbf{Ans.}$", "(6, 4)"),
                         ("$$0.36 + 0.09 \\approx 0.46\\ \\underline{\\textbf{Ans.}}$$", ".46")]:
            self.assertIn(v.norm_value(ans), {v.norm_value(x) for x in v.final_values(sol)}, sol)


class Overlap(unittest.TestCase):
    def test_invented_or_missing_prose_lowers_overlap(self):
        layer = "How many marbles are in the green jar after Pat adds seven more?"
        self.assertEqual(v.overlap(layer, "How many marbles are in the green jar after Pat adds $7$ more? seven"),
                         (1.0, 1.0))
        covered, _ = v.overlap(layer, "How many marbles are in the jar?")
        self.assertLess(covered, v.COVER_MIN)
        _, faithful = v.overlap(layer, layer + " Assume every marble is blue, round, small and heavy.")
        self.assertLess(faithful, v.OVERLAP_MIN)
        covered, faithful = v.overlap("Number of Families " + layer, layer)
        self.assertGreaterEqual(covered, v.COVER_MIN)  # figure labels in the layer are tolerated


class Tidy(unittest.TestCase):
    def test_quotes_and_superscripts(self):
        self.assertEqual(v.tidy("Pat\u2019s \u201cbox\u201d is 4 cm\u00b2, $x\u00b3 = 8$"),
                         "Pat's \"box\" is 4 cm$^2$, $x^3 = 8$")


class Gates(unittest.TestCase):
    def draft(self):
        return {"problems": [{"round": "sprint", "problemNumber": n,
                              "textLayer": "What is the total number of apples?"} for n in (1, 2)]}

    def reading(self, **over):
        r = {"content": {"sprint-01": "What is the total number of apples?",
                         "sprint-02": "What is the total number of apples?"},
             "answers": {"sprint-01": "4", "sprint-02": "$\\frac{1}{2}$"},
             "alternatives": {},
             "solutions": {"sprint-01": "$\\mathbf{4}$", "sprint-02": "$\\mathbf{1/2}$"}}
        r.update(over)
        return r

    def test_clean_reading_passes(self):
        self.assertEqual(v.gate(self.reading(), self.draft(), {"sprint": 2}, True, {}), {})

    def test_failures_and_overrides(self):
        r = self.reading(solutions={"sprint-01": "$\\mathbf{5}$"})
        fails = v.gate(r, self.draft(), {"sprint": 3}, True, {})
        self.assertEqual({k: [f["gate"] for f in fs] for k, fs in fails.items()},
                         {"sprint-01": ["final-value"], "sprint-02": ["solution"],
                          "sprint-*": ["count", "count"]})
        fails = v.gate(r, self.draft(), {"sprint": 2}, True,
                       {"sprint-01": ["final-value"], "sprint-02": ["solution"]})
        self.assertEqual(fails, {})


class FormatFixes(unittest.TestCase):
    """The shared code fixes for qwen3.6's format misses (#37)."""

    def test_round_labels_only_move_forward(self):
        pages = [("p1", "=== sprint 30\nA.\n=== target 1\nB.\n=== target 2\nC.\n=== sprint 3\nD.\n=== ? 1\nE.")]
        sols, _, warnings = v.assemble_solutions(pages, set())
        self.assertEqual(sorted(sols), ["sprint-30", "target-01", "target-02", "target-03", "team-01"])
        self.assertEqual(warnings, [])
        answers, _, _, _ = v.assemble_answers([("a1", "team 9: 4\nteam 10: 5\nsprint 1: 6")])
        self.assertEqual(sorted(answers), ["countdown-01", "team-09", "team-10"])

    def test_item_number_is_stripped_from_a_solution(self):
        self.assertEqual(v.parse_solution_page("=== sprint 5\n5. Add the two numbers."),
                         [(("sprint", 5), "Add the two numbers.")])
        self.assertEqual(v.parse_solution_page("=== sprint 5\n12. Twelve apples."),
                         [(("sprint", 5), "12. Twelve apples.")])  # a different number is content

    def test_continued_block_that_starts_with_an_item_number_is_a_header(self):
        pages = [("p1", "=== sprint 6\nFirst half"), ("p2", "=== continued\n7. A new one, $\\mathbf{2}$.")]
        sols, _, _ = v.assemble_solutions(pages, set())
        self.assertEqual(sols, {"sprint-06": "First half", "sprint-07": "A new one, $\\mathbf{2}$."})

    def test_plain_values_leave_math_in_problem_text(self):
        cases = [("Pick $5$ cards from $ABCD$.", "Pick 5 cards from ABCD."),
                 ("If $AB = BC = 5\\text{ cm}$, find it.", "If AB = BC = 5 cm, find it."),
                 ("The area is $12\\text{ cm}^2$.", "The area is 12 cm$^2$."),
                 ("It rose $25\\%$ to $\\$1.49$.", "It rose 25% to \\$1.49."),
                 ("The set $1, 2, 3$ and $PA + PB$.", "The set 1, 2, 3 and PA + PB."),
                 ("Solve $x + 2 = 5$ for $x$ at $A$.", "Solve $x + 2 = 5$ for $x$ at $A$."),
                 ("Consider\n$$x^2 = 4$$\nfor real $x$.", "Consider $$x^2 = 4$$ for real $x$.")]
        for raw, want in cases:
            self.assertEqual(v.demath(raw), want, raw)

    def test_demath_runs_on_content_not_solutions(self):
        with tempfile.TemporaryDirectory() as d:
            t = fake_test(Path(d), [("sprint", 1)])
            r = t.assemble({("problem", "sprint-01"): "Pick $5$ apples.",
                            ("answers", "answers-p1.png"): "sprint 1: 5",
                            ("solutions", "solutions-p1.png"): "=== sprint 1\nTake $5$ so $\\mathbf{5}$."})
        self.assertEqual(r["content"]["sprint-01"], "Pick 5 apples.")
        self.assertEqual(r["solutions"]["sprint-01"], "Take $5$ so $\\mathbf{5}$.")

    def test_value_before_ans_is_bolded_when_the_key_confirms_it(self):
        self.assertEqual(v.bold_final("so $x = 50$ $\\mathbf{Ans}$", ["50"]), "so $x = \\mathbf{50}$ Ans.")
        self.assertEqual(v.bold_final("The total is 12 Ans.", ["12"]), "The total is $\\mathbf{12}$ Ans.")
        for sol, accepted in [("so $x = 49$ $\\mathbf{Ans}$", ["50"]),       # the key disagrees
                              ("so $x = \\mathbf{50}$ Ans.", ["50"]),         # already bold
                              ("so $x = 50$.", ["50"])]:                     # no Ans. at all
            self.assertEqual(v.bold_final(sol, accepted), sol)


class Specs(unittest.TestCase):
    def test_backend_prefix_and_bare_names(self):
        self.assertEqual(v.parse_spec("ollama:qwen3.6:27b-q8_0"), ("ollama", "qwen3.6:27b-q8_0"))
        self.assertEqual(v.parse_spec("openrouter:moonshotai/kimi-k3.1-pro"),
                         ("openrouter", "moonshotai/kimi-k3.1-pro"))
        self.assertEqual(v.parse_spec("moonshotai/kimi-k3.1-pro"), ("openrouter", "moonshotai/kimi-k3.1-pro"))
        self.assertEqual(v.full_spec("moonshotai/kimi-k3"), "openrouter:moonshotai/kimi-k3")

    def test_cache_keys(self):
        c = v.Client.__new__(v.Client)
        bare = c.cache_path("moonshotai/kimi-k3.1-pro", "p", b"png")
        self.assertEqual(c.cache_path("openrouter:moonshotai/kimi-k3.1-pro", "p", b"png"), bare)
        self.assertNotEqual(c.cache_path("ollama:moonshotai/kimi-k3.1-pro", "p", b"png"), bare)

    def test_flag_then_environment_then_default(self):
        self.assertEqual(v.choose("ollama:a", "SBUDDY_TEST_UNSET_VAR", "b"), "ollama:a")
        self.assertEqual(v.choose("", "SBUDDY_TEST_UNSET_VAR", "b"), "")
        self.assertEqual(v.choose(None, "SBUDDY_TEST_UNSET_VAR", "b"), "b")


def fake_test(root, items, answer_pages=1, solution_pages=1, review=None):
    import json
    (root / "pages").mkdir()
    for n in range(1, answer_pages + 1):
        (root / "pages" / f"answers-p{n}.png").write_bytes(b"")
    for n in range(1, solution_pages + 1):
        (root / "pages" / f"solutions-p{n}.png").write_bytes(b"")
    (root / "draft.json").write_text(json.dumps({"problems": [
        {"round": r, "problemNumber": n, "textLayer": "words"} for r, n in items]}))
    (root / "review.json").write_text(json.dumps(review or {}))
    return v.Test(root)


class FallThrough(unittest.TestCase):
    def test_unsourced_key_rereads_only_the_pages_between_its_neighbours(self):
        with tempfile.TemporaryDirectory() as d:
            t = fake_test(Path(d), [("sprint", n) for n in range(1, 7)], answer_pages=6, solution_pages=6)
            src = {"sprint-01": ["solutions-p1.png"], "sprint-02": ["solutions-p2.png", "solutions-p3.png"],
                   "sprint-05": ["solutions-p5.png"]}
            self.assertEqual(v.neighbour_pages(t, "sprint-03", src, t.solution_pages),
                             {"solutions-p3.png", "solutions-p4.png", "solutions-p5.png"})
            self.assertEqual(v.neighbour_pages(t, "sprint-06", src, t.solution_pages),
                             {"solutions-p5.png", "solutions-p6.png"})
            self.assertEqual(len(v.neighbour_pages(t, "sprint-03", {}, t.solution_pages)), 6)
            a_src = {"sprint-01": "answers-p2.png", "sprint-04": "answers-p3.png"}
            self.assertEqual(v.neighbour_pages(t, "sprint-02", a_src, t.answer_pages),
                             {"answers-p2.png", "answers-p3.png"})


class NewRounds(unittest.TestCase):
    def test_rounds_read_only_their_crops_and_merge(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            items = [("sprint", 1), ("countdown", 1), ("countdown", 2)]
            fake_test(root, items, review={"skipRounds": ["countdown"]})
            with self.assertRaises(ValueError):
                v.Test(root, ["countdown"])
            (root / "review.json").write_text("{}")
            t = v.Test(root, ["countdown"])
            self.assertEqual(t.keys, ["countdown-01", "countdown-02"])
            self.assertEqual([j[0] for j in t.jobs()], ["problem", "problem", "answers"])
            r = t.assemble({("problem", "countdown-01"): "Q one", ("problem", "countdown-02"): "Q two",
                            ("answers", "answers-p1.png"): "sprint 1: 9\ncountdown 1: 3\ncountdown 2: 4"})
            self.assertEqual(r["answers"], {"countdown-01": "3", "countdown-02": "4"})
            merged = v.merge_keys({"sprint-01": "kimi", "countdown-01": "old"}, r["answers"], t)
            self.assertEqual(merged, {"sprint-01": "kimi", "countdown-01": "3", "countdown-02": "4"})


if __name__ == "__main__":
    unittest.main()
