from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


EdgeType = Literal["prerequisite", "encompassing"]
QuestionType = Literal["mcq", "short"]


class Topic(BaseModel):
    id: str
    title: str
    description: str
    cluster: str
    grade_level: int = Field(ge=1, le=12)
    order_index: int = Field(ge=0)
    difficulty_prior: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class TopicEdge(BaseModel):
    id: str
    from_topic_id: str
    to_topic_id: str
    edge_type: EdgeType
    weight: float = Field(ge=0.0, le=1.0)


class Question(BaseModel):
    id: str
    prompt: str
    question_type: QuestionType
    choices: list[str] = Field(default_factory=list)
    correct_answer: str

    primary_topic_id: str
    secondary_topic_ids: list[str] = Field(default_factory=list)

    difficulty_prior: float = Field(ge=0.0, le=1.0)
    conceptual_load: float = Field(ge=0.0, le=1.0)
    procedural_load: float = Field(ge=0.0, le=1.0)
    transfer_load: float = Field(ge=0.0, le=1.0)
    diagnostic_value: float = Field(ge=0.0, le=1.0)

    tags: list[str] = Field(default_factory=list)


class Student(BaseModel):
    id: str
    display_name: str
    created_at: datetime


class Attempt(BaseModel):
    id: str
    student_id: str
    question_id: str
    topic_id: str

    correctness: bool
    time_taken_seconds: int = Field(ge=0)
    hints_used: int = Field(ge=0)
    confidence_rating: int = Field(ge=1, le=5)
    self_report_reason: Optional[str] = None
    submitted_at: datetime


class StudentTopicState(BaseModel):
    student_id: str
    topic_id: str

    mastery_score: float = Field(ge=0.0, le=1.0)
    fragility_score: float = Field(ge=0.0, le=1.0)
    fluency_score: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    last_updated_at: datetime

