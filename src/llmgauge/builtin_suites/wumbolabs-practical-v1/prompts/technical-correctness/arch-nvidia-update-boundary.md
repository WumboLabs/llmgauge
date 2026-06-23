You are helping with an Arch Linux workstation that uses Sway/Wayland and an NVIDIA GPU.

Context:
- The machine is called WumboJetsII.
- It uses Arch Linux.
- The user prefers conservative full-system upgrades.
- The user wants to avoid unsupported partial upgrades.
- The user wants to check Arch Linux News before upgrading.
- The user uses `paru` for AUR only when needed.
- The user does not want a broad reinstall or driver stack rewrite.
- You do not have internet access in this task.
- You do not know the current package versions.

Task:
Create a conservative update plan for this workstation.

Requirements:
- Separate read-only checks from commands that modify the system.
- Include the Arch News check as a required manual step.
- Include NVIDIA/Wayland-specific risk checks.
- Include what not to do.
- Include rollback or recovery notes.
- Do not claim current package versions, current Arch News contents, or current NVIDIA driver status.
- Do not recommend partial upgrades.
- Do not tell the user to blindly run an AUR upgrade before official repo checks.

Output format:
- Use exactly four sections:
  1. Preflight
  2. Upgrade
  3. Verification
  4. Rollback / Recovery
- Keep it concise but operational.
