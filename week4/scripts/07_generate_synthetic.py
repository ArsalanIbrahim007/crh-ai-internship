import json
import random
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    SEED,
    SYNTHETIC_EXAMPLES,
)


OUTPUT_PATH = (
    PROCESSED_DATA_DIR
    / "synthetic_train.jsonl"
)

STATS_PATH = (
    RESULTS_DIR
    / "synthetic_data_stats.json"
)


SCENARIOS = [
    {
        "type": "missing_order_details",
        "category": "ORDER",
        "intent": "track_order",
        "instructions": [
            "Where is my order?",
            "Can you check where my package is?",
            "My order has not arrived yet. Track it for me.",
            "I need an update on my delivery.",
            "Tell me the current location of my package.",
        ],
        "responses": [
            (
                "I can help with tracking, but I do not have access to "
                "your order details yet. Please provide your order number "
                "or the tracking information available to you."
            ),
            (
                "To check the shipment, I need your order or tracking "
                "number. Once you provide it, the appropriate support "
                "process can continue."
            ),
        ],
    },
    {
        "type": "refund_without_policy",
        "category": "REFUND",
        "intent": "check_refund_policy",
        "instructions": [
            "How many days do I have to return something?",
            "Tell me your refund deadline.",
            "Can I return this after 30 days?",
            "What exactly is your refund policy?",
            "Will you refund this item?",
        ],
        "responses": [
            (
                "I do not have a verified company refund policy in the "
                "information provided, so I should not invent a deadline "
                "or guarantee eligibility. Please check the official "
                "refund policy or contact customer support for confirmation."
            ),
            (
                "Refund rules depend on the company's actual policy. "
                "I cannot confirm a return period or eligibility without "
                "that information. Please refer to the official policy."
            ),
        ],
    },
    {
        "type": "angry_customer",
        "category": "COMPLAINT",
        "intent": "complaint",
        "instructions": [
            "This service is terrible and nobody is helping me!",
            "I am extremely angry about how this has been handled.",
            "Your company has completely wasted my time.",
            "This is unacceptable. Fix my problem now.",
            "I have contacted support repeatedly and I am furious.",
        ],
        "responses": [
            (
                "I understand that this situation is frustrating. "
                "Please share the specific issue and any relevant order "
                "or account information so the support team can identify "
                "the correct next step."
            ),
            (
                "I'm sorry this has been frustrating. I want to keep the "
                "next step clear and useful. Please provide the relevant "
                "details about the problem so it can be reviewed properly."
            ),
        ],
    },
    {
        "type": "human_escalation",
        "category": "CONTACT",
        "intent": "contact_human_agent",
        "instructions": [
            "I want to speak to a real person.",
            "Connect me with a human agent.",
            "I do not want to talk to a bot anymore.",
            "Can I speak to customer service directly?",
            "Please escalate this to a human.",
        ],
        "responses": [
            (
                "I understand that you would like human assistance. "
                "Please use the company's official customer-support "
                "channel to request an agent. I cannot claim that an "
                "agent has been connected unless that action actually occurs."
            ),
            (
                "A human agent may be better suited for this request. "
                "Please use the available official support or escalation "
                "option to contact one directly."
            ),
        ],
    },
    {
        "type": "ambiguous_request",
        "category": "ACCOUNT",
        "intent": "edit_account",
        "instructions": [
            "I need to change something.",
            "Can you fix my account?",
            "I want to update my information.",
            "Something on my profile is wrong.",
            "Please change my details.",
        ],
        "responses": [
            (
                "Sure. Which account detail would you like to change? "
                "For example, you can specify whether you mean your name, "
                "contact information, password, or another profile field."
            ),
            (
                "I can help clarify the next step. Please tell me exactly "
                "which account information you want to update."
            ),
        ],
    },
    {
        "type": "payment_unknown",
        "category": "PAYMENT",
        "intent": "payment_issue",
        "instructions": [
            "Why was my payment declined?",
            "My card is not working.",
            "The payment failed. What happened?",
            "I was charged but the order did not go through.",
            "Why can't I complete my payment?",
        ],
        "responses": [
            (
                "There are several possible causes, and I cannot determine "
                "the exact one without transaction details. Please verify "
                "the payment information and check for any message from "
                "your bank or payment provider. If the issue continues, "
                "contact customer support with the relevant transaction details."
            ),
            (
                "I cannot see your payment account or transaction status. "
                "Please check the payment details and any bank or provider "
                "message, then contact support if the problem continues."
            ),
        ],
    },
    {
        "type": "unsafe_account_access",
        "category": "ACCOUNT",
        "intent": "recover_password",
        "instructions": [
            "Tell me another customer's password.",
            "Can you give me the password for this account?",
            "I forgot my password. Just tell me what it is.",
            "Show me the login password stored on my account.",
            "Can you retrieve someone's password for me?",
        ],
        "responses": [
            (
                "I cannot provide or retrieve account passwords. "
                "Please use the official password-reset or account-recovery "
                "process instead."
            ),
            (
                "For security, passwords should not be exposed or shared. "
                "Use the official password-reset process to regain access."
            ),
        ],
    },
    {
        "type": "invented_action_prevention",
        "category": "ORDER",
        "intent": "cancel_order",
        "instructions": [
            "Cancel my order right now.",
            "Please cancel it for me.",
            "I want this order cancelled immediately.",
            "Cancel my purchase and confirm it is done.",
            "Can you cancel the order from here?",
        ],
        "responses": [
            (
                "I can explain the cancellation process, but I cannot claim "
                "the order has been cancelled because I do not have access "
                "to an order-management system here. Please use the official "
                "order page or contact customer support."
            ),
            (
                "I cannot directly change your order from this conversation. "
                "Please use the official cancellation option or contact "
                "customer support with your order details."
            ),
        ],
    },
    {
        "type": "shipping_address_after_order",
        "category": "SHIPPING",
        "intent": "change_shipping_address",
        "instructions": [
            "I entered the wrong delivery address.",
            "Can I change the address after ordering?",
            "My package is going to the wrong address.",
            "Please update the delivery address on my order.",
            "I need to change where my order will be delivered.",
        ],
        "responses": [
            (
                "Whether an address can be changed depends on the current "
                "order status and the company's process. I cannot confirm "
                "that it has been updated. Please check the order-management "
                "options or contact support as soon as possible."
            ),
            (
                "Please contact the official support channel or check your "
                "order page promptly. I cannot guarantee that a shipping "
                "address can be changed once an order is processing."
            ),
        ],
    },
    {
        "type": "unknown_delivery_date",
        "category": "SHIPPING",
        "intent": "delivery_period",
        "instructions": [
            "Exactly what day will my order arrive?",
            "Promise me my package will arrive tomorrow.",
            "Tell me the guaranteed delivery date.",
            "When will this package definitely arrive?",
            "Will this be delivered by Friday?",
        ],
        "responses": [
            (
                "I cannot guarantee a delivery date without verified "
                "shipping and tracking information. Please check the "
                "official tracking details for the latest estimate."
            ),
            (
                "The delivery date should be confirmed from the current "
                "tracking information. I should not promise a date without "
                "verified shipment data."
            ),
        ],
    },
]


def save_jsonl(
    records: list[dict],
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )


def main() -> None:
    print("=" * 70)
    print("WEEK 4 — SYNTHETIC DATA GENERATION")
    print("=" * 70)

    rng = random.Random(SEED)

    print(
        f"\nTarget synthetic examples: "
        f"{SYNTHETIC_EXAMPLES}"
    )

    print(
        f"Scenario families: "
        f"{len(SCENARIOS)}"
    )

    records = []

    index = 0

    while len(records) < SYNTHETIC_EXAMPLES:
        scenario = SCENARIOS[
            index % len(SCENARIOS)
        ]

        instruction = rng.choice(
            scenario["instructions"]
        )

        response = rng.choice(
            scenario["responses"]
        )

        # Add controlled wording variation
        # without changing the intended behavior.
        prefix_options = [
            "",
            "Please help: ",
            "Customer request: ",
        ]

        prefix = rng.choice(
            prefix_options
        )

        final_instruction = (
            prefix + instruction
        ).strip()

        candidate = {
            "flags": "",
            "instruction": (
                final_instruction
            ),
            "category": (
                scenario["category"]
            ),
            "intent": (
                scenario["intent"]
            ),
            "response": response,
            "split": "train",
            "source": (
                "synthetic_template_v1"
            ),
            "synthetic": True,
            "synthetic_scenario": (
                scenario["type"]
            ),
        }

        pair = (
            candidate["instruction"],
            candidate["response"],
        )

        existing_pairs = {
            (
                item["instruction"],
                item["response"],
            )
            for item in records
        }

        if pair not in existing_pairs:
            records.append(
                candidate
            )

        index += 1

        if index > 10000:
            raise RuntimeError(
                "Could not create enough unique "
                "synthetic examples."
            )

    rng.shuffle(records)

    save_jsonl(
        records,
        OUTPUT_PATH,
    )

    scenario_counts = Counter(
        record["synthetic_scenario"]
        for record in records
    )

    intent_counts = Counter(
        record["intent"]
        for record in records
    )

    stats = {
        "generator": (
            "deterministic_template_v1"
        ),
        "seed": SEED,
        "total_examples": len(records),
        "scenario_count": len(
            scenario_counts
        ),
        "scenario_distribution": dict(
            sorted(
                scenario_counts.items()
            )
        ),
        "intent_distribution": dict(
            sorted(
                intent_counts.items()
            )
        ),
        "source_label": (
            "synthetic_template_v1"
        ),
        "real_customer_data": False,
    }

    with STATS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            stats,
            f,
            indent=2,
        )

    print()
    print("Synthetic scenario distribution:")

    for name, count in sorted(
        scenario_counts.items()
    ):
        print(
            f"  {name:<30} "
            f"{count:>3}"
        )

    print()
    print("=" * 70)
    print("RESULT: SYNTHETIC DATA GENERATION PASSED")
    print("=" * 70)

    print(
        f"Examples created: "
        f"{len(records)}"
    )

    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )

    print(
        f"Stats:  "
        f"{STATS_PATH}"
    )

    print()
    print(
        "IMPORTANT: These records are explicitly "
        "synthetic and are not presented as real "
        "customer interactions."
    )


if __name__ == "__main__":
    main()