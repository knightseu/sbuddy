/**
 * Shared display rules for Rounds, Problem labels and Answers (map #8).
 * Used by index.html, problem.html and studyPlan.html.
 */
(function () {
    // Units printed before the number in the answer blank (#18). Every other unit goes after.
    const PREFIX_UNITS = new Set(['$', '€', '£']);

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /** "sprint" -> "Sprint". */
    function roundLabel(round) {
        return round ? round.charAt(0).toUpperCase() + round.slice(1) : '';
    }

    /** "Sprint 12" for a multi-Round Test, "Problem 12" for a single-Round Test (AMC). */
    function problemLabel(problem) {
        return problem.round
            ? `${roundLabel(problem.round)} ${problem.problemNumber}`
            : `Problem ${problem.problemNumber}`;
    }

    /**
     * One Answer form with its unit. The Answer may hold $...$ LaTeX and is left
     * for MathJax; the unit is plain text in a span MathJax ignores, so "$" can't
     * open a formula.
     */
    function formatAnswer(answer, unit) {
        if (!unit) return answer;
        const unitHtml = `<span class="answer-unit tex2jax_ignore">${escapeHtml(unit)}</span>`;
        return PREFIX_UNITS.has(unit) ? `${unitHtml}${answer}` : `${answer} ${unitHtml}`;
    }

    /** The revealed Answer block: official form, then a quieter "Also accepted" line. */
    function formatAnswerBlock(problem) {
        if (!problem.correctAnswer) return '';
        const alternatives = (problem.answerAlternatives || []).filter(Boolean);
        const alsoHtml = alternatives.length
            ? `<div class="answer-alternatives">Also accepted: ${alternatives
                  .map(a => formatAnswer(a, problem.answerUnit))
                  .join(', ')}</div>`
            : '';
        return `<div class="answer-value">${formatAnswer(problem.correctAnswer, problem.answerUnit)}</div>${alsoHtml}`;
    }

    window.Rounds = { escapeHtml, roundLabel, problemLabel, formatAnswer, formatAnswerBlock };
})();
