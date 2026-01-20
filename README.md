
# CrewAI Terraform Generator (Local Use)

This project uses [CrewAI](https://docs.crewai.com/) agents to generate Terraform modules from official Terraform Registry markdown files. This README documents local setup and usage only.

---

## 📁 Structure

```
.
├── 1_generate_schema.py              # Download Terraform provider schema
├── 2_extract_schema_and_wiki.py      # Download markdown and store it locally
├── 3_crew_terraform.py               # Run agents to generate a Terraform module
├── modules/                          # Output folder for generated Terraform modules (ignored)
├── schemas/                          # Provider JSON schemas (ignored)
├── wiki/                             # Downloaded markdown inputs (ignored)
├── .gitignore
├── requirements.txt
├── venv/                             # Python virtual environment (ignored)
```

---

## 🧰 Prerequisites

- Python 3.11+
- An OpenAI API key set as an environment variable or in a local `.env` file

---

## 🛠️ Setup (Windows PowerShell)

```powershell
# From the project root
py -3.11 -m venv .\venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure OpenAI key (see below)
```

Mac/Linux activation alternative:

```bash
source venv/bin/activate
```

### API Key Configuration

**Recommended:** Store your key in a local `.env` file in the project root:

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

This method is more reliable than setting the environment variable directly in PowerShell, as it persists across sessions and avoids issues with variable scope.

Alternatively, you can set it as a PowerShell session variable (less reliable):

```powershell
$env:OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## 🚀 Usage

1. Download the provider schema
   ```bash
   python 1_generate_schema.py hashicorp azurerm 3.116.0
   ```

2. Download the resource markdown and extract inputs
   ```bash
   python 2_extract_schema_and_wiki.py hashicorp azurerm 3.116.0 azurerm_static_web_app
   ```

3. Generate the Terraform module with CrewAI
   ```bash
   python 3_crew_terraform.py hashicorp azurerm 3.116.0 azurerm_static_web_app
   ```

---

## 📦 Output

- Generated modules are written to the modules/ folder.
- Variable descriptions are sourced directly from the Terraform Registry markdown.

---

## ✅ Notes

- The folders modules/, schemas/, and wiki/ are kept locally and excluded from version control via .gitignore.
- Ensure your environment is activated before running any scripts.
