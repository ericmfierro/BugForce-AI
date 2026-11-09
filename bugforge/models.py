"""Validated data contracts shared by the AI and the executor."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator

ActionName = Literal['save_report', 'create_ticket', 'publish_github_issue']
Severity = Literal['Critical', 'High', 'Medium', 'Low']
Category = Literal['Gameplay', 'Performance', 'UI/UX', 'Networking', 'Audio', 'Graphics', 'Crash', 'Other']


class BugReport(BaseModel):
    title: str = Field(min_length=8, max_length=140)
    summary: str = Field(min_length=12, max_length=1500)
    category: Category
    severity: Severity
    severity_reason: str = Field(min_length=8, max_length=450)
    steps_to_reproduce: list[str] = Field(min_length=1, max_length=8)
    expected_behavior: str = Field(min_length=5, max_length=700)
    actual_behavior: str = Field(min_length=5, max_length=700)
    possible_cause: str = Field(max_length=650)
    suggested_tests: list[str] = Field(min_length=1, max_length=6)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=5)
    tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator('steps_to_reproduce', 'suggested_tests')
    @classmethod
    def no_empty_items(cls, values: list[str]) -> list[str]:
        if any(not item.strip() for item in values):
            raise ValueError('List items must not be empty.')
        return values


class ActionRequest(BaseModel):
    name: ActionName
    reason: str = Field(min_length=4, max_length=300)


class AgentPlan(BaseModel):
    report: BugReport
    actions: list[ActionRequest] = Field(default_factory=list, max_length=3)
    explanation: str = Field(min_length=8, max_length=800)

    @field_validator('actions')
    @classmethod
    def unique_actions(cls, actions: list[ActionRequest]) -> list[ActionRequest]:
        names = [item.name for item in actions]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate actions are not permitted.')
        return actions
