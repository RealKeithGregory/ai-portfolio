"""Canonical portfolio content.

Everything the public site says lives here (or in content/blog/*.md).
The templates read from these structures so the same fact is never written
twice.

This is an AI engineering portfolio, not a resume. Employment history --
employer names, job titles, dates, duties -- is deliberately not present in
this module, because everything here is rendered publicly. Keep personal
resume material outside the repository.

Leave a TODO rather than inventing a value that is not known yet.
"""

PROFILE = {
    "name": "Keith Gregory",
    # The one-line positioning for the whole site: page titles, hero, metadata.
    "headline": "Building Reliable AI Systems",
    "tagline": "AI Engineering · Evaluation & Reliability · RAG · Agents",
    # Short hero statement. Emphasis markers (*...*) are rendered as highlights.
    "summary": (
        "I am working toward *AI systems that are measured, not just "
        "demonstrated*: RAG and retrieval, agentic systems and tool use, "
        "guardrails, and observability, with a growing interest in *financial "
        "AI*. The writing below documents what I am learning and building."
    ),
    "about": [
        (
            "I am focused on building AI systems that can be evaluated, tested, and "
            "trusted, with an emphasis on evaluation, agentic systems, RAG, "
            "guardrails, and production reliability."
        ),
        (
            "The questions I care about are the measurable ones. Did retrieval "
            "return the right context? Did the model choose the right tool with "
            "valid arguments? Is the answer grounded in its source? What happens "
            "when a dependency fails?"
        ),
        (
            "I bring more than a decade of experience building, automating, "
            "integrating, and validating production software."
        ),
    ],
    "workflow": ["Learn", "Build", "Evaluate", "Document", "Improve"],
    # Areas of current focus, not claims of mastery.
    "ai_focus": [
        "AI Evaluation & Reliability",
        "RAG & Retrieval",
        "Agentic Systems & Tool Use",
        "Guardrails & Observability",
        "Financial AI",
    ],
    "links": {
        "github": "https://github.com/RealKeithGregory",
        "linkedin": "https://linkedin.com/in/devkeithgregory",
        "email": "keithgregory1625@gmail.com",
    },
}

# Two groups, and the difference between them is the point: established
# skills are ones I can discuss with confidence today; the second group is
# what I am actively learning. Grouped, never rated.
SKILL_GROUPS = [
    {
        "name": "Engineering Foundation",
        "blurb": "Established skills from building, testing, and shipping production software.",
        "skills": [
            "Python",
            "JavaScript",
            "FastAPI",
            "REST APIs",
            "SQL",
            "Git / GitHub",
            "CI/CD",
            "Docker",
            "Playwright",
            "Test automation",
            "Regression testing",
            "Schema validation",
            "Failure analysis",
        ],
    },
    {
        "name": "AI Engineering · Currently Developing",
        "blurb": "Areas I am actively learning and building toward.",
        "skills": [
            "LLM APIs",
            "LLM evaluation",
            "RAG & retrieval",
            "Agents & tool calling",
            "Structured outputs",
            "Guardrails",
            "Observability",
        ],
    },
]
