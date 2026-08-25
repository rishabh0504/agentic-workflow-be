import pytest
from app.runtime.contracts.validator import ContractValidator
from app.runtime.contracts.compatibility import ContractCompatibility
from app.runtime.contracts.resolver import ContractResolver
from app.runtime.contracts.json_path import JSONPathEvaluator
from app.runtime.contracts.errors import ContractValidationError


def test_validator_exact_match():
    schema = {
        "type": "object",
        "required": ["market_summary", "verified_facts"],
        "properties": {
            "market_summary": {"type": "string"},
            "verified_facts": {"type": "array"}
        }
    }
    payload = {
        "market_summary": "Dubai Hills yields 6.5%",
        "verified_facts": [{"claim": "Price up 12%"}]
    }
    res = ContractValidator.validate(payload, schema)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_validator_type_and_required_error():
    schema = {
        "type": "object",
        "required": ["market_summary", "verified_facts"],
        "properties": {
            "market_summary": {"type": "string"},
            "verified_facts": {"type": "array"}
        }
    }
    # Missing market_summary and verified_facts is a string instead of array
    bad_payload = {"verified_facts": "not_an_array"}
    res = ContractValidator.validate(bad_payload, schema)
    assert res.is_valid is False
    assert len(res.errors) >= 2


def test_recursive_compatibility_subset_pass():
    producer = {
        "type": "object",
        "required": ["market_summary", "verified_facts", "verified_sources"],
        "properties": {
            "market_summary": {"type": "string"},
            "verified_facts": {"type": "array", "items": {"type": "string"}},
            "verified_sources": {"type": "array"}
        }
    }
    # Consumer requires subset of producer guarantees
    consumer = {
        "type": "object",
        "required": ["market_summary"],
        "properties": {
            "market_summary": {"type": "string"},
            "verified_facts": {"type": "array", "items": {"type": "string"}}
        }
    }
    compat = ContractCompatibility.check(producer, consumer)
    assert compat.is_compatible is True


def test_recursive_compatibility_array_items_mismatch():
    producer = {
        "type": "object",
        "required": ["facts"],
        "properties": {
            "facts": {"type": "array", "items": {"type": "object", "properties": {"claim": {"type": "string"}}}}
        }
    }
    consumer = {
        "type": "object",
        "required": ["facts"],
        "properties": {
            "facts": {"type": "array", "items": {"type": "string"}}
        }
    }
    compat = ContractCompatibility.check(producer, consumer)
    assert compat.is_compatible is False
    assert "Type mismatch" in compat.reason


def test_jsonpath_multi_source_resolver():
    state = {
        "input": {"message": "Invoice error", "priority": "high"},
        "node_outputs": {
            "agent-research": {
                "market_summary": "Dubai Real Estate is booming",
                "verified_facts": [{"claim": "1200 transactions"}]
            },
            "agent-producer": {
                "script_dialogue": "Sarah: Welcome to Dubai Property Pulse!"
            }
        }
    }

    # Evaluate paths
    script = JSONPathEvaluator.evaluate("$nodes.agent-producer.output.script_dialogue", state)
    facts = JSONPathEvaluator.evaluate("$nodes.agent-research.output.verified_facts", state)
    msg = JSONPathEvaluator.evaluate("$workflow.input.message", state)

    assert script == "Sarah: Welcome to Dubai Property Pulse!"
    assert len(facts) == 1
    assert msg == "Invoice error"


def test_resolver_mode_b_mapping():
    state = {
        "node_outputs": {
            "agent-research": {"verified_facts": ["fact 1", "fact 2"]},
            "agent-producer": {"script_dialogue": "Podcast dialogue script"}
        }
    }
    consumer_node = {
        "id": "guardrail-fact",
        "data": {
            "inputMapping": {
                "script": "$nodes.agent-producer.output.script_dialogue",
                "facts": "$nodes.agent-research.output.verified_facts"
            }
        }
    }
    resolved = ContractResolver.resolve_and_validate_input(consumer_node, state, incoming_edges=[])
    assert resolved.mode == "MAPPED"
    assert resolved.payload["script"] == "Podcast dialogue script"
    assert resolved.payload["facts"] == ["fact 1", "fact 2"]
