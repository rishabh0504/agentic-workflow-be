from typing import Optional, Dict, Any
from app.runtime.contracts.models import ContractValidationResult, SchemaPropertyValidationError


class ContractValidationError(Exception):
    """Raised when an executable payload violates an immutable I/O contract schema."""
    def __init__(self, message: str, validation_result: Optional[ContractValidationResult] = None):
        super().__init__(message)
        self.message = message
        self.validation_result = validation_result


class IncompatibleContractError(Exception):
    """Raised when producer output contract cannot satisfy consumer input contract."""
    def __init__(self, producer_contract: str, consumer_contract: str, reason: str):
        self.producer_contract = producer_contract
        self.consumer_contract = consumer_contract
        self.reason = reason
        super().__init__(f"Contract incompatibility: '{producer_contract}' cannot satisfy '{consumer_contract}'. Reason: {reason}")


class ModelOutputContractError(Exception):
    """Raised at runtime when an LLM produces output violating its promised outputContract."""
    def __init__(self, agent_id: str, contract_name: str, validation_result: ContractValidationResult, raw_output: Any):
        self.agent_id = agent_id
        self.contract_name = contract_name
        self.validation_result = validation_result
        self.raw_output = raw_output
        super().__init__(f"Model output violation on Agent '{agent_id}' for contract '{contract_name}'.")
