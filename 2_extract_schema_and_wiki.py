import json
import os
import sys
import pprint
import urllib.request

def extract_full_block_tree(resource_type: str, provider_name: str, provider_version: str):
    path = f"{provider_name}_{provider_version}_schema.json"
    with open(path, "r") as f:
        schema = json.load(f)

    resources = schema.get("provider_schemas", {}) \
        .get(f"registry.terraform.io/{provider_supplier}/{provider_name}", {}) \
        .get("resource_schemas", {})

    resource = resources.get(resource_type, {})
    if not resource:
        raise ValueError(f"❌ Resource type '{resource_type}' not found in schema.")

    root_block = resource["block"]

    def parse_block(block):
        attributes = []
        for name, attr in block.get("attributes", {}).items():
            is_required = attr.get("required", False)
            is_computed = attr.get("computed", False)
            if not is_required and is_computed:
                continue  # Skip computed-only fields
            attributes.append({
                "name": name,
                "required": is_required
            })

        blocks = []
        for block_name, block_info in block.get("block_types", {}).items():
            sub_block = parse_block(block_info["block"])
            blocks.append({
                "name": block_name,
                "min_items": block_info.get("min_items", 0),
                "attributes": sub_block["attributes"],
                "blocks": sub_block["blocks"]
            })

        return {"attributes": attributes, "blocks": blocks}

    parsed = parse_block(root_block)
    return parsed["attributes"], parsed["blocks"]

def download_markdown(resource_type: str, provider_name: str, provider_version: str):
    base_url = f"https://raw.githubusercontent.com/{provider_supplier}/terraform-provider-{provider_name}/v{provider_version}/website/docs/r/"

    short_name = resource_type.replace(f"{provider_name}_", "")
    filename = f"{short_name}.html.markdown"
    url = base_url + filename

    os.makedirs("wiki", exist_ok=True)
    destination = os.path.join("wiki", filename)

    print(f"🔗 Downloading markdown from: {url}")
    try:
        urllib.request.urlretrieve(url, destination)
        print(f"📂 Saved markdown to: {destination}")
    except Exception as e:
        print(f"❌ Failed to download markdown: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python 2_extract_schema_and_wiki.py <provider_supplier> <provider_name> <provider_version> <resource_type>")
        sys.exit(1)

    provider_supplier = sys.argv[1]
    provider_name = sys.argv[2]
    provider_version = sys.argv[3]
    resource_type = sys.argv[4]
    print(f"\n🔍 Extracting schema for resource: {resource_type}\n")

    try:
        args, blocks = extract_full_block_tree(resource_type, provider_name, provider_version)
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    # Save to ./schemas/<resource_type>.json
    os.makedirs("schemas", exist_ok=True)
    output_path = os.path.join("schemas", f"{resource_type}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"arguments": args, "block_tree": blocks}, f, indent=2)
        print(f"\n📂 Schema summary written to: {output_path}")

    # Download corresponding markdown
    download_markdown(resource_type, provider_name, provider_version)
