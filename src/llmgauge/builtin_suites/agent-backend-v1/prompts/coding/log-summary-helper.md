# Agent Backend Test: Log Summary Helper

You are acting as the language model backend for a local coding agent.

The user wants a small Python script that reads a log file and prints:

- total lines
- count of lines containing ERROR
- count of lines containing WARNING
- the last 5 ERROR lines

Task:

Write the script.

Requirements:

- Use only the Python standard library.
- Accept the log path as a command-line argument.
- Handle missing files cleanly.
- Do not load huge files entirely into memory.
- Include a short usage example.
