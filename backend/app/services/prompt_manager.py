"""Prompt manager — loads and renders prompt templates."""
from pathlib import Path
from string import Template
from ..config import settings, PROMPTS_DIR


class PromptManager:
    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self.prompts_dir = prompts_dir
        self._cache: dict[str, str] = {}

    def _load(self, relative_path: str) -> str:
        if relative_path not in self._cache:
            full = self.prompts_dir / relative_path
            if not full.exists():
                raise FileNotFoundError(f"Prompt template not found: {full}")
            self._cache[relative_path] = full.read_text(encoding="utf-8")
        return self._cache[relative_path]

    def _render(self, template_str: str, **kwargs) -> str:
        # Use string.Template for safe ${var} substitution, but our templates use {var}
        # so we use simple format replacement
        result = template_str
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result

    def get_role_prompt(self, role: str) -> str:
        """Load role definition (pm/dev/test)."""
        return self._load(f"roles/{role}.md")

    def get_phase1_plan(self, role: str, document: str) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1 Plan step."""
        role_prompt = self.get_role_prompt(role)
        user_template = self._load("phase1/plan.md")
        user_prompt = self._render(user_template,
                                   role_prompt=role_prompt,
                                   document=document)
        return role_prompt, user_prompt

    def get_phase1_execute(self, role: str, document: str,
                           review_plan: str, focus_area: str) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1 Execute step."""
        role_prompt = self.get_role_prompt(role)
        user_template = self._load("phase1/execute.md")
        user_prompt = self._render(user_template,
                                   role_prompt=role_prompt,
                                   document=document,
                                   review_plan=review_plan,
                                   focus_area=focus_area)
        return role_prompt, user_prompt

    def get_phase1_reflect(self, role: str, review_plan: str,
                            findings: str) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1 Reflect step."""
        user_template = self._load("phase1/reflect.md")
        user_prompt = self._render(user_template,
                                   role=role,
                                   review_plan=review_plan,
                                   findings=findings)
        system_prompt = "You are a self-assessment module for requirement review."
        return system_prompt, user_prompt

    def get_phase1_consolidate(self, role: str, all_findings: str,
                                reflect_result: str) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1 Consolidate step."""
        user_template = self._load("phase1/consolidate.md")
        user_prompt = self._render(user_template,
                                   role=role,
                                   all_findings=all_findings,
                                   reflect_result=reflect_result)
        system_prompt = "You are a report consolidation module for requirement review."
        return system_prompt, user_prompt

    # Phase 2 prompts
    def get_phase2_plan(self, role: str, document: str, my_phase1: str,
                        peer_findings: str) -> tuple[str, str]:
        role_prompt = self.get_role_prompt(role)
        user_template = self._load("phase2/plan.md")
        user_prompt = self._render(user_template,
                                   role_prompt=role_prompt,
                                   document=document,
                                   my_phase1=my_phase1,
                                   peer_findings=peer_findings)
        return role_prompt, user_prompt

    def get_phase2_execute(self, role: str, document: str, cross_review_plan: str,
                            peer_findings: str, re_review_target: str) -> tuple[str, str]:
        user_template = self._load("phase2/execute.md")
        user_prompt = self._render(user_template,
                                   role=role,
                                   document=document,
                                   cross_review_plan=cross_review_plan,
                                   peer_findings=peer_findings,
                                   re_review_target=re_review_target)
        system_prompt = "You are a cross-review execution module."
        return system_prompt, user_prompt

    def get_phase2_reflect(self, role: str, cross_review_plan: str,
                            cross_findings: str) -> tuple[str, str]:
        user_template = self._load("phase2/reflect.md")
        user_prompt = self._render(user_template,
                                   role=role,
                                   cross_review_plan=cross_review_plan,
                                   cross_findings=cross_findings)
        return "You are a cross-review self-assessment module.", user_prompt

    def get_phase2_consolidate(self, role: str, cross_findings: str,
                                reflect_result: str) -> tuple[str, str]:
        user_template = self._load("phase2/consolidate.md")
        user_prompt = self._render(user_template,
                                   role=role,
                                   cross_findings=cross_findings,
                                   reflect_result=reflect_result)
        return "You are a cross-review consolidation module.", user_prompt


prompt_manager = PromptManager()
