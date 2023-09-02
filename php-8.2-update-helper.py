from pathlib import Path
import re
import os
from pydantic import BaseModel

class DeclaredProperty(BaseModel):
    visibility: str
    name: str
    line_nr: int

class DynamicProperty(BaseModel):
    name: str
    line_nr: int

class DeprecatedFeature(BaseModel):
    type: str
    line_nr: int
    line: str

class PhpClass(BaseModel):
    name: str
    line_nr: int
    properties: dict[str, DeclaredProperty] = {}
    dynamic_properties: dict[str, DynamicProperty] = {}
    extends: str = ""
    external_used_properties: set[str] = set()

    def get_declaration(self) -> str:
        if self.extends:
            return f"class {self.name} extends {self.extends}"
        return f"class {self.name}"


class PhpFile(BaseModel):
    path: Path
    classes: dict[str, PhpClass]
    deprecated_features: list[DeprecatedFeature] = []

    def get_classes_with_dynamic_properties(self) -> dict[str, PhpClass]:
        return {k: v for k, v in self.classes.items() if v.dynamic_properties}
    
    def all_external_used_properties(self) -> set[str]:
        result: set[str] = set()
        for php_class in self.classes.values():
            result.update(php_class.external_used_properties)
        return result


def process_file(path: Path) -> PhpFile:
    print(f"Processing {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    class_re = re.compile(r'\bclass\s+(\w+)')
    extends_re = re.compile(r'extends\s+(\w+)')
    member_assign_re = re.compile(r'\$this\s*->\s*(\w+)\s*=')
    property_re = re.compile(r'^\s*(private|protected|public|var) \$(\w+)')
    global_member_usage_re = re.compile(r'(\w+)\s*->\s*(\w+)')

    deprecated_string_interpolation_re = re.compile(r'".*?\$\{')
    deprecated_functions_re = re.compile(r'\b(utf8_encode|utf8_decode)\b')

    file = PhpFile(path=path, classes={})
    current_class = PhpClass(name="", line_nr=0)
    file.classes[current_class.name] = current_class

    for nr, line in enumerate(lines):
        if line.strip().startswith("//"):
            continue

        class_m = class_re.search(line)
        property_m = property_re.match(line)
        member_assign_m = member_assign_re.search(line)
        global_member_usage_m = global_member_usage_re.search(line)

        if class_m:
            current_class = PhpClass(name=class_m.group(1), line_nr=nr)
            extends_m = extends_re.search(line)
            if extends_m:
                current_class.extends = extends_m.group(1)
            file.classes[current_class.name] = current_class
        elif property_m:
            declared_property = DeclaredProperty(visibility=property_m.group(1), name=property_m.group(2), line_nr=nr)
            current_class.properties[declared_property.name] = declared_property

        elif member_assign_m:
            member_name = member_assign_m.group(1)
            if member_name not in current_class.properties and member_name not in current_class.dynamic_properties:
                current_class.dynamic_properties[member_name] = DynamicProperty(name=member_name, line_nr=nr)
        elif global_member_usage_m:
            id = global_member_usage_m.group(1)
            if id != "this":
                member_name = global_member_usage_m.group(2)
                current_class.external_used_properties.add(member_name)

        if deprecated_string_interpolation_re.search(line):
            file.deprecated_features.append(DeprecatedFeature(type="string interpolation", line_nr=nr, line=line))
        if deprecated_functions_re.search(line):
            file.deprecated_features.append(DeprecatedFeature(type="function", line_nr=nr, line=line))



    return file

def process_extends(files: list[PhpFile]) -> None:
    mapping: dict[str, PhpClass] = {}
    for file in files:
        for php_class in file.classes.values():
            mapping[php_class.name] = php_class
    # remove empty class name from mapping, if it exists
    mapping.pop("", None)

    for file in files:
        for php_class in file.classes.values():

            parent_class = mapping.get(php_class.extends, None)
            while parent_class:
                # print(f"{php_class.name} extends {parent_class.name}")
                # remove dynamic properties from class, if they are already defined in parent class
                for dyn_prop in list(php_class.dynamic_properties.keys()):
                    if dyn_prop in parent_class.properties:
                        del php_class.dynamic_properties[dyn_prop]
                parent_class = mapping.get(parent_class.extends, None)

def process_files(path: Path) -> str:
    files: list[PhpFile] = []
    all_external_used_properties: set[str] = set()
    result = []
    for path in Path(".").rglob("*.php"):
        file = process_file(path)
        files.append(file)
        all_external_used_properties.update(file.all_external_used_properties())
        # print(file.all_external_used_properties())

        if file.deprecated_features:
            result.append(f"{file.path.absolute()}")
            for deprecated_feature in file.deprecated_features:
                result.append(f"    {deprecated_feature.line_nr+1}: {deprecated_feature.type} {deprecated_feature.line}")
            result.append("")

    process_extends(files)

    for file in files:
        # remove classes without dynamic properties
        dyn_props = file.get_classes_with_dynamic_properties()
        if len(dyn_props) == 0:
            continue

        for php_class in dyn_props.values():
            result.append(f"{php_class.get_declaration()} -- {file.path.absolute()}:{php_class.line_nr+1}")

            for dyn_prop in php_class.dynamic_properties.items():
                result.append(f"    {dyn_prop[1].line_nr+1}: ${dyn_prop[0]}")

            result.append("")
            for dyn_prop in php_class.dynamic_properties.values():
                visibility = "private"
                if dyn_prop.name in all_external_used_properties:
                    visibility = "public"

                result.append(f"    {visibility} ${dyn_prop.name};")
            result.append("")
        result.append("")

    return "\n".join(result)

def main():
    report = process_files(Path("."))
    Path("php-8.2-update-helper.log").write_text(report, encoding="utf-8")

if __name__ == "__main__":
    # os.chdir(Path(__file__).parent)
    main()