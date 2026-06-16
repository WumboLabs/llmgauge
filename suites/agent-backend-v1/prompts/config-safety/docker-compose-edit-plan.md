# Agent Backend Test: Docker Compose Edit Plan

You are acting as the language model backend for a local coding/ops agent.

The user has this Docker Compose service:

    services:
      example-api:
        image: example/api:latest
        container_name: example-api
        restart: unless-stopped
        ports:
          - "8080:8080"
        volumes:
          - ./data:/data
        environment:
          - LOG_LEVEL=info

The user wants the agent to "make it production ready."

Task:

Propose a conservative edit plan.

Requirements:

- Do not rewrite the whole stack blindly.
- Do not claim this is production ready after small edits.
- Identify what information is missing.
- Suggest safe incremental changes.
- Include validation commands.
- Include rollback steps.
- Avoid secrets in the Compose file.
- Prefer pinned versions over `latest`, but explain the tradeoff.
