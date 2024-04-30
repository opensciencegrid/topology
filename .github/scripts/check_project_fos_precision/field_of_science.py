from functools import lru_cache
from typing import Union
import string

import pandas as pd


@lru_cache()
def get_cip_df():

    cip_df = pd.read_excel("data/SED-CIP-2022.xlsx")

    # Drop the first two rows and make the third row the column title
    cip_df.columns = cip_df.iloc[2]
    cip_df = cip_df.iloc[3:]

    cip_df["BroadFieldId"] = cip_df['SED-CIP code'].apply(lambda x: get_id(x, 0))
    cip_df["MajorFieldId"] = cip_df['SED-CIP code'].apply(lambda x: get_id(x, 1))
    cip_df["DetailedFieldId"] = cip_df['SED-CIP code'].apply(lambda x: get_id(x, 2))

    return cip_df


def get_matching_rows(cip_df, broad_id, major_id, detailed_id):

    # Check the finest grain first
    detailed_rows = cip_df[(cip_df["BroadFieldId"] == broad_id) & (cip_df['MajorFieldId'] == major_id) & (
                cip_df["DetailedFieldId"] == detailed_id)]

    if len(detailed_rows) > 0:
        return detailed_rows

    # Check the major grain
    major_rows = cip_df[(cip_df["BroadFieldId"] == broad_id) & (cip_df['MajorFieldId'] == major_id)]

    if len(major_rows) > 0:
        return major_rows

    # Check the broad grain
    broad_rows = cip_df[cip_df["BroadFieldId"] == broad_id]

    if len(broad_rows) > 0:
        return broad_rows

    raise ValueError(f"No matching rows for {broad_id}.{major_id}{detailed_id}")


def map_id_to_fields_of_science(id: str):

    # Define the fields we hope to populate
    broad_field_of_science = None
    major_field_of_science = None
    detailed_field_of_science = None

    cip_df = get_cip_df()

    # If we have a direct match, return it
    direct_match = cip_df[cip_df["SED-CIP code"] == id]
    if len(direct_match) > 0:
        return [direct_match["New broad field"].values[0], direct_match["New major field"].values[0], direct_match["New detailed field"].values[0]]

    # Add the broad field
    broad_id = get_id(id, 0)
    major_id = get_id(id, 1)
    detailed_id = get_id(id, 2)

    try:
        matching_rows = get_matching_rows(cip_df, broad_id, major_id, detailed_id)
    except ValueError as e:
        print(id)
        return [broad_field_of_science, major_field_of_science, detailed_field_of_science]

    possible_broad_fields = set(map(lambda x: x[1]['New broad field'], matching_rows.iterrows()))
    if broad_id is not None:
        best_option = None
        max_rows = 0
        for possible_broad_field in set(map(lambda x: x[1]['New broad field'], matching_rows.iterrows())):
            l = len(cip_df[(cip_df["BroadFieldId"] == broad_id) & (cip_df["New broad field"] == possible_broad_field)])

            if l > max_rows:
                max_rows = l
                best_option = possible_broad_field

        print(f"Broad Field: {broad_id}.{major_id}{detailed_id} has possible values {possible_broad_fields} we picked {best_option}")

        broad_field_of_science = best_option

    possible_major_fields = set(map(lambda x: x[1]['New major field'], matching_rows.iterrows()))
    if major_id is not None:
        best_option = None
        max_rows = 0
        for possible_major_field in possible_major_fields:
            l = len(cip_df[(cip_df["BroadFieldId"] == broad_id) & (cip_df['MajorFieldId'] == major_id) & (
                        cip_df["New major field"] == possible_major_field)])
            if l > max_rows:
                max_rows = l
                best_option = possible_major_field

        print(f"Major Field: {broad_id}.{major_id}{detailed_id} has rows {possible_major_fields} we picked {best_option}")

        major_field_of_science = best_option

    possible_detailed_fields = set(map(lambda x: x[1]['New detailed field'], matching_rows.iterrows()))
    if detailed_id is not None:
        best_option = None
        max_rows = 0
        for possible_detailed_field in possible_detailed_fields:
            l = len(cip_df[(cip_df["BroadFieldId"] == broad_id) & (cip_df['MajorFieldId'] == major_id) & (
                        cip_df["DetailedFieldId"] == detailed_id) & (cip_df["New detailed field"] == possible_detailed_field)])
            if l > max_rows:
                max_rows = l
                best_option = possible_detailed_field

        print(f"Detailed Field: {broad_id}.{major_id}{detailed_id} has rows {possible_detailed_fields} we picked {best_option}")

        detailed_field_of_science = best_option

    return [broad_field_of_science, major_field_of_science, detailed_field_of_science]


def get_id(id: Union[float, str], granularity: int):

    # Check if None
    if pd.isna(id):
        return None

    # Fix up issues from reading the id as a float
    digits = [x for x in str(id) if x in string.digits]

    # If the first part is preceded with a 0, (01.2023)
    if len(str(id).split(".")[0]) == 1:
        digits = ['0', *digits]

    # If the number ends with a 0, (10.2320)
    if len(digits) % 2 == 1:
        digits = [*digits, '0']


    if len(digits) % 2 == 1:
        digits = ['0', *digits]

    if granularity == 0:
        return "".join(digits[:2])

    if granularity == 1:

        if len(digits) < 4:
            return None

        return "".join(digits[2:4])

    if granularity == 2:

        if len(digits) < 6:
            return None

        return "".join(digits[4:])


def tests():

    if get_id(1.0, 0) != "01":
        raise ValueError("Test failed")

    if get_id(1.0, 1) != "00":
        raise ValueError("Test failed")

    if get_id(10.2320, 2) != "20":
        raise ValueError("Test failed")

    if get_id(10.2320, 1) != "23":
        raise ValueError("Test failed")

    if get_id(10.2320, 0) != "10":
        raise ValueError("Test failed")

    if get_id(01.23, 2) != None:
        raise ValueError("Test failed")

    if get_id(01.23, 0) != "01":
        raise ValueError("Test failed")

    if map_id_to_fields_of_science("26.15") != ['Biological and biomedical sciences','Neurobiology and neurosciences', None]:
        raise ValueError("Test failed")

if __name__ == "__main__":
    tests()
    print("All tests passed")
