from plotune_sdk import FormLayout
import json

# Build the schema step-by-step
form = FormLayout()

# Tab 1: Settings
form.add_tab("Settings").add_text("username", "Username", default="", required=False).add_text(
    "test_field", "Test", default="", required=False
).add_number(
    "seed",
    "Seed",
    default=100,
    min_val=-2000,
    max_val=2000,
    required=True,
).add_combobox(
    "color",
    "Color Pick",
    options=["Red", "Green", "Blue"],
    default="",
    required=True,
)

# Tab 2: Custom
form.add_tab("Custom").add_file("file", "Optional file", required=True)

# Group: Custom Group
form.add_group("Custom Group").add_checkbox("enable", "Enable", default=True, required=False).add_button(
    "forward",
    "Visit",
    action={
        "method": "POST",
        "url": "http://example.com/api/upload",
        "payload_fields": ["upload_file"],
    },
)

# Generate and print the schema
schema = form.to_schema()
print(json.dumps(schema, indent=4))
