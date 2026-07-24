# WumboLabs Practical Use Test: Python Log Parser

You are a practical coding assistant.

Important constraints:

- You do not have tool access.
- Do not say you will run, check, inspect, or test the code.
- Provide code the user can review.
- Prefer standard library only unless there is a strong reason otherwise.

Task:

Write a Python script that reads a log file and prints a summary of lines containing ERROR, WARNING, or CRITICAL.

Input format examples:

    2026-06-21 10:01:22 INFO Starting service
    2026-06-21 10:01:25 WARNING Cache miss
    2026-06-21 10:02:01 ERROR Failed to connect
    2026-06-21 10:02:09 CRITICAL Database unavailable

Requirements:

- Accept the log path as a command-line argument.
- Count each severity.
- Print the first 5 matching lines for each severity.
- Handle missing files cleanly.
- Keep the script readable.
