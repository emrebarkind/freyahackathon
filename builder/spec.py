"""Typed intermediate representations passed between builder stages."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Stage 1: brief -> policy -------------------------------------------------
class Variable(BaseModel):
    name: str = Field(description="snake_case; used as {{name}} in the prompt")
    description: str
    example: str


class Rule(BaseModel):
    id: str = Field(description="Stable id like R01")
    kind: Literal["must", "must_not", "conditional"]
    trigger: str = Field(description="When it applies ('always' if unconditional)")
    action: str = Field(description="Exactly what the agent must / must not do")
    source_quote: str = Field(description="Verbatim sentence from the brief this comes from")


class Outcome(BaseModel):
    code: str = Field(description="UPPER_SNAKE disposition code, e.g. PROMISE_TO_PAY")
    when: str = Field(description="Precise condition for ending the call with this outcome")
    agent_must_say_or_do: str = Field(description="Closing behaviour required for this outcome")


class Policy(BaseModel):
    bank_name: str
    agent_persona: str = Field(description="Agent name, role and tone, as the brief implies")
    language: str = Field(description="ISO code of the call language, e.g. en or tr")
    objective: str
    variables: list[Variable]
    call_flow: list[str] = Field(description="Ordered high-level steps of the ideal call")
    rules: list[Rule] = Field(description="Every atomic, testable rule. Prefer many small rules over a few vague ones.")
    outcomes: list[Outcome]
    numeric_limits: list[str] = Field(description="Every number/threshold/date constraint, verbatim")
    ambiguities: list[str] = Field(description="Gaps or conflicts in the brief and the conservative interpretation chosen")


# ---------- Stage 2: policy -> scenarios ---------------------------------------------
class VarValue(BaseModel):
    name: str
    value: str


class Scenario(BaseModel):
    id: str
    title: str
    persona: str = Field(description="Second-person instructions for the simulated customer: who they are, mood, hidden facts, how they react. Never reveal expected outcome.")
    variable_values: list[VarValue] = Field(description="A value for every policy variable")
    expected_outcome: str = Field(description="One of the policy outcome codes")
    must: list[str] = Field(description="Observable agent behaviours required to pass")
    must_not: list[str] = Field(description="Observable agent behaviours that fail the case")
    rule_ids: list[str]

    @property
    def variables(self) -> dict[str, str]:
        return {v.name: v.value for v in self.variable_values}


class ScenarioSet(BaseModel):
    scenarios: list[Scenario]


# ---------- Stage 3: policy -> agent -------------------------------------------------
class AgentDraft(BaseModel):
    name: str
    system_prompt: str
    first_message: str = Field(description="Opening line; may contain {{variables}}")
    farewell_message: str
    changelog: str = Field(default="", description="What changed vs the previous version and why")


# ---------- Stage 4: evaluation -------------------------------------------------------
class Verdict(BaseModel):
    outcome_detected: str
    passed: bool
    violated: list[str] = Field(description="Failed must / must_not items or rule ids, quoted")
    reasoning: str


class CaseResult(BaseModel):
    scenario_id: str
    transcript: list[dict]
    verdict: Verdict
