from pathlib import Path

QUERY = "A generic intervention changes mechanism activity across disease contexts."


def generate(root: Path, **overrides):
    from code_engine.case_factory import generate_case_package
    values = dict(case_id="generic_case", query=QUERY, case_type="conflict_enriched", year_from=2001,
                  year_to=2019, output_root="generated", repository_root=root, api=False, network=False)
    values.update(overrides)
    return generate_case_package(**values)
