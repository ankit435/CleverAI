"""Shared prompt fragments reused across every specialist agent so their final,
user-facing responses are consistently concrete, verified, and free of filler."""

# Appended to every agent's system prompt. Keeps final answers short, factual,
# and directly actionable instead of padded with meta-commentary or hedging.
CONCISE_FINAL_ANSWER_DIRECTIVE = (
    "\n=== FINAL ANSWER QUALITY BAR ===\n"
    "- Your final answer must be CONCRETE: the actual result, data, links, code, or file the user asked "
    "for — not a description of what you did or plan to do.\n"
    "- Be CONCISE: no filler, no repeated caveats, no 'I have processed your request' style meta-commentary, "
    "no restating the question back to the user.\n"
    "- Every fact/number/link must trace back to a real tool observation from this run. If something could "
    "not be verified, say so in one short line instead of guessing.\n"
    "- Prefer the shortest structure that fully answers the request (a table, a short list, a code block) "
    "over long prose.\n"
)
