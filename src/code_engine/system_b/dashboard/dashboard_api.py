"""Dashboard JSON routes composed with the existing KG API."""

from __future__ import annotations

from urllib.parse import unquote

from code_engine.system_b.kg.kg_api import KGAPI

from .dashboard_data import DashboardData


class DashboardAPI:
    def __init__(self, system_b_root, kg_root):
        self.data = DashboardData(system_b_root, kg_root)
        self.kg = KGAPI(kg_root)

    def dispatch(self, path, params=None):
        if not path.startswith("/api/dashboard/"):
            return self.kg.dispatch(path, params)
        if path == "/api/dashboard/summary": return 200, self.data.summary()
        if path == "/api/dashboard/cases": return 200, self.data.cases()
        if path == "/api/dashboard/comparison": return 200, self.data.comparison()
        if path == "/api/dashboard/validator-coverage": return 200, self.data.validator_coverage()
        if path == "/api/dashboard/domain-coverage": return 200, self.data.domain_coverage()
        if path == "/api/dashboard/recommendations": return 200, self.data.recommendations()
        if path == "/api/dashboard/warnings": return 200, {"warnings": self.data.warnings()}
        if path == "/api/dashboard/files": return 200, self.data.files()
        prefix = "/api/dashboard/case/"
        if path.startswith(prefix):
            remainder = unquote(path.removeprefix(prefix))
            if remainder.endswith("/card"): value = self.data.case_card(remainder.removesuffix("/card"))
            elif remainder.endswith("/quality"): value = self.data.case_quality(remainder.removesuffix("/quality"))
            else: value = self.data.case(remainder)
            return (200, value) if value is not None else (404, {"error": "case_not_found"})
        return 404, {"error": "not_found"}
