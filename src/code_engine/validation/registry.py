"""Validator plugin registry with local-resource awareness."""

from pathlib import Path

from code_engine.schemas.validation import ValidationQuestion, ValidationResult
from code_engine.validation.bindingdb import BindingDBValidator
from code_engine.validation.chembl import ChEMBLValidator
from code_engine.validation.clinical_trials import ClinicalTrialsValidator
from code_engine.validation.curated_omics import CuratedOmicsValidator
from code_engine.validation.drugbank import DrugBankValidator
from code_engine.validation.geo import GEOValidator
from code_engine.validation.null import NullValidator
from code_engine.validation.pubmed_clinical import PubMedClinicalEvidenceValidator
from code_engine.validation.reactome import PathwayValidator, ReactomeValidator
from code_engine.validation.stringdb import STRINGValidator
from code_engine.validation.lincs import LINCSValidator
from code_engine.validation.depmap import DepMapValidator
from code_engine.validation.pubchem import PubChemValidator
from code_engine.validation.uniprot import UniProtValidator
from code_engine.validation.opentargets import OpenTargetsValidator
from code_engine.schemas.validation import ValidatorCapability


DEFAULT_VALIDATORS = (
    CuratedOmicsValidator, GEOValidator, LINCSValidator, DepMapValidator,
    DrugBankValidator, ChEMBLValidator, BindingDBValidator, PubChemValidator,
    ReactomeValidator, PathwayValidator, STRINGValidator, UniProtValidator,
    ClinicalTrialsValidator, PubMedClinicalEvidenceValidator, OpenTargetsValidator,
    NullValidator,
)


class ValidatorRegistry:
    def __init__(self, *, configured_resources: set[str] | None = None, resource_paths: dict[str, str] | None = None):
        self.configured_resources = set(configured_resources or ())
        self.resource_paths = resource_paths or {}
        self._classes = {}
        self._capabilities: dict[str, ValidatorCapability] = {}

    def register(self, validator_class, capability: ValidatorCapability | None = None) -> None:
        self._classes[validator_class.name] = validator_class
        self._capabilities[validator_class.name] = capability or validator_class.capability()

    def register_defaults(self) -> "ValidatorRegistry":
        for validator in DEFAULT_VALIDATORS:
            self.register(validator)
        return self

    def is_configured(self, name: str) -> bool:
        cls = self._classes[name]
        if name == "CuratedOmicsValidator":
            return bool(CuratedOmicsValidator().registry)
        if not cls.required_resources:
            return True
        return all(resource in self.configured_resources or (resource in self.resource_paths and Path(self.resource_paths[resource]).exists()) for resource in cls.required_resources)

    def list_capabilities(self) -> list[ValidatorCapability]:
        return [self._capabilities[name] for name in sorted(self._capabilities)]

    def get_capability(self, name: str) -> ValidatorCapability:
        return self._capabilities[name]

    def names(self) -> list[str]:
        return sorted(self._classes)

    def create(self, name: str):
        cls = self._classes[name]
        if name == "NullValidator":
            return cls()
        if name == "CuratedOmicsValidator":
            return cls(lincs_index_path=self.resource_paths.get("curated_omics_registry", "configs/validators/curated_omics_registry.json"))
        available_paths = {
            resource
            for resource, path in self.resource_paths.items()
            if Path(path).exists()
        }
        return cls(
            configured_resources=self.configured_resources | available_paths,
            resource_paths=self.resource_paths,
        )

    def applicable(self, question: ValidationQuestion) -> list[str]:
        return [
            name
            for name in question.preferred_validators
            if name in self._classes and self.create(name).can_validate(question)
        ]

    def validate(self, name: str, question: ValidationQuestion) -> ValidationResult:
        if name not in self._classes:
            return ValidationResult(
                hypothesis_id=question.hypothesis_id,
                validator_name=name,
                domain_id=question.domain_id,
                validator_profile_id=question.validator_profile_id,
                validation_status="error",
                limitations=["Validator is not registered."],
            )
        return self.create(name).validate(question)
