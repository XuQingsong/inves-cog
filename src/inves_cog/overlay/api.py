"""Read-only HTTP delivery; no endpoint can alter an overlay or order."""

from datetime import date

from fastapi import FastAPI, HTTPException


def create_app(delivery):
    app = FastAPI()

    @app.get("/api/linkage/overlay")
    def overlay(date: date):
        payload = delivery.read(date.isoformat())
        if payload is None:
            raise HTTPException(status_code=404, detail="覆盖层未接通")
        return payload

    return app
