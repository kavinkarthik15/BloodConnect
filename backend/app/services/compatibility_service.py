BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

COMPATIBILITY_RULES = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["A-", "O-"],
    "A+": ["A-", "A+", "O-", "O+"],
    "B-": ["B-", "O-"],
    "B+": ["B-", "B+", "O-", "O+"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB-", "AB+", "A-", "A+", "B-", "B+", "O-", "O+"],
}


def is_potentially_compatible(donor_group: str, required_group: str) -> bool:
    return donor_group in COMPATIBILITY_RULES.get(required_group, [])


def get_compatibility_type(donor_group: str, required_group: str) -> str:
    if donor_group == required_group:
        return "Exact match"
    if is_potentially_compatible(donor_group, required_group):
        return "Potentially compatible"
    return "Not compatible"


def get_potential_donor_groups(required_group: str):
    return [group for group in BLOOD_GROUPS if is_potentially_compatible(group, required_group)]
