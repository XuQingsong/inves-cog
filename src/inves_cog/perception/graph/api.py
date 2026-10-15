"""Review API for internal callers; M10 owns rendering and deployment."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    relation_ids: list[str] = Field(min_length=1)
    action: str
    edits: dict | None = None
    expected_revisions: dict | None = None


def create_app(*, repository, clock):
    app = FastAPI(title="Graph candidate review")

    @app.get("/graph/candidates")
    def candidates(basket: str | None = None):
        return repository.candidates(basket)

    @app.post("/graph/review")
    def review(body: ReviewRequest):
        try:
            return repository.review(
                body.relation_ids,
                action=body.action,
                edits=body.edits,
                expected_revisions=body.expected_revisions,
                clock=clock,
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app
