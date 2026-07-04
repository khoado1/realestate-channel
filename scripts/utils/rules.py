"""Apply an ordered list of declarative regex substitution rules to text."""

import re

_FLAGS = {"IGNORECASE": re.IGNORECASE, "MULTILINE": re.MULTILINE, "DOTALL": re.DOTALL}


def apply_rules(text: str, rules: list[dict]) -> str:
    """Run each rule's regex substitution over ``text``, in order.

    Each rule: {pattern, replacement="", flags=[...]}. Unknown flags raise KeyError.
    """
    for rule in rules:
        flags = 0
        for name in rule.get("flags", []):
            flags |= _FLAGS[name]
        text = re.sub(rule["pattern"], rule.get("replacement", ""), text, flags=flags)
    return text
