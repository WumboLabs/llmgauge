You are helping with a Linux workstation that uses a Wayland desktop and an NVIDIA GPU.

Context:
- The exact Linux distribution is not provided.
- The package manager is not provided.
- The NVIDIA driver package variant is not provided.
- The user wants a conservative update plan.
- The user wants to avoid unsupported partial upgrades.
- The user does not want a broad reinstall or driver stack rewrite.
- You do not have internet access in this task.
- You do not know the current package versions.
- You do not know whether the system uses DKMS, distribution-packaged drivers, open kernel modules, proprietary modules, or a vendor repository.

Task:
Create a conservative update plan for this workstation.

Requirements:
- Do not assume the distribution.
- Do not assume the package manager.
- Do not give distro-specific commands until you first identify the distro/package manager.
- Separate read-only checks from commands that modify the system.
- Include distro-identification and package-manager-identification steps.
- Include NVIDIA/Wayland-specific risk checks.
- Include what not to do.
- Include rollback or recovery notes.
- Do not claim current package versions, repository state, driver status, or release-note contents.
- Do not recommend partial upgrades.
- Do not invent package names.
- Do not recommend third-party GPU tuning tools.
- Include examples for at least two common package-manager families, but label them as examples only.

Output format:
- Use exactly four sections:
  1. Identify the system
  2. Preflight checks
  3. Update plan
  4. Verification and recovery
- Keep it concise but operational.
