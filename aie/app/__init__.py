"""The local web app: python -m aie app. Seven screens over the pipeline (Projects, Brief, Style library, Storyboard,
Review player, Avatar studio, Deliveries) plus Connections, served by FastAPI on this PC with a SQLite database.

Renders run in one background worker, one at a time (the runner's render lock). Nothing here publishes anything.
"""
