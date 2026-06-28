"""Domain routing and prompt-selection contracts."""

from code_engine.domain.models import DomainProfile, PromptProfile, default_domain_profiles
from code_engine.domain.router import DomainRouter, default_domain_router
from code_engine.domain.prompt_registry import PromptRegistry, default_prompt_registry
from code_engine.domain.prompt_compiler import CompiledPrompt, compile_l1_prompt

__all__ = [
    "DomainProfile", "PromptProfile", "default_domain_profiles", "DomainRouter", "default_domain_router",
    "PromptRegistry", "default_prompt_registry", "CompiledPrompt", "compile_l1_prompt",
]
