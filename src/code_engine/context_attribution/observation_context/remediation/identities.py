from ...layer_identity import layer_identity
def remediation_identity(payload:dict)->str:
    # Candidate references and endpoint role are deliberately excluded.
    keys=("observation_id","normalized_claim_identity","current_context_identity","failure_class",
          "current_context_validator_identity","context_source_artifact_identity","validation_audit_identity")
    return layer_identity("observation_context_remediation_need","observation_context_remediation_need_identity_v1",{k:payload[k] for k in keys})
def case_identity(kind:str,payload:dict)->str:
    return layer_identity(kind,f"{kind}_identity_v1",payload)
