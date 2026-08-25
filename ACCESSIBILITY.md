# Accessibility status

The shipped paper is designed for readable print and screen review:

- ISO A4 page geometry;
- `/Lang=en-US` in the PDF catalog;
- plain running pages with the author present only in the front matter;
- embedded fonts, live HTTPS bibliography links and descriptive captions;
- no JavaScript, form, attachment, launch action, local-file URI or encryption.

The current PDF is **not claimed to conform to PDF/UA** and does not claim a
complete tagged structure tree. That limitation is explicit rather than
silently represented as conformance. The complete structured LaTeX source is
available at `paper/main.tex`, with theorem environments, section headings,
equation labels, table structure and figure captions preserved for alternative
rendering or assistive conversion.

The release checker verifies the language tag, A4 geometry, visible keywords
and MSC, canonical repository link, author placement and absence of active
content. A conforming tagged-PDF or full semantic HTML edition remains a
separate deliverable and must receive its own visual and assistive-technology
review before it can replace this disclosure.
