import re
from typing import Any, Dict, Optional


class OutputSanitizer:
    """
    Dedicated transformation utility that cleans serialized output strings,
    stripping stray markup artifacts, orphaned SVG tags, broken code fences,
    and internal logging leakage.
    """

    @staticmethod
    def sanitize(text: Optional[str]) -> str:
        if not text:
            return ""

        cleaned = str(text)

        # 1. Strip stray svg leakage patterns (e.g. svg[Segment ..., Reportsvg)
        cleaned = re.sub(r'svg\[[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'Reportsvg', '', cleaned)
        cleaned = re.sub(r'<\/?svg[^>]*>', '', cleaned)

        # 2. Strip internal reasoning tags if leaked into content
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<\/?think>', '', cleaned)

        # 3. Clean up broken triple backtick fences
        # Ensure balanced code fences
        fence_count = cleaned.count("```")
        if fence_count % 2 != 0:
            cleaned += "\n```"

        # 4. Remove leading/trailing trailing whitespace noise
        return cleaned.strip()
