from datetime import datetime
import re
import subprocess
import json

from langchain_ollama import ChatOllama


def get_os_info():
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' | Select-Object ProductName, DisplayVersion, CurrentBuild, UBR"],
        capture_output=True,
        text=True
    )
    return result.stdout


def get_installed_updates():
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-HotFix | Select-Object HotFixID, Description, InstalledOn | Sort-Object InstalledOn -Descending"],
        capture_output=True,
        text=True
    )
    return result.stdout


def get_firewall_status():
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-NetFirewallProfile | Select-Object Name, Enabled"],
        capture_output=True,
        text=True
    )
    return result.stdout


def get_demo_network_data():
    return """[SIMULATED DATA - no live devices found or router unreachable]
IP Address       Device Type        Status
-----------      -----------        ------
192.168.1.1      Router (Nokia)     Online
192.168.1.10     Desktop PC         Online
192.168.1.15     Printer            Online
192.168.1.20     Unknown Device     Online"""


def discover_network_devices():
    result = subprocess.run(
        ["powershell", "-Command", "arp -a"],
        capture_output=True,
        text=True
    )
    output = result.stdout
    if not output.strip() or len(output.strip().splitlines()) < 3:
        return get_demo_network_data()
    return output


def load_controls():
    with open("controls.json", "r") as f:
        return json.load(f)


def run_audit(os_info, updates, firewall, network):
    controls = load_controls()
    results = []

    for control in controls:
        if control["id"] == "ID-01":
            status = "Devices found" if network.strip() else "No devices found"
            results.append({**control, "result": status, "evidence": network})

        elif control["id"] == "ID-03":
            results.append({**control, "result": "Collected", "evidence": os_info})

        elif control["id"] == "ID-05":
            results.append({**control, "result": "Collected", "evidence": updates})

        elif control["id"] == "PR-05":
            all_enabled = "False" not in firewall
            status = "PASS - All profiles enabled" if all_enabled else "FAIL - One or more profiles disabled"
            results.append({**control, "result": status, "evidence": firewall})

        elif control["id"] == "DE-03":
            results.append({**control, "result": "Collected", "evidence": network})

        else:
            results.append({**control, "result": "Not yet evaluated", "evidence": None})

    return results


def calculate_days_since_last_update(updates_text):
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', updates_text)
    if not dates:
        return None

    most_recent = max(datetime.strptime(d, "%Y-%m-%d") for d in dates)
    days_since = (datetime.now() - most_recent).days
    return days_since


def run_risk_agent(audit_results):
    llm = ChatOllama(model="llama3.2", temperature=0)
    risk_assessed = []

    for result in audit_results:
        if result["result"] in ("Collected", "PASS - All profiles enabled", "Devices found"):

            extra_context = ""
            if result["id"] == "ID-05":
                days_since = calculate_days_since_last_update(result["evidence"])
                if days_since is not None:
                    extra_context = (
                        f"\nIMPORTANT VERIFIED FACT: Today's date is "
                        f"{datetime.now().strftime('%Y-%m-%d')}. It has been exactly "
                        f"{days_since} days since the most recent update was installed. "
                        f"Base your risk assessment on this fact, not on your own date interpretation."
                    )

            prompt = f"""You are a security risk analyst reviewing an SMB IT audit finding.

Control: {result['description']}
Result: {result['result']}
Evidence: {result['evidence']}
{extra_context}

In 1-2 sentences, assess the security risk level (Low, Medium, High, or Critical) and briefly explain why.
Respond in this exact format:
RISK: <level>
REASON: <explanation>"""

            response = llm.invoke(prompt)
            risk_assessed.append({**result, "risk_assessment": response.content})
        else:
            risk_assessed.append({**result, "risk_assessment": None})

    return risk_assessed


def write_log_file(os_info, updates, firewall, network, audit_results, risk_results):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"audit_log_{timestamp}.txt"

    with open(filename, "w") as f:
        f.write("=== OS INFO ===\n" + os_info + "\n")
        f.write("=== INSTALLED UPDATES ===\n" + updates + "\n")
        f.write("=== FIREWALL STATUS ===\n" + firewall + "\n")
        f.write("=== NETWORK DEVICES ===\n" + network + "\n")

        f.write("=== FULL AUDIT RESULTS (all 42 controls) ===\n")
        for r in audit_results:
            f.write(f"{r['id']} | {r['description']} | Result: {r['result']}\n")

        f.write("\n=== RISK ASSESSMENTS ===\n")
        for r in risk_results:
            if r["risk_assessment"]:
                f.write(f"\n{r['id']} | {r['description']}\n{r['risk_assessment']}\n")

    return filename


def print_summary(risk_results):
    evaluated = [r for r in risk_results if r["risk_assessment"]]
    total_controls = len(risk_results)

    print(f"\nSECURITY POSTURE SUMMARY")
    print(f"{'=' * 40}")
    print(f"Controls evaluated: {len(evaluated)} of {total_controls}")
    print()

    for r in evaluated:
        risk_line = r["risk_assessment"].split("\n")[0]
        risk_level = risk_line.replace("RISK:", "").strip()
        print(f"[{risk_level.upper()}] {r['description']}")

    print(f"\nFull technical details saved to log file.")


if __name__ == "__main__":
    os_info = get_os_info()
    updates = get_installed_updates()
    firewall = get_firewall_status()
    network = discover_network_devices()

    audit_results = run_audit(os_info, updates, firewall, network)
    risk_results = run_risk_agent(audit_results)

    log_filename = write_log_file(os_info, updates, firewall, network, audit_results, risk_results)
    print_summary(risk_results)
    print(f"(Detailed log written to: {log_filename})")