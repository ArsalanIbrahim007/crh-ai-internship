import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MAIN_ADAPTER = (
    ROOT
    / "outputs"
    / "mistral7b-customer-support-r8"
    / "final_adapter"
)

HYPERPARAM_RESULTS = (
    ROOT
    / "results"
    / "hyperparameter_results.json"
)

OUTPUT_FILE = (
    ROOT
    / "results"
    / "export_verification.json"
)


REQUIRED_FILES = [
    "adapter_config.json",
    "adapter_model.safetensors",
    "tokenizer_config.json",
]


def verify_adapter(path: Path):
    result = {
        "path": str(path),
        "exists": path.exists(),
        "files": {},
        "valid": False,
    }

    if not path.exists():
        return result

    all_present = True

    for filename in REQUIRED_FILES:
        file_path = path / filename

        exists = file_path.exists()

        result["files"][filename] = {
            "exists": exists,
            "size_bytes": (
                file_path.stat().st_size
                if exists
                else None
            ),
        }

        if not exists:
            all_present = False

    result["valid"] = all_present

    return result


print("=" * 72)
print("WEEK 4 — ADAPTER EXPORT VERIFICATION")
print("=" * 72)

main_result = verify_adapter(
    MAIN_ADAPTER
)

hyperparam_adapter = None

if HYPERPARAM_RESULTS.exists():
    with open(
        HYPERPARAM_RESULTS,
        "r",
        encoding="utf-8",
    ) as f:
        hyperparam_results = json.load(f)

    adapter_path = hyperparam_results.get(
        "final_adapter"
    )

    if adapter_path:
        hyperparam_adapter = verify_adapter(
            Path(adapter_path)
        )


results = {
    "main_adapter": main_result,
    "hyperparameter_adapter": (
        hyperparam_adapter
    ),
}


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        results,
        f,
        indent=2,
    )


print()
print("Main adapter:")
print(
    f"  Exists: {main_result['exists']}"
)
print(
    f"  Valid:  {main_result['valid']}"
)

if hyperparam_adapter:
    print()
    print("Hyperparameter adapter:")
    print(
        f"  Exists: "
        f"{hyperparam_adapter['exists']}"
    )
    print(
        f"  Valid:  "
        f"{hyperparam_adapter['valid']}"
    )

print()
print(f"Results: {OUTPUT_FILE}")

if not main_result["valid"]:
    raise RuntimeError(
        "Main adapter verification failed."
    )

print()
print("=" * 72)
print("RESULT: EXPORT VERIFICATION PASSED")
print("=" * 72)