from __future__ import annotations


def emit_status(step: str, fields: dict[str, object]) -> None:
    print(f"=== NANOCLAW SETUP: {step} ===")
    for key, value in fields.items():
        print(f"{key}: {value}")
    print("=== END ===")
