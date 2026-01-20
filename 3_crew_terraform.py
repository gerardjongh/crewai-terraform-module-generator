import os
import sys
import json
import re
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

# -------------------------------
# Clean up generated content
# -------------------------------
def clean_content(content):
    content = re.sub(r"```(?:.*?\n)?(.*?)```", r"\1", content, flags=re.DOTALL)
    content = content.replace("`", "")
    content = re.sub(r'/\*\*.*?\*/', '', content, flags=re.DOTALL).strip()
    content = re.sub(r'[\u200b\u200c\u200d\uFEFF\u00A0]', '', content).strip()
    content = content.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    content = content.encode('utf-8-sig', 'ignore').decode('utf-8-sig').strip()
    return content

# -------------------------------
# CLI arguments: provider, version, resource type
# -------------------------------
if len(sys.argv) != 5:
    print("Usage: python 3_crew_terraform.py <provider_supplier> <provider_name> <provider_version> <resource_type>")
    sys.exit(1)

provider_supplier = sys.argv[1]
provider_name = sys.argv[2]
provider_version = sys.argv[3]
resource_type = sys.argv[4]

# -------------------------------
# Load preprocessed schema
# -------------------------------
schema_path = os.path.join("schemas", f"{resource_type}.json")
if not os.path.isfile(schema_path):
    print(f"❌ Schema file not found: {schema_path}")
    sys.exit(1)

with open(schema_path, "r", encoding="utf-8") as f:
    schema = json.load(f)

arguments = schema.get("arguments", [])
block_tree = schema.get("block_tree", [])

# -------------------------------
# Load markdown reference
# -------------------------------
short_name = resource_type.replace(f"{provider_name}_", "")
markdown_file = os.path.join("wiki", f"{short_name}.html.markdown")
if not os.path.isfile(markdown_file):
    print(f"❌ Markdown file not found: {markdown_file}")
    sys.exit(1)

with open(markdown_file, "r", encoding="utf-8") as f:
    markdown_content = f.read()

# -------------------------------
# LLM context input (prompt base)
# -------------------------------
schema_summary = f"You are generating Terraform code for resource {resource_type}.\nArguments:\n"
for arg in arguments:
    required = "required" if arg['required'] else "optional"
    schema_summary += f"- {arg['name']} ({required})\n"

def format_block_tree(blocks, indent=0):
    lines = []
    for block in blocks:
        lines.append("  " * indent + f"- {block['name']} (min_items={block['min_items']})")
        for attr in block.get("attributes", []):
            required = "required" if attr.get("required") else "optional"
            lines.append("  " * (indent + 1) + f"- {attr['name']} ({required})")
        if block.get("blocks"):
            lines.extend(format_block_tree(block["blocks"], indent + 1))
    return lines

schema_summary += "\nNested Block Tree:\n" + "\n".join(format_block_tree(block_tree))

llm = ChatOpenAI(model="gpt-5", temperature=1)

# -------------------------------
# AGENT: variables.tf
# -------------------------------
variables_agent = Agent(
    role='Terraform Variables Generator',
    goal='Generate variables.tf with exact schema descriptions',
    backstory="You generate clean, accurate Terraform variable definitions based on schema structure and exact markdown documentation.",
    allow_delegation=False,
    llm=llm
)

variables_task = Task(
    description=(
        f"{schema_summary}\n\n"
        "Use the markdown below to extract the exact description text for each argument and block.\n"
        "\n"
        "--- START MARKDOWN ---\n"
        f"{markdown_content}\n"
        "--- END MARKDOWN ---\n"
        "\n"
        "Instructions for generating variables.tf:\n"
        "\n"
        "1. VARIABLE INCLUSION:\n"
        "   - Generate a valid `variables.tf` file\n"
        "   - Include ALL variables from the schema, both required and optional\n"
        "   - Do NOT include the Timeouts block as a variable\n"
        "\n"
        "2. VARIABLE TYPES:\n"
        "   - Use the correct Terraform type for each variable based on the schema\n"
        "   - For simple types: use `string`, `number`, `bool`\n"
        "   - For nested structures: use `object({...})` or `list(object({...}))`\n"
        "   - For maps: use `map(string)`, `map(object({...}))`, etc.\n"
        "   - For lists: use `list(string)`, `list(object({...}))`, etc.\n"
        "\n"
        "3. DEFAULT VALUES:\n"
        "   - All optional variables MUST have a default value\n"
        "   - Required variables must NOT have a default value\n"
        "   - Default values by type:\n"
        "     * Optional string variables: `default = null`\n"
        "     * Optional number variables: `default = null`\n"
        "     * Optional bool variables: `default = null`\n"
        "     * Optional object variables: `default = {{}}`\n"
        "     * Optional map variables: `default = {{}}`\n"
        "     * Optional list variables: `default = []`\n"
        "\n"
        "4. OBJECT AND MAP DEFINITIONS:\n"
        "   - When defining `object()` types, wrap each property with `optional()` if that property does not require input\n"
        "   - Example: `object({{name = string, location = optional(string), tags = optional(map(string))}})`\n"
        "   - For nested objects, apply `optional()` consistently at each nesting level\n"
        "\n"
        "5. DESCRIPTIONS:\n"
        "   - Every variable MUST have a `description` property\n"
        "   - Copy the description text EXACTLY from the markdown documentation\n"
        "   - The `description` property MUST be the LAST property in each variable block\n"
        "   - For simple variables (string, number, bool, simple lists): use single-line or standard multi-line descriptions\n"
        "   - For complex variables (objects, maps with multiple properties): use extensive descriptions with the format:\n"
        "     description = <<DESCRIPTION\n"
        "     [Main description from markdown]\n"
        "     Properties:\n"
        "     - property_name: description of this property\n"
        "     - nested_property: description of nested property\n"
        "     DESCRIPTION\n"
        "   - The markers `<<DESCRIPTION` and `DESCRIPTION` are LITERAL text to be used\n"
        "\n"
        "6. FORMATTING:\n"
        "   - Use consistent indentation (2 spaces per level)\n"
        "   - Place each variable in a separate `variable` block\n"
        "   - Order variables logically: required variables first, then optional variables\n"
        "   - Do NOT include any comments in the code\n"
        "\n"
        "7. OUTPUT REQUIREMENTS:\n"
        "   - Output ONLY raw Terraform HCL code\n"
        "   - Do NOT wrap the output in markdown code blocks (no ```, no backticks)\n"
        "   - Do NOT include any commentary, explanations, or extra text\n"
        "   - The output should be ready to write directly to a .tf file"
    ),
    expected_output="Clean variables.tf with exact schema and literal description match.",
    agent=variables_agent
)

# -------------------------------
# AGENT: main.tf
# -------------------------------
main_agent = Agent(
    role='Terraform Main Generator',
    goal='Generate main.tf file referencing variables correctly',
    backstory="You create a valid main.tf file.",
    allow_delegation=False,
    llm=llm
)

main_task = Task(
    description=(
        f"{schema_summary}\n\n"
        f"Generate a valid Terraform `main.tf` file that creates the resource {resource_type}.\n"
        "\n"
        "Instructions for generating main.tf:\n"
        "\n"
        "1. RESOURCE DEFINITION:\n"
        "   - Create a single resource block for the resource type\n"
        "   - Do NOT include a provider block or provider configuration\n"
        "   - Do NOT include the Timeouts block\n"
        "\n"
        "2. RESOURCE NAMING (CAF CONVENTIONS):\n"
        "   - The resource label (local identifier after the resource type) MUST use the exact abbreviation from Microsoft's Cloud Adoption Framework (CAF)\n"
        "   - Find the abbreviation by matching the Azure resource type in the official CAF documentation:\n"
        "     https://raw.githubusercontent.com/MicrosoftDocs/cloud-adoption-framework/refs/heads/main/docs/ready/azure-best-practices/resource-abbreviations.md\n"
        "   - Example: For Route Server (Microsoft.Network/virtualHubs), use 'rtserv':\n"
        "     resource \"azurerm_route_server\" \"rtserv\" {{ ... }}\n"
        "   - Example: For Storage Account (Microsoft.Storage/storageAccounts), use 'st':\n"
        "     resource \"azurerm_storage_account\" \"st\" {{ ... }}\n"
        "\n"
        "3. VARIABLE REFERENCES:\n"
        "   - Reference all simple arguments (strings, numbers, bools, simple lists) using `var.variable_name`\n"
        "   - For required arguments: directly use `var.variable_name`\n"
        "   - For optional arguments with defaults: use `var.variable_name` (Terraform will use the default if not provided)\n"
        "\n"
        "4. DYNAMIC BLOCKS:\n"
        "   - Use `dynamic` blocks ONLY for properties listed in the Nested Block Tree\n"
        "   - Do NOT use dynamic blocks for simple arguments\n"
        "   - Each dynamic block must use the exact block name from the schema\n"
        "\n"
        "5. DYNAMIC BLOCK SYNTAX:\n"
        "   - Use `for_each` with implicit iterators\n"
        "   - The iterator name MUST match the block name (implicit iterator pattern)\n"
        "   - Do NOT create custom iterator names\n"
        "   - Access values using `block_name.value` syntax\n"
        "   - Example:\n"
        "     dynamic \"identity\" {{\n"
        "       for_each = var.identity != null ? [var.identity] : []\n"
        "       content {{\n"
        "         type = identity.value.type\n"
        "         identity_ids = identity.value.identity_ids\n"
        "       }}\n"
        "     }}\n"
        "\n"
        "6. NESTED DYNAMIC BLOCKS:\n"
        "   - When nesting dynamic blocks, each level accesses its parent via `parent_block_name.value`\n"
        "   - Do NOT use `var.*` to access variables inside nested content blocks\n"
        "   - Access parent dynamic block properties only via the iterator value reference\n"
        "   - Example:\n"
        "     dynamic \"site_config\" {{\n"
        "       for_each = var.site_config != null ? [var.site_config] : []\n"
        "       content {{\n"
        "         dynamic \"cors\" {{\n"
        "           for_each = site_config.value.cors != null ? [site_config.value.cors] : []\n"
        "           content {{\n"
        "             allowed_origins = cors.value.allowed_origins\n"
        "           }}\n"
        "         }}\n"
        "       }}\n"
        "     }}\n"
        "\n"
        "7. CONTENT BLOCKS:\n"
        "   - Do NOT use content{{}} blocks at the root resource level\n"
        "   - Content blocks should ONLY appear inside dynamic blocks\n"
        "   - The content block defines the structure of each iteration in a dynamic block\n"
        "\n"
        "8. CONDITIONAL LOGIC:\n"
        "   - For optional blocks, use conditional expressions in for_each:\n"
        "     for_each = var.block_name != null ? [var.block_name] : []\n"
        "   - For optional lists that may be empty:\n"
        "     for_each = var.block_list != null ? var.block_list : []\n"
        "   - This ensures the block is only created when the variable is provided\n"
        "   - IMPORTANT: Do NOT combine both `!= null` AND `length() > 0` checks - choose ONE based on the default value\n"
        "\n"
        "9. FORMATTING:\n"
        "   - Use consistent indentation (2 spaces per level)\n"
        "   - Place simple arguments before dynamic blocks\n"
        "   - Order arguments alphabetically within each section for consistency\n"
        "   - Do NOT include any comments in the code\n"
        "\n"
        "10. OUTPUT REQUIREMENTS:\n"
        "    - Output ONLY valid Terraform HCL code\n"
        "    - Do NOT wrap the output in markdown code blocks (no ```, no backticks)\n"
        "    - Do NOT include any commentary, explanations, or extra text\n"
        "    - The output should be ready to write directly to a .tf file"
    ),
    expected_output="Valid main.tf file only.",
    agent=main_agent
)

# -------------------------------
# AGENT: outputs.tf
# -------------------------------
outputs_agent = Agent(
    role='Terraform Outputs Generator',
    goal='Generate outputs.tf with useful resource attributes',
    backstory="You generate helpful Terraform outputs for users to use in other modules.",
    allow_delegation=False,
    llm=llm
)

outputs_task = Task(
    description=(
        f"Generate an outputs.tf file for the resource {resource_type}.\n"
        "\n"
        "Instructions for generating outputs.tf:\n"
        "\n"
        "1. OUTPUT CONTENT:\n"
        "   - Create a SINGLE output that exposes the resource ID\n"
        "   - The output name should be: `id`\n"
        "   - The output value should reference: `<resource_type>.<caf_abbreviation>.id`\n"
        "\n"
        "2. RESOURCE REFERENCE (CAF CONVENTIONS):\n"
        "   - The resource reference MUST use the exact abbreviation from Microsoft's Cloud Adoption Framework (CAF)\n"
        "   - This abbreviation must match the one used in main.tf\n"
        "   - Find the abbreviation by matching the Azure resource type in the official CAF documentation:\n"
        "     https://raw.githubusercontent.com/MicrosoftDocs/cloud-adoption-framework/refs/heads/main/docs/ready/azure-best-practices/resource-abbreviations.md\n"
        "   - Example: For Route Server (Microsoft.Network/virtualHubs), use 'rtserv':\n"
        "     output \"id\" {{\n"
        "       value = azurerm_route_server.rtserv.id\n"
        "     }}\n"
        "   - Example: For Storage Account (Microsoft.Storage/storageAccounts), use 'st':\n"
        "     output \"id\" {{\n"
        "       value = azurerm_storage_account.st.id\n"
        "     }}\n"
        "\n"
        "3. OUTPUT STRUCTURE:\n"
        "   - Include a `description` property in the output block\n"
        "   - The description should be: \"The ID of the <resource_name>\"\n"
        "   - Example:\n"
        "     output \"id\" {{\n"
        "       description = \"The ID of the Route Server\"\n"
        "       value       = azurerm_route_server.rtserv.id\n"
        "     }}\n"
        "\n"
        "4. FORMATTING:\n"
        "   - Use consistent indentation (2 spaces per level)\n"
        "   - Align the `description` and `value` properties for readability\n"
        "   - Do NOT include any comments in the code\n"
        "\n"
        "5. OUTPUT REQUIREMENTS:\n"
        "   - Output ONLY valid Terraform HCL code\n"
        "   - Do NOT wrap the output in markdown code blocks (no ```, no backticks)\n"
        "   - Do NOT include any commentary, explanations, or extra text\n"
        "   - The output should be ready to write directly to a .tf file"
    ),
    expected_output="Terraform outputs.tf only.",
    agent=outputs_agent
)

# -------------------------------
# Run CrewAI
# -------------------------------
crew = Crew(
    agents=[variables_agent, main_agent, outputs_agent],
    tasks=[variables_task, main_task, outputs_task]
)

result = crew.kickoff()

# -------------------------------
# Output results
# -------------------------------
generated = {
    'variables.tf': clean_content(variables_task.output.raw if variables_task.output else ""),
    'main.tf': clean_content(main_task.output.raw if main_task.output else ""),
    'outputs.tf': clean_content(outputs_task.output.raw if outputs_task.output else ""),
    'terraform.tf': f'''terraform {{
  required_version = "~> 1.8"
  required_providers {{
    {provider_name} = {{
      source  = "{provider_supplier}/{provider_name}"
      version = "~> {provider_version}"
    }}
  }}
}}
'''
}

# Output to folder
output_folder = os.path.join("modules", resource_type.lower())
os.makedirs(output_folder, exist_ok=True)

for filename, content in generated.items():
    if content:
        path = os.path.join(output_folder, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"✅ Written: {path}")
