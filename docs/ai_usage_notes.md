# AI usage notes

Raw notes of moments where I corrected, rejected or changed a suggestion from the AI assistant.
Each entry is written from what really happened. I use these notes for the README section about AI usage.

## 1. Duplicate invoices 07 and 08

The report for invoices 07 and 08 was confusing. I pointed out that they are the same invoice (one digital, one scanned copy).
Because of my comment, the two duplicate codes were merged into one (DUPLICATE_INVOICE_NUMBER) and the reason text was changed.

## 2. Ambiguous date in invoice 15

I questioned the date of invoice 15. The PDF says "03/04/2026" and it is not clear which format it uses.
We did not edit the extraction file. The date was documented as ambiguous.

## 3. README for non-technical readers

The first README draft told the reviewer to open a terminal and paste commands. That is not what I wanted: I chose Colab so a non-technical person can see the result. I said this, and the README was changed. The report and the Colab notebook come first, and the commands are in sections that start closed.

## 4. "The tool does not approve anything"

The first README text said the tool does not approve anything. I pointed out that the tool does the matching, and the task asks for it. The text now says that the tool matches and flags, but does not approve or pay.

## 5. Status label for invoices with no findings

I thought "SIN HALLAZGOS" was not clear for an operations person and I asked to change it. The assistant warned that a green check alone could look like an approval. We changed it to the text "NADA QUE REVISAR" with a small check icon.
