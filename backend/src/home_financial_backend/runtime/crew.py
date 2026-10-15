from importlib.resources import files
from typing import Any

import yaml
from crewai import Agent, Crew, Process, Task

from home_financial_backend.domain.models import InsightCard
from home_financial_backend.runtime.contracts import ClassificationCandidate


def _load_config(filename: str) -> dict[str, Any]:
    config_path = files("home_financial_backend").joinpath("config", filename)
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def build_classification_crew(llm: Any) -> Crew:
    agents = _load_config("agents.yaml")
    tasks = _load_config("tasks.yaml")
    agent = Agent(config=agents["categorization_agent"], llm=llm, verbose=False)
    task = Task(
        **tasks["classification_task"],
        agent=agent,
        output_pydantic=ClassificationCandidate,
    )
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        max_rpm=6,
        verbose=False,
    )


def build_insight_crew(llm: Any) -> Crew:
    agents = _load_config("agents.yaml")
    tasks = _load_config("tasks.yaml")
    agent = Agent(config=agents["insight_agent"], llm=llm, verbose=False)
    task = Task(
        **tasks["insight_task"],
        agent=agent,
        output_pydantic=InsightCard,
    )
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        max_rpm=6,
        verbose=False,
    )
