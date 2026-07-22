SYSTEM:

You are a conservative local systems assistant. Prefer safe, reversible, verified steps. Say when unsure. Do not invent commands, packages, flags, or docs.

USER:

# WumboLabs Practical Use Test: Docker Compose Review

You are a practical self-hosting assistant.

Important constraints:

- You do not have tool access.
- Do not say you will run, check, inspect, or edit files.
- Review only the provided Compose snippet.
- Do not invent services, networks, files, or environment variables.
- Give specific, useful feedback.

Compose snippet:

    services:
      app:
        image: example/app:latest
        container_name: example-app
        ports:
          - "8080:80"
        volumes:
          - .REDACTED_ABSOLUTE_PATH
          - REDACTED_ABSOLUTE_PATH
        environment:
          - PUID=1000
          - PGID=1000
        restart: always

Task:

Review this Compose snippet for practical self-hosting risks and improvements.

Requirements:

- Identify security concerns.
- Identify reproducibility concerns.
- Identify operational concerns.
- Suggest safer alternatives where appropriate.
- Do not overstate certainty.