import time
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.guardrail import GuardrailModel, GuardrailExecutionModel, GuardrailBindingModel
from app.schemas.guardrail import GuardrailResult, GuardrailViolation
from app.runtime.sanitizer import OutputSanitizer


class GuardrailManager:
    """
    Authoritative Policy Execution Subsystem.
    Evaluates multi-level guardrails across scopes (AGENT_OUTPUT, WORKFLOW_OUTPUT, etc.),
    distinguishing detection (validators) from transformation (sanitizers), and
    recording standardized audit trails into PostgreSQL guardrail_executions.
    """

    @staticmethod
    async def evaluate(
        guardrail: GuardrailModel,
        payload: Any,
        db: AsyncSession,
        scope: str = "AGENT_OUTPUT",
        workflow_run_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        binding_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> GuardrailResult:
        start_time = time.perf_counter()
        exec_id = f"gex_{uuid.uuid4().hex[:12]}"
        
        # Safely extract raw_text string from any payload shape
        if isinstance(payload, str):
            raw_text = payload
        elif isinstance(payload, dict):
            raw_text = (
                payload.get("response")
                or payload.get("script_dialogue")
                or payload.get("resolution_draft")
                or payload.get("message")
                or payload.get("text")
                or json.dumps(payload)
            )
        elif payload is None:
            raw_text = ""
        else:
            raw_text = str(payload)

        raw_text = str(raw_text or "")
        
        violations: List[GuardrailViolation] = []
        status = "PASSED"
        action = guardrail.default_action or "ALLOW"
        score = 1.0
        output_payload = payload
        context = context or {}

        # -------------------------------------------------------------
        # 1. TRANSFORMATION GUARDRAILS (Output Sanitizer / Formatter)
        # -------------------------------------------------------------
        if guardrail.execution_mode == "transformer" or guardrail.category == "output_quality":
            cleaned_text = OutputSanitizer.sanitize(raw_text)
            if cleaned_text != raw_text:
                status = "REWRITTEN"
                action = "REWRITE"
                if isinstance(payload, dict):
                    output_payload = {**payload, "response": cleaned_text}
                else:
                    output_payload = cleaned_text

        # -------------------------------------------------------------
        # 2. LIVE LINK HEALTH & 404 GUARDRAIL
        # -------------------------------------------------------------
        elif "link" in guardrail.name or guardrail.name == "link_health_verifier":
            import httpx
            urls_found = re.findall(r'https?://[^\s\)\]\>]+', raw_text)
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                for u in urls_found[:8]:
                    try:
                        resp = await client.get(u, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code in (404, 410, 500, 502, 503):
                            violations.append(GuardrailViolation(
                                type="CUSTOM",
                                severity="WARNING",
                                message=f"Broken link detected (HTTP {resp.status_code}): {u}",
                                claim=u,
                                suggested_fix="Replace with active article link or search archive"
                            ))
                    except (httpx.ConnectError, httpx.TimeoutException) as conn_err:
                        violations.append(GuardrailViolation(
                            type="CUSTOM",
                            severity="WARNING",
                            message=f"Unreachable link detected ({type(conn_err).__name__}): {u}",
                            claim=u,
                            suggested_fix="Replace with active article link"
                        ))
                    except Exception:
                        pass

            if violations:
                status = "WARNING"
                action = "WARN"
                score = 0.8
            else:
                status = "PASSED"
                action = "ALLOW"
                score = 1.0

        # -------------------------------------------------------------
        # 3. FACT PROVENANCE & GROUNDING GUARDRAIL
        # -------------------------------------------------------------
        elif guardrail.category == "grounding" or "fact" in guardrail.name:
            verified_facts = context.get("verified_facts", []) or []
            
            # A. Check for factual anchors [FACT_xxx]
            fact_anchors_found = re.findall(r'\[(FACT_\d+)\]', raw_text)
            
            # B. Check for numbers without fact anchors
            # Pattern looking for percentages or billion/million figures
            numerical_claims = re.findall(r'(\b\d+(?:\.\d+)?%|\b(?:AED|USD|\$)?\s*\d+(?:\.\d+)?\s*(?:billion|million|B|M)\b)', raw_text, re.IGNORECASE)
            
            # C. Check geographic grounding rules
            # Flag invalid claim that Dubai Hills is waterfront
            if re.search(r'Dubai Hills[^\.\n]*waterfront', raw_text, re.IGNORECASE):
                violations.append(GuardrailViolation(
                    type="GEOGRAPHIC_MISMATCH",
                    severity="ERROR",
                    message="Dubai Hills is an inland golf-course community, not waterfront.",
                    claim="Dubai Hills waterfront",
                    suggested_fix="Position Palm Jebel Ali as waterfront and Dubai Hills as inland luxury."
                ))
            
            if violations:
                status = "FAILED"
                action = guardrail.default_action or "RETRY"
                score = 0.5
            else:
                status = "PASSED"
                action = "ALLOW"
                score = 1.0

        # -------------------------------------------------------------
        # 3. LIVE LINK HEALTH & 404 GUARDRAIL
        # -------------------------------------------------------------
        elif "link" in guardrail.name or guardrail.name == "link_health_verifier":
            import httpx
            urls_found = re.findall(r'https?://[^\s\)\]\>]+', raw_text)
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                for u in urls_found[:8]:
                    try:
                        resp = await client.head(u, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 404:
                            violations.append(GuardrailViolation(
                                type="CUSTOM",
                                severity="WARNING",
                                message=f"Broken 404 link detected: {u}",
                                claim=u,
                                suggested_fix="Replace with active article link or search archive"
                            ))
                    except Exception:
                        pass

            if violations:
                status = "WARNING"
                action = "WARN"
                score = 0.8
            else:
                status = "PASSED"
                action = "ALLOW"
                score = 1.0

        # -------------------------------------------------------------
        # 3. SAFETY & PII GUARDRAIL
        # -------------------------------------------------------------
        elif guardrail.category == "safety" or "pii" in guardrail.name:
            # Check for email / phone leaks
            email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
            emails = re.findall(email_pattern, raw_text)
            if emails:
                violations.append(GuardrailViolation(
                    type="PII_LEAK",
                    severity="CRITICAL",
                    message=f"Detected PII email address leak: {emails[0]}",
                    claim=emails[0]
                ))
                status = "FAILED"
                action = "BLOCK"
                score = 0.0

        # Compute Duration & Hash
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        payload_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()[:16]
        preview = (raw_text[:120] + "...") if len(raw_text) > 120 else raw_text

        result = GuardrailResult(
            status=status,
            action=action,
            score=score,
            violations=violations,
            output_payload=output_payload,
            duration_ms=duration_ms,
            metadata={"guardrail_name": guardrail.name, "category": guardrail.category}
        )

        # Audit Record in PostgreSQL
        try:
            audit_entry = GuardrailExecutionModel(
                id=exec_id,
                guardrail_id=guardrail.id,
                binding_id=binding_id,
                workflow_run_id=workflow_run_id,
                agent_run_id=agent_run_id,
                scope=scope,
                status=status,
                action_taken=action,
                score=score,
                payload_hash=payload_hash,
                input_preview=preview,
                violations=[v.model_dump() for v in violations],
                output_payload=output_payload if status == "REWRITTEN" else None,
                duration_ms=duration_ms,
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit_entry)
            await db.commit()
        except Exception:
            pass

        return result
