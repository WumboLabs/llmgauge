A Linux workstation has Docker containers that cannot resolve DNS after an nftables change.

Known clues:
- Docker uses bridge networking.
- The nftables forward policy may be dropping traffic.
- DNS worked before firewall changes.

Task:
Give a conservative troubleshooting procedure.

Requirements:
- Separate observation, diagnosis, and action.
- Include verification commands.
- Avoid broad destructive firewall resets.
- Include rollback awareness.
