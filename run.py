#!/usr/bin/env python3
"""Entry point: uvicorn server for the BitAxe dashboard."""

import uvicorn

from app import config

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT)
