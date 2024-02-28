from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from halo import Halo
import argparse

params = {
    "lang": "en",
}


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


lookup_table_df = pd.DataFrame()

globe_parents = []
soup = None

# create empty dataframe with column names type, name, label, hint, constraint, constraint_message, required, default, relevant, calculation, choice_filter, appearance and media
df = pd.DataFrame(
    columns=[
        "type",
        "name",
        "hint",
        "constraint",
        "required",
        "default",
        "relevance",
        "calculation",
        "choice_filter",
        "appearance",
        "media",
        "read_only",
        "node_set",
        "has_label",
    ]
)

df_choice = pd.DataFrame(columns=["list_name", "name", "value", "media", "read_only"])

prelab_df = None
mode = None
missing_elements = pd.DataFrame()


# check if the nodeset is in the dataframe
# if it is return true else return false
def check_nodeset_in_df(nodeset):
    global df
    check_nodeset = df.loc[df["name"] == nodeset]
    if check_nodeset.empty:
        return False
    else:
        return True


# load lookup tables from the lookupTable.xlsx file
# this will be used to map the instance tags in the xml file
# to the lookup table
def loadLookupTables():
    global lookup_table_df
    lookup_table = pd.read_excel("./input/lookupTable.xlsx", sheet_name=None)

    dfs_with_sheet_names = []

    for sheet, df in lookup_table.items():
        df["sheet"] = sheet
        dfs_with_sheet_names.append(df)

    lookup_table_df = pd.concat(dfs_with_sheet_names, ignore_index=True)


# generate if else statement in XLSForm format
# based on the provided conditions and results
# if the condition is true return the truthValue
# else return the notTruthValue
def generate_if_else(condition, truthValue, notTruthValue):
    template = "if({condition}, '{true}', '{false}')"
    return template.format(condition=condition, true=truthValue, false=notTruthValue)


def generate_nested_if(conditions, results, default_result=""):
    """
    Generate a nested if statement in XLSForm format based on the provided conditions and results.

    Parameters:
    - conditions (list): List of conditions to check.
    - results (list): List of results corresponding to each condition.
    - default_result: Result to return if none of the conditions are true.

    Returns:
    - str: Generated XLSForm content.
    """
    if len(conditions) != len(results):
        raise ValueError("Number of conditions must be equal to the number of results.")

    xlsform_content = "if({condition}, '{true_result}', ".format(
        condition=conditions[0], true_result=results[0]
    )

    for i, (condition, result) in enumerate(zip(conditions[1:], results[1:])):
        xlsform_content += f"if({condition}, '{result}', "

    xlsform_content += f"'{default_result}'"

    # Add closing parentheses for each nested if
    for _ in range(len(conditions)):
        xlsform_content += ")"

    return xlsform_content


"""
parseInstance function will parse the instance tags in the xml file
and map them to the lookup table
"""


def parseInstance(instance):
    global lookup_table_df
    global df
    global prelab_df
    global missing_elements

    # remove the instance tag
    instnace_bak = instance

    if "@case_id" in instance:
        pattern = re.compile(r"[,:><=+) ]")
        element = instance.split("]")[-1]
        split_element = pattern.split(element)
        element_key = split_element[0][1:].strip().replace("/", "_")
        element_value = split_element[-1].strip()
        find_prelab_element = prelab_df.loc[
            prelab_df["label"] == element_key, "nodeset"
        ]
        if find_prelab_element is not None:
            parsed_pre_lab_element = find_prelab_element

            if (
                len(
                    missing_elements.loc[
                        missing_elements["name"] == parsed_pre_lab_element.values[0],
                        "name",
                    ]
                )
                == 0
            ):
                missing_elements = missing_elements._append(
                    {
                        "type": "hidden",
                        "name": parsed_pre_lab_element.values[0],
                        "label": "NO_LABEL",
                    },
                    ignore_index=True,
                )

            parsed_element = re.sub(
                r"\b" + re.escape(element_key) + r"\b",
                "${" + find_prelab_element.values[0] + "}",
                element[1:],
            )
            # parsed_element = element[1:].replace(
            #     element_key, "${" + find_prelab_element.values[0] + "}"
            # )
            return parsed_element
        else:
            print("empty")

    instance = instance.strip()[8:]
    # remove the last paranthesis
    if instance.endswith(")"):
        instance = instance[:-1]

    try:
        out_statement = ""
        # drop text beteeen ) and [
        instance = re.sub(r"\)[^\]]*\[", ")[", instance)
        # extract text beteen paranthesis
        instance_items = re.search(r"\(\'(.*?)\'\)", instance)
        # extact instance name
        instance_name = instance_items.group(1).split(":")[1]
        # extract instance key value pairs
        instance_key_value = re.search(r"\[(.*?)\]", instance)
        instance_key = instance_key_value.group(1).split("=")[0].strip()
        instance_value = instance_key_value.group(1).split("=")[1].strip()
        # get the instance y param
        instance_y = instance.split("/")[-1].strip()

        # extract the sheet from the lookup table
        sheet_data = lookup_table_df.loc[lookup_table_df["sheet"] == instance_name]
        # extract the column from the sheet_data
        filter_sheet = sheet_data.loc[
            :, ["field: " + instance_key, "field: " + instance_y]
        ]

        # extract the value inside paranthesis in the instance_value
        instance_value_nodes = re.findall(r"\((.*?)\)", instance_value)
        # replace / with _
        instance_value_nodes_parsed = [
            "_".join(i[1:].split("/")) for i in instance_value_nodes
        ]

        # check if the instance_value_node is in the dataframe
        for index, instance_value_node in enumerate(instance_value_nodes):
            instance_value = instance_value.replace(
                instance_value_node, "${" + instance_value_nodes_parsed[index] + "}"
            )

        conditions = []
        results = []

        # iterate through the sheet_data and generate the conditions and results
        for index, row in sheet_data.iterrows():
            key_value = row["field: " + instance_key]

            # check if the key_value is a float
            # if it is convert it to int
            if type(key_value) == float:
                key_value = int(key_value)

            instance_logic = instance_key_value.group(1).replace(
                instance_key, "'" + str(key_value) + "'"
            )

            for index, instance_value_node in enumerate(instance_value_nodes):
                instance_logic = instance_logic.replace(
                    instance_value_node, "${" + instance_value_nodes_parsed[index] + "}"
                )
                conditions.append(instance_logic)

            results.append(row["field: " + instance_y])

        if len(conditions) > 1:
            nested_if_else_statement = generate_nested_if(
                conditions, results, default_result=""
            )
            out_statement = nested_if_else_statement
        if len(conditions) == 1:
            if_else_statement = generate_if_else(conditions[0], results[0], "")
            out_statement = if_else_statement

        return out_statement

    except Exception as e:
        print(f"{bcolors.WARNING} WARNING: {e} {bcolors.ENDC}")
        return instance


"""
extract_lookup_table_data function will extract the lookup table data
from the lookup table dataframe 
"""


def extract_lookup_table_data(sheetName):
    global lookup_table_df
    sheet_data = lookup_table_df.loc[lookup_table_df["sheet"] == sheetName]
    return sheet_data


"""
get_label_value function will extract the label value from the xml file 
"""


def get_label_value(text_id):
    translations = soup.find("itext").find_all("translation")
    output = {}
    for translation in translations:
        translation_lang = translation.get("lang")
        labels = translation.find("text", id=text_id)
        if labels is None:
            text_value = None

        elif labels.find("value", form="markdown") is not None:
            text_value = labels.find("value", form="markdown").get_text()
        else:
            text_value = labels.find("value").get_text()
        output[translation_lang] = text_value
    return output


"""
build_form_structure function will extract the form structure from the xml file
"""


def build_form_structure():
    global df
    # find the form structure
    formStructure = soup.find("instance").find("data")

    return formStructure


"""
traverse function will traverse the form structure and generate the dataframe
"""


def traverse(t, current_path=None):
    global df
    global globe_parents
    parents = []

    if current_path is None:
        current_path = [t.name]

    for tag in t.find_all(recursive=False):
        if not tag.find():
            node_type = None
            # print(" -> ".join(current_path + [tag.name]))
            # print(tag.name)
            if current_path[-1] not in parents:
                if len(parents) > 0:
                    node_name = parents[-1], "_", current_path[-1]
                else:
                    node_name = "data_" + current_path[-1]

                parents.append(current_path[-1])
                globe_parents.append(current_path[-1])
                node_type = "begin_group"
                df = df._append(
                    {
                        "type": node_type,
                        "name": node_name,
                        "label": tag.name,
                        "hint": "",
                        "constraint": "",
                        "constraint_message": "",
                        "required": "",
                        "default": "",
                        "relevance": "",
                        "calculation": "",
                        "choice_filter": "",
                        "appearance": "",
                        "media": "",
                        "read_only": "",
                        "node_set": "",
                    },
                    ignore_index=True,
                )

            df = df._append(
                {
                    "type": None,
                    "name": "_".join(current_path + [tag.name]),
                    "label": tag.name,
                    "hint": "",
                    "constraint": "",
                    "constraint_message": "",
                    "required": "",
                    "default": "",
                    "relevance": "",
                    "calculation": "",
                    "choice_filter": "",
                    "appearance": "",
                    "media": "",
                    "read_only": "",
                    "node_set": "",
                },
                ignore_index=True,
            )

            if (tag == t.find_all(recursive=False)[-1]) and (
                current_path[-1] in parents
            ):
                # print("end_group", current_path[-1])
                parents.remove(current_path[-1])
                globe_parents.remove(current_path[-1])
        else:
            traverse(tag, current_path + [tag.name])
            df = df._append(
                {
                    "type": "end_group",
                    "name": "data_" + tag.name,
                    "label": tag.name,
                    "hint": "",
                    "constraint": "",
                    "constraint_message": "",
                    "required": "",
                    "default": "",
                    "relevance": "",
                    "calculation": "",
                    "choice_filter": "",
                    "appearance": "",
                    "media": "",
                    "read_only": "",
                    "node_set": "",
                },
                ignore_index=True,
            )
    # print(globe_parents)


# nodes = build_form_structure()
# traverse(nodes)
# print("dataframe generated")
def parse_binds():
    global df
    binds = soup.find_all("bind")
    for bind in binds:
        nodeset = bind.get("nodeset")[1:]
        nodeset = "_".join(nodeset.split("/"))
        # print(nodeset)
        df.loc[df["name"] == nodeset, "nodeset"] = nodeset
        df.loc[df["name"] == nodeset, "required"] = bind.get("required")
        bind_relevant = bind.get("relevant")

        # map relevant
        if bind_relevant is not None:
            while bind_relevant.__contains__("casedb"):
                bind_relevant_re = re.search(r"instance(.*?)(?:,|\))", bind_relevant)
                if bind_relevant_re is not None:
                    pattern = re.compile(r"instance\('.+?'\)/.+?\[")
                    matches = pattern.findall(bind_relevant)
                    split_relevant = matches[0]
                    replace_instance_with_logic = parseInstance(
                        bind_relevant.split("[")[1]
                    )
                    bind_relevant = bind_relevant.replace(
                        split_relevant + bind_relevant.split("[")[1],
                        replace_instance_with_logic,
                    )
            extract_instance_tags = bind_relevant.split(",")
            for instance in extract_instance_tags:
                instance_re = re.search(r"\binstance(.*?)(?:,|\))", instance)
                if instance_re is not None:
                    if instance.endswith(")"):
                        bind_relevant = bind_relevant.replace(
                            instance, replace_instance_with_logic + ")"
                        )
                    else:
                        bind_relevant = bind_relevant.replace(
                            instance, replace_instance_with_logic
                        )
                    if "commcare" in instance:
                        print(
                            f"{bcolors.WARNING}Possible commcare header: {instance}{bcolors.ENDC}"
                        )
                else:
                    continue

            bind_relevant_regex = re.findall(r"\/[^\s=]+", bind_relevant)
            bind_relevant_regex = sorted(bind_relevant_regex, key=len, reverse=True)
            for reg in bind_relevant_regex:
                reg = reg.strip()
                if reg.endswith(",") or reg.endswith(")"):
                    reg_filter = reg[1:-1]
                    reg_to_name = "_".join(reg_filter.split("/"))
                    if check_nodeset_in_df(reg_to_name):
                        bind_relevant = bind_relevant.replace(
                            reg, "${" + reg_to_name + "}" + reg[-1]
                        )

                else:
                    reg_filter = reg[1:]
                    reg_to_name = "_".join(reg_filter.split("/"))
                    if check_nodeset_in_df(reg_to_name):
                        bind_relevant = bind_relevant.replace(
                            reg, "${" + reg_to_name + "}"
                        )

            df.loc[df["name"] == nodeset, "relevance"] = bind_relevant

        # map constraints
        bind_constratint = bind.get("constraint")
        if bind_constratint is not None:
            bind_constratint_regex = re.findall(r"\/[^\s=]+", bind_constratint)
            bind_constratint_regex = sorted(
                bind_constratint_regex, key=len, reverse=True
            )
            for reg in bind_constratint_regex:
                reg = reg.strip()
                if reg.endswith(",") or reg.endswith(")"):
                    reg_filter = reg[1:-1]
                    reg_to_name = "_".join(reg_filter.split("/"))

                    if check_nodeset_in_df(reg_to_name):
                        bind_constratint = bind_constratint.replace(
                            reg, "${" + reg_to_name + "}" + reg[-1]
                        )

                else:
                    reg_filter = reg[1:]
                    reg_to_name = "_".join(reg_filter.split("/"))
                    if check_nodeset_in_df(reg_to_name):
                        bind_constratint = bind_constratint.replace(
                            reg, "${" + reg_to_name + "}"
                        )

            df.loc[df["name"] == nodeset, "constraint"] = bind_constratint

        # map calculations
        bind_calculate = bind.get("calculate")
        if bind_calculate is not None:
            if "weight_estimated" in bind_calculate:
                temp = bind_calculate
                print(
                    f"{bcolors.WARNING}Possible weight_estimated header:{bcolors.ENDC}"
                )
                print(
                    bind_calculate.replace(
                        "weight_estimated",
                        f"{bcolors.OKCYAN}weight_estimated{bcolors.ENDC}",
                    )
                )
            while bind_calculate.__contains__("casedb"):
                bind_calculate_re = re.search(r"instance(.*?)(?:,|\))", bind_calculate)
                if bind_calculate_re is not None:
                    pattern = re.compile(r"instance\('.+?'\)/.+?\[")
                    matches = pattern.findall(bind_calculate)
                    split_calculate = matches[0]
                    replace_instance_with_logic = parseInstance(
                        bind_calculate.split("[")[1]
                    )
                    bind_calculate = bind_calculate.replace(
                        split_calculate + bind_calculate.split("[")[1],
                        replace_instance_with_logic,
                    )
            extract_instance_tags = bind_calculate.split(",")
            for instance in extract_instance_tags:
                instance_re = re.search(r"\binstance(.*?)(?:,|\))", instance)
                if instance_re is not None:
                    replace_instance_with_logic = parseInstance(instance)
                    # print(f"{bcolors.OKBLUE}{bind_calculate}{bcolors.ENDC}")
                    # print(
                    #     f"{bcolors.OKCYAN}{replace_instance_with_logic}{bcolors.ENDC}"
                    # )

                    if instance.endswith(")"):
                        bind_calculate = bind_calculate.replace(
                            instance, replace_instance_with_logic + ")"
                        )
                    else:
                        bind_calculate = bind_calculate.replace(
                            instance, replace_instance_with_logic
                        )
                    if "commcare" in instance:
                        print(
                            f"{bcolors.WARNING}Possible commcare header: {instance}{bcolors.ENDC}"
                        )
                else:
                    continue
            bind_calculate_regex = re.findall(r"\/[^\s=]+", bind_calculate)
            bind_calculate_regex = sorted(bind_calculate_regex, key=len, reverse=True)
            for reg in bind_calculate_regex:
                reg = reg.strip()
                if reg.endswith(",") or reg.endswith(")"):
                    reg_filter = reg[1:-1]
                    reg_to_name = "_".join(reg_filter.split("/"))

                    if check_nodeset_in_df(reg_to_name):
                        bind_calculate = bind_calculate.replace(
                            reg, "${" + reg_to_name + "}" + reg[-1]
                        )
                else:
                    reg_filter = reg[1:]
                    reg_to_name = "_".join(reg_filter.split("/"))
                    if check_nodeset_in_df(reg_to_name):
                        bind_calculate = bind_calculate.replace(
                            reg, "${" + reg_to_name + "}"
                        )

            df.loc[df["name"] == nodeset, "calculation"] = bind_calculate

        # map constraintMsg
        constraint_message = bind.get("jr:constraintMsg")
        if constraint_message is not None:
            constraint_message = constraint_message.split("'")[1]
            constraint_labels = get_label_value(constraint_message)
            if constraint_labels is not None:
                for lang, label in constraint_labels.items():
                    df.loc[df["name"] == nodeset, "constraint_message::" + lang] = label

        # map requiredMsg
        required_message = bind.get("jr:requiredMsg")
        if required_message is not None:
            required_message = required_message.split("'")[1]
            required_message_labels = get_label_value(required_message)
            for lang, label in required_message_labels.items():
                df.loc[df["name"] == nodeset, "required_message::" + lang] = label

        # map types
        # currently this form has only these types, however there are more odk type
        # this has to mapped with more xml files when available
        bind_type = bind.get("type")
        if bind_type is not None and "string" in bind_type:
            df.loc[df["name"] == nodeset, "type"] = "string"
        if bind_type is not None and "int" in bind_type:
            df.loc[df["name"] == nodeset, "type"] = "integer"
        if bind_type is not None and "double" in bind_type:
            df.loc[df["name"] == nodeset, "type"] = "decimal"


def parse_body():
    global df
    global df_choice
    body = soup.find("h:body")

    for tag in body.find_all(recursive=True):
        tag_ref = tag.get("ref")
        tag_name = tag.name
        tag_appearance = tag.get("appearance")
        tag_ref_to_name = None
        tag_name_regex = None
        df_name = None

        if tag_ref is None:
            continue

        tag_ref_regex = re.findall(r"\/[^\s=':)]+", tag_ref)
        for reg in tag_ref_regex:
            tag_ref_to_name = "_".join(reg.split("/")[1:])

        if tag_name == "select1":
            df.loc[df["name"] == tag_ref_to_name, "type"] = (
                "select_one " + tag_ref_to_name
            )

            # parse itemset tags if available
            itemset = tag.find("itemset")
            if itemset is not None:
                itemset_reference = itemset.get("nodeset")
                # extract the instance name within the nodeset

            for child in tag.find_all("item"):
                child_label = child.find("label").get("ref")
                child_label = child_label.split("'")[1]
                df_element_name = child_label.split("/")[-1].split(":")[0]
                label_values = get_label_value(child_label)

                choice = {}
                for lang, label in label_values.items():
                    choice["label::" + lang] = label

                choice["list_name"] = tag_ref_to_name
                choice["name"] = df_element_name
                df_choice = df_choice._append(choice, ignore_index=True)

        elif tag_name == "select":
            df.loc[df["name"] == tag_ref_to_name, "type"] = (
                "select_multiple " + tag_ref_to_name
            )

            # parse itemset tags if available
            itemset = tag.find("itemset")
            if itemset is not None:
                itemset_reference = itemset.get("nodeset")
                # extract the instance name within the nodeset
                instance = re.search(r"'(.*?)'", itemset_reference)
                instance = instance.group(1)
                lookup_data = extract_lookup_table_data(instance)
                fields = re.search(r"\[(.*?)\]", itemset_reference)
                fields = fields.group(1).split(" ")

                filtered_field_dataframe = pd.DataFrame()
                refined_fields = ["field: value", "field: label 1"]
                for field in fields:
                    if field.__contains__("/"):
                        field = field.split("/")[-1]

                    field = field.replace("/", "_")
                    refined_fields.append("field: " + field)

                valid_columns = list(
                    set(refined_fields).intersection(lookup_data.columns)
                )
                filtered_field_dataframe = lookup_data[valid_columns]
                filtered_field_dataframe = filtered_field_dataframe.copy()
                filtered_field_dataframe.loc[:, "list_name"] = tag_ref_to_name

                filtered_field_dataframe_columns = (
                    filtered_field_dataframe.columns.tolist()
                )

                for column in filtered_field_dataframe_columns:
                    column = column.strip()
                    if ":" in column:
                        column_post = column.split(":")[1]
                        column_post = column_post.strip()
                        filtered_field_dataframe = filtered_field_dataframe.rename(
                            columns={column: column_post}
                        )

                filtered_field_dataframe = filtered_field_dataframe.rename(
                    columns={"label 1": "label"}
                )

                df_choice = pd.concat(
                    [df_choice, filtered_field_dataframe], ignore_index=True
                )
                # for data in lookup_data:
                #     print(data)

            for child in tag.find_all("item"):
                child_label = child.find("label").get("ref")
                child_label = child_label.split("'")[1]
                df_element_name = child_label.split("/")[-1].split(":")[0]
                label_value = get_label_value(child_label)

                choice = {}

                for lang, label in label_value.items():
                    choice["label::" + lang] = label

                choice["list_name"] = tag_ref_to_name
                choice["name"] = df_element_name

                # value = child.find("value").get_text()
                df_choice = df_choice._append(choice, ignore_index=True)
        # df.loc[df["name"] == tag_ref_to_name, "type"] = odk_type

        if tag_appearance == "field-list":
            df_name = tag_ref.split("/")[-1]
            df.loc[df["name"] == df_name, "appearance"] = "field-list"

        elif tag_appearance is not None:
            df.loc[df["name"] == tag_ref_to_name, "appearance"] = tag_appearance


# fill_labels function will fill the labels in the dataframe
def fill_labels():
    global df
    df["has_label"] = False
    translations = soup.find("itext").find_all("translation")

    for translation in translations:
        translation_lang = translation.get("lang")
        column_name = "label" + "::" + translation_lang

        for text in translation.find_all("text"):
            text_content = text.contents

            text_id = text.get("id")
            text_id_regex = re.findall(r"\/[^\s=':)]+", text_id)
            text_id_to_name = "_".join(text_id_regex[0].split("/")[1:])

            text_value = text.find("value", form="markdown")
            if text_value is not None:
                output_tag = text_value.find_all("output")
                if output_tag is not None and len(output_tag) > 0:
                    for output in output_tag:
                        output_tag_value = output.get("value")
                        output_value_to_name = "_".join(output_tag_value.split("/")[1:])
                        output.replace_with("${" + output_value_to_name + "}")
                df.loc[df["name"] == text_id_to_name, column_name] = (
                    text_value.get_text()
                )
                df.loc[df["name"] == text_id_to_name, "has_label"] = True
            else:
                text_value = text.find("value")
                output_tag = text_value.find_all("output")
                if output_tag is not None and len(output_tag) > 0:
                    for output in output_tag:
                        output_tag_value = output.get("value")
                        output_value_to_name = "_".join(output_tag_value.split("/")[1:])
                        output.replace_with("${" + output_value_to_name + "}")
                df.loc[df["name"] == text_id_to_name, column_name] = (
                    text_value.get_text()
                )
                df.loc[df["name"] == text_id_to_name, "has_label"] = True


# refine function will do the final refines of the dataframe
def refine():
    global df
    # change type of the dataframe to calculate if the label name has not changed
    exclusion_condition = df["type"].str.contains("begin_group") | df[
        "type"
    ].str.contains("end_group")
    inclusion_condition = df["has_label"] == False
    df.loc[
        ~exclusion_condition & inclusion_condition,
        "type",
    ] = "calculate"


def main():
    global df
    global soup
    global prelab_df
    global missing_elements
    global mode

    parser = argparse.ArgumentParser(description="Convert CHT XML to XLSForm")
    parser.add_argument(
        "--input", "-i", type=str, required=True, help="Input file path"
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True, help="Output file path"
    )
    parser.add_argument(
        "--prelab", "-p", type=str, required=False, help="Prelab file path"
    )
    parser.add_argument(
        "--mode", "-m", type=str, required=True, help="Mode of operation"
    )

    args = parser.parse_args()

    input_file = args.input
    output_file = args.output
    mode = args.mode
    prelab_file = args.prelab

    if (input_file is None) or (output_file is None):
        print(
            f"{bcolors.FAIL} ERROR: Please provide input and output file paths {bcolors.ENDC}"
        )
        return
    if mode == "postLab" and prelab_file is None:
        print(f"{bcolors.FAIL} ERROR: Please provide prelab file path {bcolors.ENDC}")
        return
    elif mode == "postLab" and prelab_file is not None:
        prelab_df = pd.read_excel(prelab_file)

        missing_elements = missing_elements._append(
            [
                {"type": "hidden", "name": "data"},
                {
                    "type": "begin_group",
                    "name": "inputs",
                    "label": "NO_LABEL",
                    "appearance": "field-list",
                    "relevance": "./source='user'",
                },
                {
                    "type": "hidden",
                    "name": "data_load",
                },
                {
                    "type": "integer",
                    "name": "hidden_int",
                    "relevance": "false()",
                    "label": "NO_LABEL",
                },
                {
                    "type": "hidden",
                    "name": "source",
                    "default": "user",
                    "appearance": "hidden",
                },
                {"type": "hidden", "name": "source_id", "relevance": "hidden"},
                {
                    "type": "begin_group",
                    "name": "user",
                    "label": "NO_LABEL",
                },
                {
                    "type": "string",
                    "name": "contract_id",
                    "label": "NO_LABEL",
                },
                {
                    "type": "string",
                    "name": "facility_id",
                    "label": "NO_LABEL",
                },
                {"type": "string", "name": "name", "label": "NO_LABEL"},
                {"type": "end_group", "name": "user"},
                {
                    "type": "hidden",
                    "name": "person_uuid",
                },
                {"type": "hidden", "name": "person_name"},
                {"type": "hidden", "name": "person_role"},
                {"type": "hidden", "name": "patient_uuid"},
                {"type": "begin_group", "name": "contact", "label": "NO_LABEL"},
                {"type": "string", "name": "_id", "label": "NO_LABEL"},
                {"type": "end_group", "name": "contact"},
                {
                    "type": "calculate",
                    "name": "source_id",
                    "calculation": "../inputs/source_id",
                },
                {
                    "type": "calculate",
                    "name": "patient_uuid",
                    "calculation": "../inputs/patient_uuid",
                },
            ],
            ignore_index=True,
        )

    # read the xml file and populate variable
    xml = ""
    with open(input_file, "r") as file:
        xml = file.read()

    # parse the xml file
    soup = BeautifulSoup(xml, "xml")

    spinner = Halo(text="Loading", spinner="dots")
    spinner.start()

    loadLookupTables()
    print(" >> lookup tables loaded")
    parseForm = build_form_structure()
    print(" >> form structure generated")
    traverse(parseForm)
    print(" >> form structure traversed")
    parse_binds()
    print(" >> binds parsed")
    parse_body()
    print(" >> body parsed")
    fill_labels()
    print(" >> labels filled")
    refine()
    print(" >> refine dataframe")

    missing_elements = missing_elements._append(
        {
            "type": "end_group",
            "name": "inputs",
        },
        ignore_index=True,
    )

    df = df.drop(0)
    missing_elements = missing_elements.drop(0)
    df = pd.concat([missing_elements, df], axis=0, ignore_index=True)

    # currently this assumes that all non types are notes, but this may not be the case all the tie
    # but for this CHT form it works, maybe this can be improved in the future with more XML files and identifying more types
    missing_types = df.loc[df["type"].isna()]
    df["type"] = df["type"].fillna("note")

    # remove labels from end_group
    df.loc[df["type"] == "end_group", "label"] = ""

    # remove appearence from end_group
    df.loc[df["type"] == "end_group", "appearance"] = ""

    # remove relevant from end_group
    df.loc[df["type"] == "end_group", "relevance"] = ""

    with pd.ExcelWriter(output_file) as writer:
        df.to_excel(writer, sheet_name="survey", index=False)
        df_choice.to_excel(writer, sheet_name="choices", index=False)

    print(" >> excel file generated")

    spinner.stop()


if __name__ == "__main__":
    main()
