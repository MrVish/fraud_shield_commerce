from dataclasses import dataclass


@dataclass
class RuleDefinition:
    name: str
    conditions: dict
    action: str
    priority: int = 0


class CustomRuleEngine:
    def __init__(self):
        self.whitelist: dict[str, set[str]] = {"email": set(), "ip": set(), "bin": set()}
        self.blacklist: dict[str, set[str]] = {"email": set(), "ip": set(), "bin": set()}
        self.rules: list[RuleDefinition] = []

    def add_whitelist(self, entry_type: str, value: str):
        self.whitelist.setdefault(entry_type, set()).add(value.lower())

    def add_blacklist(self, entry_type: str, value: str):
        self.blacklist.setdefault(entry_type, set()).add(value.lower())

    def add_rule(self, rule: RuleDefinition):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, email: str = "", ip: str = "", card_bin: str = "") -> str | None:
        if email.lower() in self.blacklist.get("email", set()): return "block"
        if ip in self.blacklist.get("ip", set()): return "block"
        if card_bin in self.blacklist.get("bin", set()): return "block"
        if email.lower() in self.whitelist.get("email", set()): return "approve"
        if ip in self.whitelist.get("ip", set()): return "approve"
        return None

    def evaluate_signals(self, signals_dict: dict, order_total: float = 0,
                         email: str = "", ip: str = "", card_bin: str = "") -> str | None:
        override = self.evaluate(email=email, ip=ip, card_bin=card_bin)
        if override: return override
        for rule in self.rules:
            if self._matches(rule.conditions, signals_dict, order_total):
                return rule.action
        return None

    def _matches(self, conditions: dict, signals: dict, order_total: float) -> bool:
        for key, expected in conditions.items():
            if key == "order_total_gt":
                if order_total <= expected: return False
            elif key == "order_total_lt":
                if order_total >= expected: return False
            else:
                if signals.get(key) != expected: return False
        return True
