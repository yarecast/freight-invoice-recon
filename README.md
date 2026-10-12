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

TODO

## What I would do with more time

TODO

## Left out

TODO

## Limitations

TODO

## Security notes

TODO

## Where I used AI assistants and where I overrode them

TODO (author): write this from docs/ai_usage_notes.md.