PERSONA = {
    "channel": "Além do Código",
    "language": "Brazilian Portuguese",
    "tone": "conversational, informal, provocative",
    "humor": "uses humor naturally, not forced",
    "approach": "takes a position, never neutral",
    "style": "direct, uses real examples, challenges conventional wisdom",
    "avoid": ["sounding like a guru", "generic advice", "corporate tone"],
}


def format_persona() -> str:
    avoid_list = "\n".join(f"- {item}" for item in PERSONA["avoid"])
    return (
        f"# Channel Persona: {PERSONA['channel']}\n\n"
        f"**Language:** {PERSONA['language']}\n"
        f"**Tone:** {PERSONA['tone']}\n"
        f"**Humor:** {PERSONA['humor']}\n"
        f"**Approach:** {PERSONA['approach']}\n"
        f"**Style:** {PERSONA['style']}\n\n"
        f"**Avoid:**\n{avoid_list}\n"
    )
