# Agentic-AI
Agentic AI for small businesses


# Agentic SMB Security Posture Auditor

An autonomous, multi-agent system that audits a small business's IT environment against the NIST Cybersecurity Framework (CSF) 2.0, and produces a plain-English risk report a non-technical business owner can actually understand.

This project turns a real IT security consulting audit process (originally a manual 42-control checklist) into a semi-automated pipeline: real system scanning → rule-based control matching → LLM-driven risk reasoning → human-readable summary.

## Why this project exists

Most "agentic AI" demos wrap an LLM around a trivial task. This project deliberately does the opposite: it starts from a real-world, domain-specific process (a NIST CSF-aligned security audit) and automates the parts that can genuinely be automated, while being explicit and honest about the parts that still require human judgment.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│  Scanner Agent   │ --> │ Audit Engine │ --> │  Risk Agent   │ --> │  Output Layer     │
│ (real system     │     │ (matches raw │     │ (LLM reasons  │     │ - Console summary │
│  + network data) │     │  data to the │     │  about        │     │ - Full detail log │
│                  │     │  42 controls)│     │  severity)    │     │                    │
└─────────────────┘     └──────────────┘     └───────────────┘     └──────────────────┘
```

**Scanner Agent** — collects real data from the host machine and local network:
- OS version and build number (via Windows Registry)
- Installed update/patch history (via `Get-HotFix`)
- Host firewall status (via `Get-NetFirewallProfile`)
- Network device discovery (via ARP table), with a clearly-labeled simulated-data fallback for environments where live discovery isn't possible (e.g. consumer routers without SSH/SNMP access)

**Audit Engine** — matches scanner output against a digitized version of a 42-control NIST CSF 2.0 checklist (`controls.json`). Each control is tagged `automated`, `planned`, or `manual`, making clear exactly what this tool can and cannot verify today.

**Risk Agent** — for every control with real evidence, an LLM (running locally via Ollama, or optionally via the Anthropic API for higher-quality runs) assesses risk severity (Low/Medium/High/Critical) with a plain-English justification.

**Output Layer** — a short, readable summary is printed to the console for a business owner; the full technical detail (raw scan data, every control's status, full LLM reasoning) is written to a timestamped log file for anyone who needs to dig deeper.

## Tech stack

- **Python 3.14** — core language
- **PowerShell** (invoked from Python via `subprocess`) — real system/network data collection on Windows
- **LangGraph / LangChain** — agent orchestration framework (in progress — see Roadmap)
- **Ollama (llama3.2)** — local LLM inference for development and testing, at no API cost
- **Anthropic API (Claude)** — planned for polished final demo runs
- **NIST CSF 2.0** — the control framework the audit logic is built on

## Setup

1. Clone this repo and navigate into it.
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```
   pip install langgraph langchain-anthropic langchain-ollama
   ```
4. Install [Ollama](https://ollama.com) and pull a local model:
   ```
   ollama run llama3.2
   ```
5. Run the auditor:
   ```
   python scanner.py
   ```

Console output gives a plain-English summary. A detailed `audit_log_<timestamp>.txt` file is written to the project folder for every run.

## Real findings from building this

Building this surfaced several genuine, non-obvious issues that are documented here because working through them was as valuable as the code itself:

1. **`Get-ComputerInfo` reported the wrong OS entirely.** On a confirmed clean install of Windows 11 23H2, this cmdlet reported "Windows 10 Pro" and an unrelated version label ("2009"). Switched to reading directly from the registry (`HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`), which is what Windows Settings itself uses, more reliable, though even this registry value still literally stores `ProductName: Windows 10 Pro` on this machine, a known long-standing Microsoft inconsistency rather than a bug in this code.

2. **`Get-HotFix` under-reports installed updates.** It only surfaced updates through a certain date, while the actual Windows Update history (visible in Settings) showed real updates installed weeks later — meaning `Get-HotFix` misses certain update types (e.g. some .NET and cumulative updates). Flagged as a known limitation; a more complete implementation would also read the Windows Update log directly.

3. **LLMs cannot reliably reason about elapsed time from raw dates alone.** In an early version, the Risk Agent was given a raw "last updated: 2026-05-22" string and confidently — and incorrectly — assessed the patch status as "up to date," despite the date being months in the past. LLMs don't inherently know today's date or reliably compute date arithmetic from text. Fixed by calculating the exact day-count in Python (deterministic, always correct) and explicitly injecting it into the prompt as a verified fact, rather than letting the model infer it.

4. **Even with a correct verified fact, an LLM can still misstate a secondary detail.** After the date fix above, the Risk Agent correctly flagged the 113-day patch gap as Medium risk — but still referred to the wrong record as "the most recent update" in its written explanation. This is a good illustration of why LLM output in a serious tool needs structured, verifiable facts for anything safety/compliance-critical, and why free-text LLM reasoning should be treated as explanatory narrative, not as the source of truth for hard facts.

## Roadmap

- [ ] Wire the pipeline together with LangGraph as an explicit agent graph (currently a sequential script)
- [ ] Add a dedicated Report Agent to generate a polished, client-ready written report (PDF/HTML)
- [ ] Expand automated coverage beyond the current 5 of 42 controls (installed software inventory, MFA status, endpoint protection status, etc.)
- [ ] Attempt real router/switch config pulls where hardware supports SSH/SNMP (currently falls back to simulated data on consumer-grade routers)
- [ ] Package with Docker for portable deployment

## Disclaimer

This tool is a portfolio/learning project. The NIST CSF 2.0-aligned checklist and output are for demonstration and internal review purposes and do not constitute a certified compliance audit.
