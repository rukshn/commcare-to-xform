from bs4 import BeautifulSoup
import pandas as pd
import re
import time

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

# create empty dataframe with column names type, name, label, hint, constraint, constraint_message, required, default, relevant, calculation, choice_filter, appearance and media
df = pd.DataFrame(
    columns=[
        "type",
        "name",
        "label",
        "hint",
        "constraint",
        "constraint_message",
        "required",
        "default",
        "relevant",
        "calculation",
        "choice_filter",
        "appearance",
        "media",
        "read_only",
        "node_set",
    ]
)

df_choice = pd.DataFrame(
    columns=["list_name", "name", "label", "value", "media", "read_only"]
)

# read the xml file and populate variable
xml = ""
with open("./input/cht.xml", "r") as file:
    xml = file.read()

# parse the xml file
soup = BeautifulSoup(xml, "xml")

globe_parents = []


def check_nodeset_in_df(nodeset):
    global df
    check_nodeset = df.loc[df["name"] == nodeset]
    if check_nodeset.empty:
        return False
    else:
        return True


def loadLookupTables():
    global lookup_table_df
    lookup_table = pd.read_excel("./input/lookupTable.xlsx", sheet_name=None)

    dfs_with_sheet_names = []

    for sheet, df in lookup_table.items():
        df["sheet"] = sheet
        dfs_with_sheet_names.append(df)

    lookup_table_df = pd.concat(dfs_with_sheet_names, ignore_index=True)


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
    for _ in range(len(conditions) - 1):
        xlsform_content += ")"

    return xlsform_content


def parseInstance(instance):
    global lookup_table_df
    global df
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
    filter_sheet = sheet_data.loc[:, ["field: " + instance_key, "field: " + instance_y]]

    # extract the value inside paranthesis in the instance_value
    instance_value_nodes = re.findall(r"\((.*?)\)", instance_value)
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

    for index, row in sheet_data.iterrows():
        key_value = row["field: " + instance_key]
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
        print(conditions)
        print(results)
        nested_if_else_statement = generate_nested_if(
            conditions, results, default_result=""
        )
        print(nested_if_else_statement)

    print(
        f"{bcolors.OKGREEN}instance name: {instance_name} {bcolors.ENDC} {bcolors.OKBLUE} instance key: {instance_key} {bcolors.ENDC} {bcolors.WARNING} instance value: {instance_value} {bcolors.ENDC} {bcolors.OKCYAN} instance y: {instance_y}{bcolors.ENDC}"
    )


def extract_lookup_table_data(sheetName):
    global lookup_table_df
    sheet_data = lookup_table_df.loc[lookup_table_df["sheet"] == sheetName]
    return sheet_data


def get_label_value(text_id):
    labels = soup.find("itext").find("translation", lang="en").find("text", id=text_id)
    if labels is None:
        return None
    text_value = labels.find("value", form="markdown")
    if text_value is not None:
        return text_value.get_text()
    else:
        text_value = labels.find("value")
        return text_value.get_text()


def build_form_structure():
    global df
    # find the form structure
    formStructure = soup.find(
        "data",
        xmlns="http://openrosa.org/formdesigner/466B8B00-76BA-482F-A396-35BD6F0767DB",
    )

    return formStructure


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
                        "relevant": "",
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
                    "relevant": "",
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
                    "relevant": "",
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

            df.loc[df["name"] == nodeset, "relevant"] = bind_relevant

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

            extrat_instance_tags = re.findall(r"instance(.*?),", bind_calculate)
            for instance in extrat_instance_tags:
                parseInstance(instance)

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
            constraint_message = get_label_value(constraint_message)
            df.loc[df["name"] == nodeset, "constraint_message"] = constraint_message

        # map requiredMsg
        required_message = bind.get("jr:requiredMsg")
        if required_message is not None:
            required_message = required_message.split("'")[1]
            required_message = get_label_value(required_message)

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
                label_value = get_label_value(child_label)

                value = child.find("value").get_text()
                df_choice = df_choice._append(
                    {
                        "list_name": tag_ref_to_name,
                        "name": df_element_name,
                        "label": label_value,
                        # "value": value,
                    },
                    ignore_index=True,
                )

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

                value = child.find("value").get_text()
                df_choice = df_choice._append(
                    {
                        "list_name": tag_ref_to_name,
                        "name": df_element_name,
                        "label": label_value,  # "value": value,
                    },
                    ignore_index=True,
                )
        # df.loc[df["name"] == tag_ref_to_name, "type"] = odk_type

        if tag_appearance == "field-list":
            df_name = tag_ref.split("/")[-1]
            df.loc[df["name"] == df_name, "appearance"] = "field-list"

        elif tag_appearance is not None:
            df.loc[df["name"] == tag_ref_to_name, "appearance"] = tag_appearance


def fill_labels():
    global df
    labels = soup.find("itext").find_all("translation", lang="en")

    for label in labels:
        for text in label.find_all("text"):
            text_id = text.get("id")
            text_id_regex = re.findall(r"\/[^\s=':)]+", text_id)
            text_id_to_name = "_".join(text_id_regex[0].split("/")[1:])

            text_value = text.find("value", form="markdown")
            if text_value is not None:
                df.loc[df["name"] == text_id_to_name, "label"] = text_value.get_text()

            else:
                text_value = text.find("value")
                df.loc[df["name"] == text_id_to_name, "label"] = text_value.get_text()


loadLookupTables()
print("lookup tables loaded")

parseForm = build_form_structure()
print("form structure generated")
traverse(parseForm)
print("form structure traversed")
parse_binds()
print("binds parsed")
parse_body()
print("body parsed")
fill_labels()
print("labels filled")

# currently this assumes that all non types are notes, but this may not be the case all the tie
# but for this CHT form it works, maybe this can be improved in the future with more XML files and identifying more types
missing_types = df.loc[df["type"].isna()]
df["type"] = df["type"].fillna("note")
print("completed")

# remove labels from end_group
df.loc[df["type"] == "end_group", "label"] = ""

# remove appearence from end_group
df.loc[df["type"] == "end_group", "appearance"] = ""

# remove relevant from end_group
df.loc[df["type"] == "end_group", "relevant"] = ""

output_excel_file = "./cht.xlsx"

df = df.drop(0)

with pd.ExcelWriter(output_excel_file) as writer:
    df.to_excel(writer, sheet_name="survey", index=False)
    df_choice.to_excel(writer, sheet_name="choices", index=False)
print("excel file generated")
