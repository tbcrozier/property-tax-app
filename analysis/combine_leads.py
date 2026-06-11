#!/usr/bin/env python3
"""
Combines all *v2.csv lead files into a single referral CSV.
Extracts zipcode from filename and parses owner_address into city, state, zip.
"""

import pandas as pd
import glob
import os
import re


def extract_zipcode_from_filename(filepath: str) -> str:
    """Extract the zipcode from a filename like '37115_leads_v2.csv'."""
    basename = os.path.basename(filepath)
    match = re.match(r'^(\d+)_leads_v2\.csv$', basename)
    if match:
        return match.group(1)
    return ""


def parse_owner_address(address: str) -> tuple[str, str, str]:
    """
    Parse owner_address field into city, state, zip.
    Expected format: "STREET, CITY, STATE, ZIP" or similar variations.
    """
    if pd.isna(address) or not address:
        return ("", "", "")

    parts = [p.strip() for p in address.split(",")]

    if len(parts) >= 4:
        # Standard format: STREET, CITY, STATE, ZIP
        city = parts[-3]
        state = parts[-2]
        zipcode = parts[-1]
        return (city, state, zipcode)
    elif len(parts) == 3:
        # Possibly: CITY, STATE, ZIP (no street)
        city = parts[0]
        state = parts[1]
        zipcode = parts[2]
        return (city, state, zipcode)
    elif len(parts) == 2:
        # Possibly: STATE, ZIP
        return ("", parts[0], parts[1])
    else:
        return ("", "", "")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")

    # Find all v2 lead files
    pattern = os.path.join(data_dir, "*_leads_v2.csv")
    files = glob.glob(pattern)

    if not files:
        print(f"No files matching pattern: {pattern}")
        return

    print(f"Found {len(files)} files to process:")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    all_data = []

    for filepath in files:
        zipcode = extract_zipcode_from_filename(filepath)
        print(f"\nProcessing {os.path.basename(filepath)} (zipcode: {zipcode})...")

        df = pd.read_csv(filepath)

        # Parse owner_address into city, state, zip
        parsed = df["owner_address"].apply(parse_owner_address)
        df["city"] = parsed.apply(lambda x: x[0])
        df["state"] = parsed.apply(lambda x: x[1])
        df["zip"] = parsed.apply(lambda x: x[2])

        # Add zipcode from filename as first column
        df["zipcode"] = zipcode

        # Select and rename columns as needed
        output_df = df[[
            "zipcode",
            "parid",
            "address",
            "owner_name",
            "owner_address",
            "city",
            "state",
            "zip",
            "current_assessment",
            "median_comp_sale_price",
            "over_assessment",
            "pct_over_median",
            "estimated_savings",
            "num_comparables"
        ]].copy()

        # Rename owner_name to owner
        output_df = output_df.rename(columns={"owner_name": "owner"})

        # Convert pct_over_median to decimal (e.g., 207.0 -> 2.07)
        output_df["pct_over_median"] = output_df["pct_over_median"] / 100

        all_data.append(output_df)
        print(f"  Loaded {len(output_df)} records")

    # Combine all data
    combined = pd.concat(all_data, ignore_index=True)

    # Write output
    output_path = os.path.join(data_dir, "tpta_davidson_referrals.csv")
    combined.to_csv(output_path, index=False)

    print(f"\nWrote {len(combined)} total records to {output_path}")


if __name__ == "__main__":
    main()
