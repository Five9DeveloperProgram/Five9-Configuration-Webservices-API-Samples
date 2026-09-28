import re

# Grouping expressions reference criteria by 1-based ordinal position only;
# campaignFilterCriterion carries no id, so position is the sole identity.
CRITERION_INDEX_PATTERN = re.compile(r"\d+")
DEMYSTIFIED_CONDITION_PATTERN = re.compile(
    r"\[([^\[\]\r\n]*?::[^\[\]\r\n]*?::[^\[\]\r\n]*?)\]" r"(?:--)?(?:\[\d+\])?"
)
GROUPING_TOKEN_PATTERN = re.compile(r"AND|OR|NOT|\d+|\(|\)")


def validate_grouping_tokens(tokens, criterion_count):
    """Validate a tokenized custom grouping expression."""
    position = 0

    def current_token():
        return tokens[position] if position < len(tokens) else None

    def parse_primary():
        nonlocal position
        token = current_token()
        if token and token.isdigit():
            criterion_index = int(token)
            if not 1 <= criterion_index <= criterion_count:
                raise ValueError(
                    f"grouping references criterion {criterion_index}, but only "
                    f"{criterion_count} criteria exist"
                )
            position += 1
            return
        if token == "(":
            position += 1
            parse_or_expression()
            if current_token() != ")":
                raise ValueError("grouping expression has an unclosed parenthesis")
            position += 1
            return
        raise ValueError(
            f"grouping expression expected a criterion or '(', got {token!r}"
        )

    def parse_not_expression():
        nonlocal position
        if current_token() == "NOT":
            position += 1
            parse_not_expression()
            return
        parse_primary()

    def parse_and_expression():
        nonlocal position
        parse_not_expression()
        while current_token() == "AND":
            position += 1
            parse_not_expression()

    def parse_or_expression():
        nonlocal position
        parse_and_expression()
        while current_token() == "OR":
            position += 1
            parse_and_expression()

    if not tokens:
        raise ValueError("grouping expression is empty")
    parse_or_expression()
    if position != len(tokens):
        raise ValueError(
            f"grouping expression has an orphaned token {tokens[position]!r}"
        )


def criterion_key(criterion):
    """Identity of a criterion as the Admin UI sees it: the comparison triple."""
    return (
        criterion["leftValue"],
        criterion["compareOperator"],
        criterion["rightValue"],
    )


def find_duplicate_criteria(profile_filter):
    """
    Locates criteria rows that repeat an earlier row's comparison triple.

    Returns a list of dicts, one per duplicated triple, each with the criterion
    key, the 1-based index kept (first occurrence), and the indexes to drop.
    """
    positions = {}
    for index, criterion in enumerate(profile_filter.get("crmCriteria") or [], 1):
        positions.setdefault(criterion_key(criterion), []).append(index)

    return [
        {"key": key, "keep": found[0], "drop": found[1:]}
        for key, found in positions.items()
        if len(found) > 1
    ]


def canonical_expression(expression, crm_criteria):
    """
    Rewrites a grouping expression so each index token names the *condition* it
    points at rather than its ordinal slot.

    Two expressions with identical canonical forms are logically equivalent
    regardless of how their rows are numbered, which makes this an exact
    equivalence proof rather than a sampled one.
    """
    condition_ids = {}
    for criterion in crm_criteria:
        condition_ids.setdefault(criterion_key(criterion), len(condition_ids) + 1)
    index_to_id = {
        index: condition_ids[criterion_key(criterion)]
        for index, criterion in enumerate(crm_criteria, 1)
    }
    return CRITERION_INDEX_PATTERN.sub(
        lambda match: f"C{index_to_id[int(match.group())]}", expression
    )


def renumber_expression(expression, index_map):
    """
    Applies an old-index -> new-index mapping to a grouping expression.

    Substitutes whole number tokens in a single pass; replacing digits
    individually would corrupt multi-digit indexes (remapping 4->3 would
    otherwise rewrite 14 as 13).
    """
    return CRITERION_INDEX_PATTERN.sub(
        lambda match: str(index_map[int(match.group())]), expression
    )


def repair_duplicate_criteria(profile_filter):
    """
    Removes duplicate criteria rows and renumbers the grouping expression to match.

    Duplicate rows were once accepted by the API but are now silently collapsed by
    the Admin UI, which leaves the grouping expression referencing more rows than
    the UI recognizes and makes the filter unsavable. This keeps the first
    occurrence of each triple, points every reference at it, and shifts the
    surviving rows down to close the gaps.

    Returns a dict describing the repair. "equivalent" is an exact proof that the
    rewritten filter selects the same contacts; callers must refuse to push when
    it is False.
    """
    crm_criteria = profile_filter.get("crmCriteria") or []
    grouping = profile_filter.get("grouping") or {}
    expression = grouping.get("expression") or ""

    duplicates = find_duplicate_criteria(profile_filter)
    if not duplicates:
        return {"changed": False, "duplicates": []}

    kept = []
    first_seen = {}
    index_map = {}
    for index, criterion in enumerate(crm_criteria, 1):
        key = criterion_key(criterion)
        if key in first_seen:
            index_map[index] = first_seen[key]
        else:
            kept.append(criterion)
            first_seen[key] = len(kept)
            index_map[index] = len(kept)

    new_expression = renumber_expression(expression, index_map)

    return {
        "changed": True,
        "duplicates": duplicates,
        "index_map": index_map,
        "renumbered": {old: new for old, new in index_map.items() if old != new},
        "rows_before": len(crm_criteria),
        "rows_after": len(kept),
        "original_expression": expression,
        "crmCriteria": kept,
        "grouping": {
            "expression": new_expression,
            "type": grouping.get("type", "Custom"),
        },
        "orderByFields": profile_filter.get("orderByFields") or [],
        "equivalent": canonical_expression(expression, crm_criteria)
        == canonical_expression(new_expression, kept),
    }


def prettify(ugly="", open_set="{[(<", close_set="}])>"):
    """
    Formats a string with indentation and newlines based on specified delimiters.

    Args:
        ugly (str): The string to be formatted.
        open_set (str): A string containing all opening delimiters to be used for indentation.
        close_set (str): A string containing all closing delimiters to be used for de-indentation.

    Returns:
        str: The formatted string with indentation and newlines.
    """
    # Add a space to the end of the string to ensure the last character is processed
    ugly += " "

    # Initialize a variable to keep track of the current indentation level
    level = 0

    # Remove any double spaces in the string
    while ugly.find("  ") > -1:
        ugly = ugly.replace("  ", " ")
    while ugly.find("( (") > -1:
        ugly = ugly.replace("( (", "((")
    while ugly.find(") )") > -1:
        ugly = ugly.replace(") )", "))")

    # Initialize a variable to store the formatted output
    output = ""

    # Iterate through each character in the string
    for idx, char in enumerate(ugly):
        # If the character is an opening delimiter, increase the indentation level and add a newline
        if char in open_set:
            level += 1
            output += char + "\n" + "\t" * (level)
        # If the character is a closing delimiter, decrease the indentation level and add a newline
        elif char in close_set:
            level -= 1
            output += "\n" + "\t" * level + char
            # If the next character is not a closing delimiter, add an extra newline
            if ugly[idx + 1] not in close_set:
                output += "\n"
        # If the character is "AND" preceded by a space, add a newline and indent
        elif ugly[idx - 1 : idx + 4] == " AND ":
            output += "\n" + "\t" * level + " " * (-4) + char
        # If the character is "OR" preceded by a space, add a newline and indent
        elif ugly[idx - 1 : idx + 3] == " OR ":
            output += "\n" + "\t" * level + " " * (-3) + char
        # For all other characters, simply add them to the output string
        else:
            output += char

    # Return the formatted string
    return output


def demystify_filter(profile_filter, verbose=False):
    """
    Takes a profile filter information object with a ["grouping"]["expression"] attribute and returns a demystified expression string.

    Args:
        profile_filter (dict): A dictionary containing the profile filter information.
        verbose (bool, optional): Whether to spool output to console. Defaults to False.

    Returns:
        str: The demystified expression string.
    """
    # Compile a regular expression to match numbers
    numbers = re.compile(r"(\d+)")

    # Set up placeholder strings for parentheses
    parens_open = "|||||"
    parens_close = "+_+_+_+_"

    # Create a dictionary to map expression operator strings to their corresponding symbols
    expression_operators = {
        "Equals": "=",
        "NotEqual": "!=",
        "Like": "LIKE",
        "Less": "<",
        "LessOrEqual": "<=",
        "Greater": ">",
        "GreaterOrEqual": ">=",
    }

    # Get the grouping expression from the profile filter object
    grouping_expression = profile_filter["grouping"]["expression"]

    # Replace numbers in the expression with brackets
    grouping_expression = numbers.sub(r"[\1]", grouping_expression)

    # Iterate through each criteria in the filter
    for idx, criteria in enumerate(profile_filter["crmCriteria"]):
        # Get the index of the current criteria
        i = idx + 1

        # Replace parentheses in the right value with placeholder strings
        rightValue = (
            (criteria["rightValue"] or "null")
            .replace("(", parens_open)
            .replace(")", parens_close)
        )

        # Construct the condition string using the left value, compare operator, and right value
        condition = (
            f'{criteria["leftValue"]} ::{criteria["compareOperator"]}:: {rightValue}'
        )

        # Replace the bracketed number in the grouping expression with the condition string
        grouping_expression = grouping_expression.replace(
            f"[{i}]", f"[{condition}][{i}]"
        )

    # Use the prettify function to format the grouping expression
    demystified = (
        prettify(grouping_expression, "(", ")")
        .replace(parens_open, "(")
        .replace(parens_close, ")")
    )

    # If verbose is True, print the demystified expression to the console
    if verbose == True:
        print(f"{demystified}")

    # Return the demystified expression
    return demystified


def remystify_filter_in_place(nice_filter):
    """
    Converts a "nice filter" string into a format that can be used by the Five9 Configuration Webservices API.
    """
    nice_filter = re.sub(r"\[.*?\]\[", "", nice_filter)
    nice_filter = nice_filter.replace("]", "").replace("\t", "").replace("\n", "")
    return nice_filter


def remystify_filter(nice_filter, verbose=False):
    """
    Converts a "nice filter" string into a format that can be used by the Five9 Configuration Webservices API.

    Args:
        nice_filter (str): A "nice filter" string that contains filter conditions in a human-readable format.

    Returns:
        dict: A dictionary that contains the converted filter criteria, grouping expression, and order by fields.
    """
    criterion_indexes = {}
    crm_criteria = []

    def replace_condition(match):
        condition = match.group(1)
        parts = [part.strip() for part in condition.split("::", 2)]
        if len(parts) != 3 or not parts[0] or not parts[1]:
            raise ValueError(f"invalid filter condition: [{condition}]")

        left_value, compare_operator, right_value = parts
        criterion_key = (left_value, compare_operator, right_value)
        if criterion_key not in criterion_indexes:
            criterion_indexes[criterion_key] = len(crm_criteria) + 1
            crm_criteria.append(
                {
                    "compareOperator": compare_operator,
                    "leftValue": left_value,
                    "rightValue": "" if right_value == "null" else right_value,
                }
            )
        return str(criterion_indexes[criterion_key])

    new_grouping_expression, condition_count = DEMYSTIFIED_CONDITION_PATTERN.subn(
        replace_condition, nice_filter
    )
    if condition_count == 0:
        raise ValueError("filter does not contain any demystified conditions")

    grouping_tokens = []
    position = 0
    while position < len(new_grouping_expression):
        if new_grouping_expression[position].isspace():
            position += 1
            continue
        token_match = GROUPING_TOKEN_PATTERN.match(new_grouping_expression, position)
        if not token_match:
            unsupported_text = new_grouping_expression[position : position + 40]
            raise ValueError(
                "filter contains unsupported text outside its conditions near: "
                f"{unsupported_text}"
            )
        grouping_tokens.append(token_match.group())
        position = token_match.end()

    depth = 0
    for token in grouping_tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                break
    if depth != 0:
        raise ValueError("filter grouping expression has unbalanced parentheses")

    validate_grouping_tokens(grouping_tokens, len(crm_criteria))

    new_grouping_expression = " ".join(grouping_tokens)
    new_grouping_expression = new_grouping_expression.replace("( ", "(")
    new_grouping_expression = new_grouping_expression.replace(" )", ")")

    if verbose:
        for criterion, index in criterion_indexes.items():
            print(f"{index:02} {' ::'.join(criterion)}")
        print(new_grouping_expression)

    return {
        "crmCriteria": crm_criteria,
        "grouping": {"expression": new_grouping_expression, "type": "Custom"},
        "orderByFields": [],
    }
