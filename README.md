# Freight Invoice Reconciliation

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/yarecast/freight-invoice-recon/blob/entrega-v1/notebooks/demo_colab.ipynb)

Take-home project for the AI Automation Engineer role at Transmaquila (via Scale Army).
The tool reads carrier invoices, matches each one to a load in the register, and lists what a person must review, with the reason.

## Open first

You do not need to install anything or write commands.

1. **Colab notebook (easiest):** click the badge above, then `Runtime > Run all`. It takes 1-2 minutes, shows the report inside the notebook and needs no API key.
2. **The report file:** download [output/reporte.html](output/reporte.html) and open it in your browser (GitHub only shows the source code of HTML files). It has no JavaScript and does not need internet.
3. **Quick look on GitHub:** [output/reporte.csv](output/reporte.csv) shows as a table directly on this page.

Read the section "Excepciones por severidad" first: it is the list of what needs human attention. The other sections give context.

## What it does

Input: 18 carrier invoices as PDF files (clean digital files, scans and phone photos; 3 vendor layouts; MXN and USD; English and Spanish) and a register of 16 agreed loads (`data/registro_de_cargas.csv`).

Output: `output/reporte.html` and `output/reporte.csv`, with:
- a summary by severity,
- the exceptions, sorted by severity, each with a plain-language reason and a suggested action,
- every invoice with its status (nothing is dropped silently),
- the register loads that have no invoice,
- run details (mode, model, extraction dates).

The agreed rate in the register is the source of truth.
The model only reads the invoices. Every decision (matching and rules) is plain deterministic code.
The tool matches each invoice to a load and flags what needs attention. It does not approve or pay anything: "NADA QUE REVISAR" means the tool found no exceptions, not that the invoice is approved.

## How to run

**Level 1: open the report.** See "Open first" above. No installation.

**Level 2 and Level 3 are for people who want to run the code.** Open the sections below.

<details>
<summary>Level 2: demo run (no internet, no API key)</summary>

You need Python 3.11 or 3.12.

Windows (PowerShell):

```powershell
git clone https://github.com/yarecast/freight-invoice-recon.git
cd freight-invoice-recon
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

macOS / Linux:

```bash
git clone https://github.com/yarecast/freight-invoice-recon.git
cd freight-invoice-recon
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Demo mode reads only the saved extractions in `extractions/` (JSON files that come from real Gemini runs). It rewrites `output/reporte.html` and `output/reporte.csv`.
If a PDF changed after its extraction was saved, the report shows a warning.

</details>

<details>
<summary>Level 3: live run (Gemini API)</summary>

1. Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY` and `GEMINI_MODEL`. There is no default model name. Never commit `.env`.
2. Run:

```powershell
python run.py --live
python run.py --live --only-missing
```

The second command skips PDFs that already have a JSON in `extractions/`.

Live mode writes the JSON files again. The free tier of Google AI Studio allows about 20 requests per day per model, failed calls count, and a quota error (429) stops the run. For this reason demo mode is the default.

</details>

<details>
<summary>Tests</summary>

```powershell
python -m pytest
python scripts/compare_golden.py
```

The second command compares the system with a hand-written answer sheet (`tests/golden/expected.csv`) and lists every difference.

</details>

## Architecture and why

Pipeline: PDF files -> ingest -> extraction with Gemini -> JSON cache -> verification -> matching -> rules -> report.

**The model reads, the code decides.** Gemini only turns each PDF into fields: carrier, invoice number, load reference, date, amount, currency and handwritten notes. Each field comes with a short text copied from the document as evidence. The model does not compute or correct anything. Matching and every rule are normal Python code, so each decision is the same every time and a person can check it.

**Why a cache of JSON files.** Every extraction is saved in `extractions/` with the PDF hash, the model name, the prompt version and the date. Demo mode reads only these files, so anyone can run the project without internet or an API key, and the result is the same on every run. It also protects the free-tier quota. If a PDF changes after its extraction was saved, the report shows a warning. The JSON files are real model output and were never edited by hand.

**Why not OCR only.** The invoices have three layouts, two languages, scans, phone photos and handwriting. OCR gives only raw text, and then I would need fixed rules for each layout. A vision model reads the document and returns the fields directly. I did not run an OCR comparison, so this is a design choice and not a measured result. The risk is that the model can be wrong, so the code does not trust it blindly: for PDFs with a text layer, the invoice number, the load reference and the amount must also appear in the PDF text. If not, the invoice gets an extraction warning (EXTRACTION_MISMATCH). Scans and photos have no text layer, so they are marked as a single read.

**Other design choices.**
- Money is always `Decimal`, never float, and the agreed rate in the register is the source of truth.
- The currency is never guessed.
- Matching is exact on the load reference. There is no automatic fuzzy matching.
- A file that cannot be read becomes an exception in the report (FILE_UNREADABLE), not a crash.

## Judgment calls on ambiguity

- **Currency not printed.** Some Del Norte invoices do not print the currency. The tool never guesses it. It compares the amount using the currency of the register, says so in the reason, and marks it LOW.
- **Handwritten amounts.** Invoice RG-7812 prints a total of 850 USD. Handwritten notes add "+ 150 detention" and "TOTAL 1,000". The agreed rate is 850 USD. The printed amount matches, but the handwritten total does not, so the tool flags ANNOTATED_AMOUNT (HIGH) and shows the three numbers: printed, handwritten and agreed. It does not decide which one is right. A person does.
- **Identical loads.** TRQ-4476 and TRQ-4488 have the same route, commodity and rate. Matching by route or amount would be ambiguous, so the tool matches only by the load reference written on the invoice.
- **No fuzzy auto-match.** If the load reference is missing or unknown, the result is NO_LOAD_MATCH. The report may list candidate loads (same carrier, close dates) as suggestions only. I prefer a false no-match that a person reviews over a wrong match that nobody notices.
- **Ambiguous date.** Invoice RG-7801 prints "03/04/2026". The model read 4 March 2026. I read 3 April 2026 in my hand-written answer sheet. Nothing in the PDF tells which format it uses. In both cases the date is before the shipment date (2026-09-21), so the result is the same: INVOICE_BEFORE_SHIPMENT (MEDIUM). The reason text explains the ambiguity. I did not edit the extraction.
- **Duplicates.** The same invoice number received twice (invoices 07 and 08, one digital and one scanned copy) is reported once as DUPLICATE_INVOICE_NUMBER. The tool cannot know if the content is identical, so the reason says it seems to be the same invoice received twice. Two different invoice numbers for the same load (invoices 09 and 10) are reported as DUPLICATE_LOAD_INVOICE. In my answer sheet I expected both duplicate codes for 07 and 08; the tool shows only one on purpose. I kept this difference visible (see Results).
- **Carrier names.** Names are compared without accents, punctuation and company suffixes, and known aliases live in `config.toml` (for example "Pena Hnos." and "Pena Hermanos").

## Results

Demo mode, 18 invoices, saved extractions:

| Status | Invoices |
|---|---|
| ALTA (high) | 9 |
| MEDIA (medium) | 1 |
| BAJA (low) | 1 |
| NADA QUE REVISAR | 7 |

Exceptions by code:

| Code | Invoices |
|---|---|
| AMOUNT_MISMATCH | 2 (11, 12) |
| DUPLICATE_INVOICE_NUMBER | 2 (07, 08) |
| DUPLICATE_LOAD_INVOICE | 2 (09, 10) |
| NO_LOAD_MATCH | 2 (13, 16) |
| ANNOTATED_AMOUNT | 1 (17) |
| INVOICE_BEFORE_SHIPMENT | 1 (15) |
| CURRENCY_NOT_PRINTED | 1 (14) |

Register loads with no invoice (information only, not an exception): TRQ-4485 and TRQ-4486.

**Comparison with my hand-written answer sheet.** I filled `tests/golden/expected.csv` by hand from the PDFs and the register, one row per invoice. `python scripts/compare_golden.py` compares it with the system:

| Field | Matches |
|---|---|
| carrier, invoice number, load reference | 18/18 each |
| amount, currency | 18/18 each |
| handwriting (yes/no) and handwritten amount | 18/18 each |
| status | 18/18 |
| invoice date | 17/18 |
| exception codes | 16/18 |

There are 3 differences and I left them visible:
- Invoices 07 and 08: I expected both duplicate codes, the tool shows only DUPLICATE_INVOICE_NUMBER. This is the merge described above.
- Invoice 15: the date "03/04/2026" is ambiguous (see above). The result is the same with both readings.

**What the real data does not test.** EXTRACTION_MISMATCH and SINGLE_READ_LOW_LEGIBILITY do not appear in these 18 invoices (no extraction has legibility notes). They are tested only with fixtures in `tests/`.

## What I would do with more time

- Read photos and scans twice (for example with a second model or a second pass) and compare, because today they have a single read.
- Ask the model to return an empty date when the date format cannot be known, instead of choosing one.
- Run a measured comparison against an OCR-based approach, and test with many more invoices.
- Move to a paid API tier and process invoices in batches or in parallel.
- Suggest candidate loads with a human confirmation step, instead of only listing them.
- Let the operations team mark each exception as reviewed, and keep that history.
- Add a retention policy for invoice files and extractions.

## Left out

On purpose, to keep the scope narrow and finish in 3-4 hours:

- Currency conversion (FX). Amounts are compared in the currency of the register.
- Tax and CFDI validation.
- Fuzzy matching in production. Only exact matching on the load reference.
- Email intake of invoices.
- A user interface. The report is a static file.
- Multi-page invoices. Files are limited by page count in `config.toml`.
- Auto-approval or payment. The tool only reports.

## Limitations

- **Photos and scans have a single read.** There is no text layer to double-check the model, so they are marked as single read.
- **Handwriting.** The model can misread handwritten notes. I have only one invoice with handwritten amounts (RG-7812).
- **Model variance.** The model can change between runs, even with temperature 0. The JSON cache is why the demo gives the same result every time.
- **Dates.** The model decides how to read a date such as "03/04/2026". The tool cannot tell if it is right.
- **Amount format.** Amounts are parsed only in the format 1,000.00. Other formats (for example 1.000,00) are not parsed.
- **Small sample.** The 18 invoices are not an estimate of accuracy in general, and the answer sheet was written by one person.
- **Free tier.** Google AI Studio gives about 20 requests per day per model, and failed calls count. A quota error stops the run. Data sent on the free tier may be used by Google to improve its products (check the current terms). For real invoices I would use a paid tier.
- **Data retention.** Invoices contain business data. In production the extractions need a retention policy.

## Security notes

- PDFs are treated as untrusted input. The code does not use `eval`, `pickle` or shell commands on their content.
- All extracted text is HTML-escaped in the report, which has no JavaScript and makes no external requests. A test checks this.
- CSV cells that start with `=`, `+`, `-` or `@` get a leading apostrophe, so Excel does not run them as formulas. A test checks this.
- The API key comes only from the `GEMINI_API_KEY` environment variable (loaded from `.env`, which Git ignores). It is never printed, logged or committed.
- Dependencies are pinned in `requirements.txt`.
- The model only extracts fields. Matching and decisions are code, so text inside a PDF cannot approve anything. I did not test prompt-injection attacks inside invoices, so the extracted fields of a hostile PDF could still be wrong.

## Where I used AI assistants and where I overrode them

**Where I used AI.** I built this project with Claude (Anthropic) as a pair-programming mentor, in a chat. We worked in small steps. For each step it explained what we were doing and why, and gave me the command or the file. I ran it myself and pasted the real output, and we did not continue until the output was what we expected. I used it for the code, the tests, the README and the Spanish summary. Gemini is a different part: it only reads the invoices inside the tool.

**How I checked the work.**
- I ran every command and read the real output before going on.
- I checked each saved extraction against its PDF.
- I wrote the answer sheet (`tests/golden/expected.csv`) by hand from the PDFs and the register, not from the output of the system, and compared it with the system.
- Tests and CI run on every push.

**Where I corrected or changed the assistant.**
1. **Invoices 07 and 08.** The report was confusing, because they are the same invoice (one digital, one scanned copy). I pointed this out. The two duplicate codes were merged into one and the reason text was changed.
2. **Invoice 15 date.** I questioned the date "03/04/2026". We did not edit the extraction. The date is documented as ambiguous.
3. **README for non-technical readers.** The first README draft told the reviewer to open a terminal and paste commands. I did not want that, and this is why I chose Colab. The README now starts with the report and the notebook, and the commands are in sections that start closed.
4. **"The tool does not approve anything".** The first wording made it sound like the tool does not do the matching. I pointed out that matching is part of the task. The text now says the tool matches and flags, but does not approve or pay.
5. **Status label.** I thought "SIN HALLAZGOS" was not clear for an operations person and I asked to change it. The assistant warned that a green check alone could look like an approval. We used the text "NADA QUE REVISAR" with a small check icon.
