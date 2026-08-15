# n8n Student Enrollment ETL — README

This directory contains a GenAI-powered ETL pipeline built in n8n to clean and validate student enrollment CSV data. The pipeline was created as part of a "GenAI Architect — ETL Pipeline (n8n)" assignment and demonstrates how n8n can orchestrate file ingestion, call a language model to clean rows, post-process AI outputs, and write categorized CSV outputs.

Contents
- N8N-Assignment.json — Exported n8n workflow (importable into n8n Editor).
- GenAI_Architect_ETL_Pipeline_n8n_Assignment.pdf — Assignment brief describing goals and acceptance criteria.
- student_enrollment_raw.csv — Example raw input CSV with unclean/inconsistent records.
- Chennail_with_Email.csv — Example output: Chennai rows with valid emails.
- Chennai_with_invalid_email.csv — Chennai rows with invalid emails.
- Other_city_with_email.csv — Non-Chennai rows with valid emails.
- Other_City_Invalid_email.csv — Non-Chennai rows with invalid emails.

Project goal / Assignment summary
The assignment requires designing an n8n workflow that:
- Accepts an uploaded CSV of student enrollment rows, possibly messy or inconsistent.
- Uses a generative model (LLM) to clean and normalize each row according to a precise prompt and rules.
- Post-processes the model output safely (robust JSON parsing and normalization).
- Routes cleaned rows into four output CSVs: Chennai with valid email, Chennai with invalid email, Other cities with valid email, Other cities with invalid email.
- Demonstrates defensive coding and predictable routing for downstream use.

High-level workflow (node-by-node)
- On form submission (n8n formTrigger)
  - Trigger that accepts a CSV file upload (accepts .csv). This simulates a user uploading the raw data.

- Switch
  - Guards against empty uploads and ensures binary data exists before continuing.

- Extract from File
  - Converts the uploaded CSV into n8n items (one item per row) for downstream processing.

- Basic LLM Chain (LangChain node)
  - Sends each row (as JSON) to the LLM with the following prompt (the workflow expects the LLM to return only raw JSON):

Prompt (condensed):
"Clean this student enrollment row and return ONLY a JSON object.\nRow data: {{ JSON.stringify($json) }}\nRules:\n- Name: Title Case\n- Email: if invalid (no @ or no .com/.in) set INVALID_EMAIL\n- Phone: if less than 10 digits or empty set MISSING\n- Course: only Python or Machine Learning or Data Science\n- Fee_Paid: yes/YES = true, no/NO = false\n- City: Title Case, empty = UNKNOWN\n- Enrolled_Date: YYYY-MM-DD format\nReturn ONLY raw JSON. No explanation. No markdown."

  - Model configured in the workflow: `gpt-5-mini` via the n8n LangChain/OpenAI integration. You must configure your OpenAI credential in n8n and attach it to the model node after importing the workflow.

- Loop / Split in batches
  - The chain splits results into batches and iterates over them for stable processing.

- Code (JavaScript) node — robust post-processing
  - Purpose: defensive parsing and normalization of the LLM response.
  - Key behaviors implemented in the node:
    - Locate the LLM response inside common fields (output, text, response, content, message, result) or fall back to the full item JSON.
    - Remove markdown fences (```json or ```) and trim whitespace.
    - JSON.parse the response; if the parsed value is a string, parse again (handles double-encoded JSON).
    - Normalize fields and perform light validation:
      - Student_ID: string trim
      - Name: collapse multiple spaces and trim
      - Email: lowercase + regex check for basic validity
      - Email_Valid: boolean from regex
      - Phone: strip non-digits
      - Course: trimmed string (expected to be one of Python/Machine Learning/Data Science)
      - Fee_Paid: boolean mapping
      - City: normalized and empty -> UNKNOWN
      - Enrolled_Date: string output from LLM expected in YYYY-MM-DD
    - If parsing fails, produce an error object containing the error message and original data (so errors can be inspected later).

  - This node is critical because LLM outputs can vary in format. The code node increases reliability and prevents malformed CSV outputs.

- Conditional routing (If / Switch nodes)
  - Evaluates `City` and `Email_Valid` to route rows to one of four Convert-to-File nodes:
    1. Chennai + Email_Valid = true -> Chennail_with_Email (yes, note the file name typo in the example file)
    2. Chennai + Email_Valid = false -> Chennai_with_invalid_email
    3. Other city + Email_Valid = true -> Other_city_with_email
    4. Other city + Email_Valid = false -> Other_City_Invalid_email

- Convert to File nodes
  - Each target group is exported to a CSV file (names listed above). The example output CSVs in this folder are produced by the workflow and can be used to verify expected formatting.

Input & output schemas
- Input (student_enrollment_raw.csv): Student_ID,Name,Email,Phone,Course,Fee_Paid,City,Enrolled_Date
- Output CSV columns (as produced by Convert to File nodes): Student_ID,Name,Email,Email_Valid,Phone,Course,Fee_Paid,City,Enrolled_Date

Sample data observations
- The raw CSV contains many inconsistencies: mixed-case fields, missing emails or phones, abbreviated course names (ML, ml, etc.), inconsistent city names (chennai, CHENNAI, Trichy/Trichy variant), and dates in DD-MM-YYYY.
- Example normalizations applied by the workflow:
  - Telephone numbers: non-digit characters removed; missing numbers may be left empty.
  - Emails: lowercased; basic regex used to mark Email_Valid true/false; invalid emails set to a placeholder in LLM prompt or left as-is but flagged by Email_Valid.
  - Courses: normalized to canonical names (Python, Machine Learning, Data Science).
  - Fee_Paid: "yes", "YES" => true; "no", "NO" => false.
  - City: Missing values normalized to "UNKNOWN".
  - Dates: LLM instructed to produce YYYY-MM-DD; confirm post-run and add additional parsing if needed.

How to import & run
1. Start n8n (cloud, desktop, or locally via Docker).
2. In the n8n Editor, import `N8N-Assignment.json` (Workflows > Import).
3. Configure credentials:
   - Create or add an OpenAI (or LangChain/OpenAI) credential in n8n. The imported workflow references a saved credential id — reassign the credential in the OpenAI Chat Model node.
   - Do NOT commit API keys to the repository.
4. Option A — Manual test:
   - Open the workflow editor and run the workflow in the UI with a manual trigger or by uploading `student_enrollment_raw.csv` through the form trigger.
   - Inspect node outputs (Basic LLM Chain, Code node) to confirm the LLM returns valid JSON and the code node normalizes it.
5. Option B — Automated test:
   - Use the n8n execution API to POST the CSV or simulate the form trigger programmatically.

Credential & configuration notes
- The workflow uses an LLM — supply an API key with sufficient quota for test runs.
- Model in the exported workflow is set to `gpt-5-mini`. If unavailable, switch to a supported model (e.g., OpenAI's gpt-4o or gpt-4 if your account supports it) in the OpenAI Chat Model node.

Error handling & troubleshooting
- Common failures:
  - LLM returns non-JSON: Inspect the Basic LLM Chain node output, then inspect the Code node logs for parse errors. The code node returns an object with error details for problematic rows.
  - Credential issues: Ensure OpenAI credential is configured and attached to the model node.
  - Date normalization: If the LLM returns inconsistent date formats, add a small date-parsing step (JavaScript node or moment.js) to coerce to ISO.
- To debug:
  - Use the n8n UI to review the input/output of each node.
  - Run the Basic LLM Chain node for one sample row first to verify prompt effectiveness.
  - Add extra logging in the JavaScript code node to capture edge cases.

Suggested improvements / production hardening
- Replace the simple email regex with a dedicated email verification service for higher accuracy.
- Add rate-limiting, batching and retry logic for the LLM calls when processing large files.
- Persist cleaned records to a database (Postgres, BigQuery) for downstream analytics.
- Add metrics (counts of valid/invalid emails, rows processed, LLM parse errors) and alerting.
- Use a look-up or canonicalization table for city and course names to avoid LLM ambiguity.

Notes about files in this folder
- Example output CSV filenames intentionally follow the routing implemented in the workflow; one filename `Chennail_with_Email.csv` contains a typographic error ("Chennail"). Consider renaming for clarity.
- The exported workflow references an internal credential id — reconfigure credentials in your n8n instance after importing.

License
- Provided as-is for educational/demonstration purposes. Adapt license to your organizational needs when reusing.

Contact / next steps
- If you want a node-by-node annotated screenshot walkthrough, an automated test script to push sample CSVs into n8n, or conversion to push results into a database, request one and the README will be extended.

---
Last updated: 2026-08-15
