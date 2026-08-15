import os
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

# Input CSV file
INPUT_FILE = "student_enrollment_raw.csv"

# Output directory
OUTPUT_DIR = Path("output")

# Output files
CLEANED_FILE = OUTPUT_DIR / "cleaned_students.csv"
FAILED_FILE = OUTPUT_DIR / "failed_students.csv"

# Number of records sent to OpenAI at one time
BATCH_SIZE = 10

# Number of times to retry a failed OpenAI request
MAX_RETRIES = 3

# Seconds to wait between retries
RETRY_DELAY_SECONDS = 2


# ============================================================
# REQUIRED CSV COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "Student_ID",
    "Name",
    "Email",
    "Phone",
    "Course",
    "Fee_Paid",
    "City",
    "Enrolled_Date",
]


# ============================================================
# PYDANTIC MODELS
#
# These models define the structure we expect from OpenAI.
# ============================================================

class CleanedStudent(BaseModel):
    Student_ID: str = Field(
        description=(
            "Student ID. Must be STUD followed by exactly "
            "4 digits. Otherwise use INVALID."
        )
    )

    Name: str = Field(
        description=(
            "Normalized student name using proper capitalization."
        )
    )

    Email: str = Field(
        description=(
            "Normalized lowercase email address. "
            "Use INVALID if clearly invalid."
        )
    )

    Phone: str = Field(
        description=(
            "Phone number containing digits only. "
            "Use INVALID if clearly invalid."
        )
    )

    Course: str = Field(
        description="Normalized course name."
    )
    # Fee_Paid: str = Field(
    #     description=(
    #         "Normalized numeric fee amount represented as a string. "
    #         "Use INVALID if it cannot be reliably determined."
    #     )
    # )

    City: str = Field(
        description="Normalized city name."
    )

    Enrolled_Date: str = Field(
        description=(
            "Enrollment date in YYYY-MM-DD format. "
            "Use INVALID if it cannot be reliably determined."
        )
    )


class CleanedStudentsResponse(BaseModel):
    students: List[CleanedStudent] = Field(
        description=(
            "Exactly one cleaned student for every input student."
        )
    )


# ============================================================
# OPENAI CLIENT
# ============================================================

def create_openai_client():
    """
    Load the OpenAI API key and model from the .env file.

    Expected .env:

        OPENAI_API_KEY=your_api_key_here
        OPENAI_MODEL=gpt-5-mini
    """

    # --------------------------------------------------------
    # Locate .env next to this Python script.
    #
    # This makes the program work even if it is launched
    # from another working directory.
    # --------------------------------------------------------

    env_file = (
        Path(__file__).resolve().parent / ".env"
    )

    # --------------------------------------------------------
    # Load environment variables
    # --------------------------------------------------------

    load_dotenv(
        dotenv_path=env_file
    )

    # --------------------------------------------------------
    # Read OpenAI API key
    # --------------------------------------------------------

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "\n"
            "OPENAI_API_KEY was not found.\n\n"
            f"Expected .env file:\n"
            f"{env_file}\n\n"
            "Create the .env file with:\n\n"
            "OPENAI_API_KEY=your_openai_api_key_here\n"
            "OPENAI_MODEL=gpt-5-mini\n"
        )

    # Remove accidental whitespace
    api_key = api_key.strip()

    # --------------------------------------------------------
    # Read model name
    # --------------------------------------------------------

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5-mini"
    ).strip()

    # --------------------------------------------------------
    # Create OpenAI client
    # --------------------------------------------------------

    client = OpenAI(
        api_key=api_key
    )

    print("OpenAI API key loaded successfully.")
    print(f"OpenAI model: {model}")

    return client, model


# ============================================================
# LOAD CSV
# ============================================================

def load_csv(file_path: str) -> pd.DataFrame:
    """
    Load the input CSV file into a Pandas DataFrame.
    """

    print()
    print("=" * 60)
    print("STEP 1: LOAD CSV")
    print("=" * 60)

    path = Path(file_path)

    # Check whether file exists
    if not path.exists():

        raise FileNotFoundError(
            f"Input CSV file not found: {file_path}"
        )

    # Read CSV as strings so we don't accidentally convert
    # Student_ID or phone numbers into numbers.
    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False
    )

    print(f"Input file : {file_path}")
    print(f"Rows found : {len(df)}")

    return df


# ============================================================
# VALIDATE CSV COLUMNS
# ============================================================

def validate_columns(df: pd.DataFrame) -> None:
    """
    Make sure all required columns exist in the CSV.
    """

    print()
    print("=" * 60)
    print("STEP 2: VALIDATE CSV")
    print("=" * 60)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    print("All required columns are present.")


# ============================================================
# CLEAN RAW CSV VALUE
# ============================================================

def clean_raw_value(value) -> str:
    """
    Convert a raw CSV value into a safe string.
    """

    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# PREPARE RECORDS
# ============================================================

def prepare_records(
    df: pd.DataFrame
) -> List[dict]:
    """
    Convert DataFrame rows into dictionaries.
    """

    records = []

    for _, row in df.iterrows():

        record = {
            column: clean_raw_value(
                row[column]
            )
            for column in REQUIRED_COLUMNS
        }

        records.append(record)

    return records


# ============================================================
# CREATE BATCHES
# ============================================================

def create_batches(
    records: List[dict],
    batch_size: int
):
    """
    Split records into smaller batches.

    Example:

        50 records
        batch size = 10

        Batch 1 = records 1-10
        Batch 2 = records 11-20
        ...
    """

    for i in range(
        0,
        len(records),
        batch_size
    ):

        yield records[
            i:i + batch_size
        ]


# ============================================================
# OPENAI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a professional student enrollment data-cleaning engine.

Your job is to clean and normalize student enrollment records.

IMPORTANT GENERAL RULES:

1. Process every input record.
2. Return exactly one output record for every input record.
3. Never remove records.
4. Never invent information.
5. Preserve the original meaning of the data.
6. If a value cannot be reliably determined, use "INVALID".


STUDENT_ID RULES:

The Student_ID must match:

    STUD + exactly 4 digits

Examples:

    stud1001  -> STUD1001
    STUD1002  -> STUD1002
    stud 1003 -> STUD1003

Invalid examples:

    ABC123
    STUD123
    STUD12345
    STUDENT1001

If the ID is invalid, return:

    INVALID


NAME RULES:

1. Remove leading and trailing whitespace.
2. Collapse multiple spaces.
3. Use proper name capitalization.

Examples:

    "  JOHN DOE  "       -> "John Doe"
    "PRIYA   KUMAR"      -> "Priya Kumar"
    "ravi kumar"         -> "Ravi Kumar"


EMAIL RULES:

1. Remove leading/trailing whitespace.
2. Remove accidental spaces around @.
3. Convert to lowercase.
4. Do not invent an email address.

Examples:

    " JOHN@GMAIL.COM "  -> "john@gmail.com"
    "john @ gmail.com"  -> "john@gmail.com"

If the email is clearly invalid:

    INVALID


PHONE RULES:

1. Remove spaces.
2. Remove hyphens.
3. Remove brackets.
4. Keep digits only.
5. Do not invent missing digits.

Example:

    "98765-43210" -> "9876543210"

If clearly invalid:

    INVALID


COURSE RULES:

Normalize equivalent course names.

Examples:

    "python"
    "PYTHON"
    "Python"
    "python programming"
    "PYTHON PROGRAMMING"

should become:

    Python Programming

Use consistent course names.


FEE_PAID RULES:

Yes or YES  then covert to TRUE else FALSE

Do not invent values.


CITY RULES:

Normalize city names.

Examples:

    "chennai"   -> "Chennai"
    "CHENNAI"   -> "Chennai"
    " chennai " -> "Chennai"

Only normalize obvious aliases when you are confident.

Do not invent a city.


ENROLLED_DATE RULES:

Convert recognizable dates into:

    YYYY-MM-DD

Examples:

    "2026/01/10"  -> "2026-01-10"
    "10-01-2026"  -> "2026-01-10"
    "Jan 10, 2026" -> "2026-01-10"

If the date is ambiguous and cannot be reliably determined:

    INVALID

Do not invent dates.


FINAL RULE:

Return exactly one cleaned record for every input record.
"""


# ============================================================
# SEND BATCH TO OPENAI
# ============================================================

def clean_batch_with_openai(
    client: OpenAI,
    model: str,
    batch: List[dict],
    batch_number: int,
    total_batches: int
) -> List[dict]:
    """
    Send one batch to OpenAI and return cleaned records.
    """

    print()
    print(
        f"Processing batch "
        f"{batch_number}/{total_batches} "
        f"({len(batch)} records)..."
    )

    # --------------------------------------------------------
    # Convert records into a prompt
    # --------------------------------------------------------

    user_prompt = f"""
Clean the following student enrollment records.

INPUT RECORDS:

{batch}

IMPORTANT:

Return exactly {len(batch)} cleaned student records.

Do not remove any record.
Do not add any record.
Do not invent missing information.
"""

    # --------------------------------------------------------
    # Retry OpenAI request if it fails
    # --------------------------------------------------------

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            # ------------------------------------------------
            # Call OpenAI Structured Outputs
            # ------------------------------------------------

            response = client.responses.parse(
                model=model,

                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],

                text_format=CleanedStudentsResponse,
            )

            # ------------------------------------------------
            # Check response
            # ------------------------------------------------

            if not response.output:

                raise RuntimeError(
                    "OpenAI returned an empty response."
                )

            parsed_result = None

            # ------------------------------------------------
            # Find parsed structured output
            # ------------------------------------------------

            for output_item in response.output:

                if output_item.type != "message":
                    continue

                for content_item in output_item.content:

                    if content_item.type != "output_text":
                        continue

                    parsed_result = (
                        content_item.parsed
                    )

                    if parsed_result is not None:
                        break

                if parsed_result is not None:
                    break

            # ------------------------------------------------
            # Make sure parsing succeeded
            # ------------------------------------------------

            if parsed_result is None:

                raise RuntimeError(
                    "Could not parse OpenAI structured output."
                )

            # ------------------------------------------------
            # Extract cleaned students
            # ------------------------------------------------

            cleaned_students = (
                parsed_result.students
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Make sure OpenAI returned exactly the same
            # number of records we sent.
            # ------------------------------------------------

            if len(cleaned_students) != len(batch):

                raise RuntimeError(
                    "Record count mismatch. "
                    f"Input={len(batch)}, "
                    f"Output={len(cleaned_students)}"
                )

            print(
                f"Batch {batch_number} "
                f"completed successfully."
            )

            # ------------------------------------------------
            # Convert Pydantic objects to dictionaries
            # ------------------------------------------------

            return [
                student.model_dump()
                for student in cleaned_students
            ]

        except Exception as e:

            print(
                f"Batch {batch_number} failed "
                f"(attempt {attempt}/{MAX_RETRIES}): "
                f"{e}"
            )

            # ------------------------------------------------
            # Wait before retrying
            # ------------------------------------------------

            if attempt < MAX_RETRIES:

                print(
                    f"Retrying in "
                    f"{RETRY_DELAY_SECONDS} seconds..."
                )

                time.sleep(
                    RETRY_DELAY_SECONDS
                )

    # --------------------------------------------------------
    # All retries failed
    # --------------------------------------------------------

    raise RuntimeError(
        f"Batch {batch_number} failed after "
        f"{MAX_RETRIES} attempts."
    )


# ============================================================
# VALIDATE STUDENT ID
# ============================================================

def validate_student_id(
    value: str
) -> str:
    """
    Validate Student_ID using Python regex.

    Required format:

        STUD + exactly 4 digits
    """

    value = clean_raw_value(
        value
    ).upper()

    if re.fullmatch(
        r"STUD\d{4}",
        value
    ):

        return value

    return "INVALID"


# ============================================================
# VALIDATE EMAIL
# ============================================================

def validate_email(
    value: str
) -> str:
    """
    Perform basic email validation.
    """

    value = clean_raw_value(
        value
    ).lower()

    if value == "INVALID":
        return "INVALID"

    # Basic email pattern
    pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if re.fullmatch(
        pattern,
        value
    ):

        return value

    return "INVALID"


# ============================================================
# VALIDATE PHONE
# ============================================================

def validate_phone(
    value: str
) -> str:
    """
    Validate and normalize phone number.
    """

    value = clean_raw_value(
        value
    )

    if value.upper() == "INVALID":
        return "INVALID"

    # Keep digits only
    digits = re.sub(
        r"\D",
        "",
        value
    )

    # Basic phone length validation
    if 7 <= len(digits) <= 15:
        return digits

    return "INVALID"


# ============================================================
# VALIDATE FEE
# ============================================================

def validate_fee(
    value: str
) -> str:
    """
    Convert fee indicator to TRUE/FALSE per rules.
    """

    value = clean_raw_value(value)

    # Per project rules: if the fee field indicates Yes (or variants),
    # convert to "TRUE"; otherwise convert to "FALSE".
    if not value:
        return "FALSE"

    normalized = value.strip().lower()

    true_values = {"yes", "y", "true", "t", "1"}

    if normalized in true_values:
        return "TRUE"

    return "FALSE"


# ============================================================
# VALIDATE DATE
# ============================================================

def validate_date(
    value: str
) -> str:
    """
    Make sure date is YYYY-MM-DD.
    """

    value = clean_raw_value(
        value
    )

    if value.upper() == "INVALID":
        return "INVALID"

    try:

        parsed_date = datetime.strptime(
            value,
            "%Y-%m-%d"
        )

        return parsed_date.strftime(
            "%Y-%m-%d"
        )

    except ValueError:

        return "INVALID"


# ============================================================
# FINAL PYTHON VALIDATION
# ============================================================

def final_python_validation(
    student: dict
) -> dict:
    """
    Perform deterministic validation after OpenAI cleanup.

    OpenAI performs semantic normalization.
    Python performs deterministic validation.
    """

    cleaned = {

        "Student_ID": validate_student_id(
            student.get(
                "Student_ID",
                ""
            )
        ),

        "Name": clean_raw_value(
            student.get(
                "Name",
                ""
            )
        ),

        "Email": validate_email(
            student.get(
                "Email",
                ""
            )
        ),

        "Phone": validate_phone(
            student.get(
                "Phone",
                ""
            )
        ),

        "Course": clean_raw_value(
            student.get(
                "Course",
                ""
            )
        ),

        "Fee_Paid": validate_fee(
            student.get(
                "Fee_Paid",
                ""
            )
        ),

        "City": clean_raw_value(
            student.get(
                "City",
                ""
            )
        ),

        "Enrolled_Date": validate_date(
            student.get(
                "Enrolled_Date",
                ""
            )
        ),
    }

    return cleaned


# ============================================================
# CHECK INVALID FIELDS
# ============================================================

def has_invalid_field(
    student: dict
) -> bool:
    """
    Check whether the student record contains INVALID.
    """

    for value in student.values():

        if str(value).upper() == "INVALID":

            return True

    return False


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    cleaned_records: List[dict],
    failed_records: List[dict]
) -> None:
    """
    Save cleaned and failed records to CSV files.
    """

    print()
    print("=" * 60)
    print("STEP 5: SAVE OUTPUT")
    print("=" * 60)

    # --------------------------------------------------------
    # Create output directory if it doesn't exist
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Save cleaned records
    # --------------------------------------------------------

    cleaned_df = pd.DataFrame(
        cleaned_records,
        columns=REQUIRED_COLUMNS
    )

    cleaned_df.to_csv(
        CLEANED_FILE,
        index=False
    )

    print(
        f"Cleaned CSV : {CLEANED_FILE}"
    )

    # --------------------------------------------------------
    # Save failed records
    # --------------------------------------------------------

    if failed_records:

        failed_df = pd.DataFrame(
            failed_records,
            columns=REQUIRED_COLUMNS
        )

        failed_df.to_csv(
            FAILED_FILE,
            index=False
        )

        print(
            f"Failed CSV  : {FAILED_FILE}"
        )

    else:

        print(
            "Failed CSV  : No records with INVALID fields."
        )


# ============================================================
# PRINT ETL SUMMARY
# ============================================================

def print_summary(
    total_records: int,
    cleaned_records: List[dict],
    failed_records: List[dict]
) -> None:
    """
    Print final ETL summary.
    """

    successful_records = (
        len(cleaned_records)
        - len(failed_records)
    )

    print()
    print("=" * 60)
    print("ETL SUMMARY")
    print("=" * 60)

    print(
        f"Input records          : "
        f"{total_records}"
    )

    print(
        f"Output records         : "
        f"{len(cleaned_records)}"
    )

    print(
        f"Records with INVALID   : "
        f"{len(failed_records)}"
    )

    print(
        f"Successfully processed : "
        f"{successful_records}"
    )

    print()
    print(
        f"Cleaned file           : "
        f"{CLEANED_FILE}"
    )

    if failed_records:

        print(
            f"Failed file            : "
            f"{FAILED_FILE}"
        )

    print()
    print(
        "ETL completed successfully."
    )


# ============================================================
# MAIN ETL PIPELINE
# ============================================================

def main():

    print()
    print("=" * 60)
    print("STUDENT DATA CLEANUP ETL")
    print("=" * 60)

    try:

        # ----------------------------------------------------
        # STEP 0
        # Load .env and create OpenAI client
        # ----------------------------------------------------

        client, model = (
            create_openai_client()
        )

        # ----------------------------------------------------
        # STEP 1
        # Load CSV
        # ----------------------------------------------------

        df = load_csv(
            INPUT_FILE
        )

        # ----------------------------------------------------
        # STEP 2
        # Validate CSV structure
        # ----------------------------------------------------

        validate_columns(
            df
        )

        # ----------------------------------------------------
        # STEP 3
        # Convert CSV rows into Python records
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("STEP 3: READ RECORDS")
        print("=" * 60)

        records = prepare_records(
            df
        )

        print(
            f"Prepared {len(records)} "
            f"student records."
        )

        if not records:

            print(
                "No records found. Exiting."
            )

            return

        # ----------------------------------------------------
        # STEP 4
        # Split records into batches
        # ----------------------------------------------------

        batches = list(
            create_batches(
                records,
                BATCH_SIZE
            )
        )

        total_batches = len(
            batches
        )

        print(
            f"Batch size    : "
            f"{BATCH_SIZE}"
        )

        print(
            f"Total batches : "
            f"{total_batches}"
        )

        # ----------------------------------------------------
        # STEP 5
        # OpenAI cleanup
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("STEP 4: OPENAI CLEANUP")
        print("=" * 60)

        cleaned_records = []

        for (
            batch_number,
            batch
        ) in enumerate(
            batches,
            start=1
        ):

            batch_result = (
                clean_batch_with_openai(
                    client=client,
                    model=model,
                    batch=batch,
                    batch_number=batch_number,
                    total_batches=total_batches
                )
            )

            # ------------------------------------------------
            # Final Python validation
            # ------------------------------------------------

            for student in batch_result:

                validated_student = (
                    final_python_validation(
                        student
                    )
                )

                cleaned_records.append(
                    validated_student
                )

        # ----------------------------------------------------
        # Verify final record count
        # ----------------------------------------------------

        if len(cleaned_records) != len(records):

            raise RuntimeError(
                "Final record count mismatch. "
                f"Input={len(records)}, "
                f"Output={len(cleaned_records)}"
            )

        # ----------------------------------------------------
        # Identify records containing INVALID fields
        # ----------------------------------------------------

        failed_records = [
            student
            for student in cleaned_records
            if has_invalid_field(
                student
            )
        ]

        # ----------------------------------------------------
        # Save results
        # ----------------------------------------------------

        save_results(
            cleaned_records=cleaned_records,
            failed_records=failed_records
        )

        # ----------------------------------------------------
        # Print summary
        # ----------------------------------------------------

        print_summary(
            total_records=len(records),
            cleaned_records=cleaned_records,
            failed_records=failed_records
        )

    except FileNotFoundError as e:

        print()
        print(
            f"FILE ERROR: {e}"
        )

    except ValueError as e:

        print()
        print(
            f"VALIDATION ERROR: {e}"
        )

    except RuntimeError as e:

        print()
        print(
            f"ETL ERROR: {e}"
        )

    except Exception as e:

        print()
        print(
            f"UNEXPECTED ERROR: "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()