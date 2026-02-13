# plotune_sdk/forms.py
# Helpers to generate form schemas for extensions

from typing import List, Dict, Any


class FormLayout:
    def __init__(self):
        self.sections: List[Dict[str, Any]] = []
        self.fields: Dict[str, Dict[str, Any]] = {}

    def add_tab(self, label: str):
        """
        Add a new tab section to the form layout.

        :param label: The label for the tab.
        :return: SectionBuilder for chaining field additions.
        """
        tab = {"type": "tab", "label": label, "fields": []}
        self.sections.append(tab)
        return SectionBuilder(tab, self.fields)

    def add_group(self, label: str):
        """
        Add a new group section to the form layout.

        :param label: The label for the group.
        :return: SectionBuilder for chaining field additions.
        """
        group = {"type": "group", "label": label, "fields": []}
        self.sections.append(group)
        return SectionBuilder(group, self.fields)

    def to_schema(self) -> Dict[str, Any]:
        """
        Generate the schema dictionary from the built layout and fields.

        :return: The schema as a dictionary.
        """
        return {"layout": self.sections, "fields": self.fields}


class SectionBuilder:
    def __init__(self, section: Dict[str, Any], fields_dict: Dict[str, Dict[str, Any]]):
        self.section = section
        self.fields_dict = fields_dict

    def add_text(self, key: str, label: str, default: str = "", required: bool = False):
        """
        Add a text field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param default: Default value.
        :param required: Whether the field is required.
        :return: Self for chaining.
        """
        self.fields_dict[key] = {
            "type": "text",
            "label": label,
            "default": default,
            "required": required,
        }
        self.section["fields"].append(key)
        return self

    def add_number(
        self,
        key: str,
        label: str,
        default: int = 0,
        min_val: int = -999999,
        max_val: int = 999999,
        required: bool = False,
    ):
        """
        Add a number field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param default: Default value (will be converted to string in schema).
        :param min_val: Minimum value.
        :param max_val: Maximum value.
        :param required: Whether the field is required.
        :return: Self for chaining.
        """
        self.fields_dict[key] = {
            "type": "number",
            "label": label,
            "default": str(default),
            "min": min_val,
            "max": max_val,
            "required": required,
        }
        self.section["fields"].append(key)
        return self

    def add_combobox(
        self,
        key: str,
        label: str,
        options: List[str],
        default: str = "",
        required: bool = False,
    ):
        """
        Add a combobox field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param options: List of options.
        :param default: Default selected option.
        :param required: Whether the field is required.
        :return: Self for chaining.
        """
        self.fields_dict[key] = {
            "type": "combobox",
            "label": label,
            "options": options,
            "default": default,
            "required": required,
        }
        self.section["fields"].append(key)
        return self

    def add_checkbox(self, key: str, label: str, default: bool = False, required: bool = False):
        """
        Add a checkbox field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param default: Default checked state.
        :param required: Whether the field is required.
        :return: Self for chaining.
        """
        self.fields_dict[key] = {
            "type": "checkbox",
            "label": label,
            "default": default,
            "required": required,
        }
        self.section["fields"].append(key)
        return self

    def add_file(self, key: str, label: str, required: bool = False):
        """
        Add a file picker field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param required: Whether the field is required.
        :return: Self for chaining.
        """
        self.fields_dict[key] = {"type": "file", "label": label, "required": required}
        self.section["fields"].append(key)
        return self

    def add_button(self, key: str, label: str, action: Dict[str, Any]):
        """
        Add a button field to the section.

        :param key: Unique key for the field.
        :param label: Display label.
        :param action: Action dictionary (e.g., {"method": "POST", "url": "...", "payload_fields": [...]})
        :return: Self for chaining.
        """
        self.fields_dict[key] = {"type": "button", "label": label, "action": action}
        self.section["fields"].append(key)
        return self
