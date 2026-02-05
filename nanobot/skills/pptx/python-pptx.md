# python-pptx Tutorial

## Required Output Format (Do Not Skip)

When creating a new deck, the deliverable is a runnable **Python script** that directly uses `python-pptx`.

**Do not output JSON or pseudo-code.** The `.py` file must include:
- `from pptx import Presentation`
- `from pptx.util import Inches, Pt`
- `from pptx.dml.color import RGBColor`
- `prs = Presentation()`
- At least one `prs.slides.add_slide(...)`
- `prs.save("output.pptx")`

If it cannot run with `python3 your_file.py`, it is not acceptable.

### Hard Rejection Rules

If the output starts with `[` or `{`, **it is JSON or a data dump, not Python code**. Discard it and regenerate.

The file must include **all** of the following strings:
- `from pptx import Presentation`
- `prs = Presentation()`
- `prs.save(`

## Minimal Working Template

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()

# Use a title slide layout
title_slide = prs.slides.add_slide(prs.slide_layouts[0])

title = title_slide.shapes.title
subtitle = title_slide.placeholders[1]

title.text = "Presentation Title"
subtitle.text = "Subtitle | Date"

# Add a content slide with bullets
content_slide = prs.slides.add_slide(prs.slide_layouts[1])
content_slide.shapes.title.text = "Key Points"
body = content_slide.placeholders[1].text_frame
body.text = "First point"

p = body.add_paragraph()
p.text = "Second point"

p = body.add_paragraph()
p.text = "Third point"

# Add a custom text box
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
textbox = slide.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(8.4), Inches(1.0))
text_frame = textbox.text_frame
run = text_frame.paragraphs[0].add_run()
run.text = "Custom text box"
run.font.size = Pt(32)
run.font.bold = True
run.font.color.rgb = RGBColor(30, 39, 97)
text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

prs.save("output.pptx")
print("Saved: output.pptx")
```

## Smoke Test (Required)

```bash
python3 -m venv venv_pptx
./venv_pptx/bin/pip install python-pptx
./venv_pptx/bin/python -m py_compile output.py
./venv_pptx/bin/python output.py
ls -l output.pptx
```

If the script fails, fix the Python code. **Do not switch to PptxGenJS** unless the user asks.

---

## Tips

- Use `prs.slide_layouts[1]` (Title and Content) to get bullet formatting from the placeholder.
- For full control, use `prs.slide_layouts[6]` (blank) and add shapes/text boxes manually.
- Set background color:
  ```python
  slide.background.fill.solid()
  slide.background.fill.fore_color.rgb = RGBColor(26, 60, 64)
  ```
- Avoid non-ASCII in file paths on some systems; keep output path simple if possible.
