"""Unit tests for vision.py's parsing and gates. Synthetic text only: the repo
is public, so no MATHCOUNTS content goes here.

    python3 -I -m unittest discover -s scripts/mathcounts -p 'test_*.py'
"""

import unittest

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


if __name__ == "__main__":
    unittest.main()
