import argparse
import re
from bs4 import BeautifulSoup
import json


def generate_frontmatter_content_with_llm(book_title, sample_highlights_text):
    """
    Generates tags and description for the Markdown frontmatter using an LLM.
    """
    print("[INFO] Attempting to generate frontmatter content via LLM...")
    print(f"[INFO] Book Title for LLM: {book_title}")

    try:
        from anthropic import Anthropic
        client = Anthropic()
        prompt = (
            f"Given the book title '{book_title}'"
            "and the following sample highlights:\n\n"
            # This will now contain all highlights (potentially truncated)
            f"{sample_highlights_text}\n\n"
            "Please generate appropriate metadata for a Markdown note. I need:\n"
            "1. A list of 5-7 relevant tags (e.g., history, revolution).\n"
            "2. A concise description (2-3 sentences) of the book's content based on the title and highlights.\n"
            "Return the output as a JSON object with keys 'tags' (a list of strings) and 'description' (a string).\n"
            " Remember: return NOTHING but the JSON object."
        )
        response = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        try:
            llm_output = json.loads(content)
            print("[INFO] Successfully received and parsed LLM response.")
            return {
                "tags": llm_output.get("tags", ["llm_generated_tag"]),
                "description": llm_output.get(
                    "description", "LLM generated description."
                ),
            }
        except json.JSONDecodeError:
            print(f"[ERROR] LLM response was not valid JSON: {content}")
            return {
                "tags": ["error_parsing_llm_tags"],
                "description": f"Error parsing description. Raw: {content}",
            }
    except Exception as e:
        print(
            f"[ERROR] An unexpected error occurred during the API call: {e}"
        )

    # Fallback if API call is skipped or fails
    print(
        "[INFO] Using fallback frontmatter content"
        " because no LLM API was successfully used."
    )
    return {
        "tags": ["untagged", "needs_review"],
        "description": "Description to be generated or manually entered.",
    }


def parse_html_notebook(html_content):
    """
    Parses the HTML content of a Kindle notebook export.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    book_title_tag = soup.find("div", class_="bookTitle")
    book_title = book_title_tag.text.strip() if book_title_tag else "Unknown Title"

    authors_tag = soup.find("div", class_="authors")
    author = authors_tag.text.strip() if authors_tag else "Unknown Author"

    notes = []

    # Regex to parse note heading
    # Example: Highlight(<span class="highlight_yellow">yellow</span>) - 一场民变 > Page 4 · Location 34
    # Example: Note - Chapter Name > Page 10
    note_heading_regex = re.compile(
        r"(Highlight|Note)\s*"  # Type: Highlight or Note
        # Optional color
        r"(?:\(<span class=\"highlight_(?P<color>\w+)\">\w+</span>\))?\s*"
        r"-\s*(?P<chapter>[^>]+?)\s*>"  # Chapter name
        r"(?:\s*Page\s*(?P<page>\d+))?"  # Optional Page number
        r"(?:\s*·\s*Location\s*(?P<location>\d+))?"  # Optional Location
    )

    for element in soup.find_all(["div", "hr"]):
        if element.name == "hr":  # Separator often before a new set of notes or section
            continue

        element_classes = element.get("class", [])
        if "sectionHeading" in element_classes:
            notes.append({"type": "section_header",
                         "text": element.text.strip()})
        elif "noteHeading" in element_classes:
            heading_text_content = (
                element.decode_contents().strip()
            )  # Use decode_contents to keep span for regex
            note_text_tag = element.find_next_sibling("div", class_="noteText")
            text_content = note_text_tag.text.strip() if note_text_tag else ""

            match = note_heading_regex.search(heading_text_content)
            if match:
                data = match.groupdict()
                note_info = {
                    "type": "highlight",  # Assume 'Note' type also refers to a highlight or annotation
                    "color": data.get("color") if data.get("color") else "no_color",
                    "chapter": data.get("chapter", "Unknown Chapter").strip(),
                    "page": data.get("page"),
                    "location": data.get("location"),
                    "text": text_content,
                    "original_heading": element.text.strip(),  # For fallback/debugging
                }
                notes.append(note_info)
            else:
                # Fallback for headings that don't match the detailed regex
                notes.append(
                    {
                        "type": "unknown_heading_format",
                        "original_heading": element.text.strip(),  # Get the plain text of the heading
                        "text": text_content,
                    }
                )

    return {"book_title": book_title, "author": author, "notes": notes}


def format_to_markdown(parsed_data, llm_frontmatter):
    """
    Formats the parsed data into a Markdown string.
    """
    markdown_lines = []

    # --- Frontmatter ---
    markdown_lines.append("---")
    markdown_lines.append(f'bookTitle: "{parsed_data["book_title"]}"')
    markdown_lines.append(f'author: "{parsed_data["author"]}"')

    markdown_lines.append("tags:")
    for tag_item in llm_frontmatter.get(
        "tags", ["default_tag"]
    ):  # Ensure there's always a list
        markdown_lines.append(f"  - {tag_item}")

    description_text = llm_frontmatter.get(
        "description", "No description generated.")
    # Ensure multi-line descriptions are correctly formatted for YAML
    if "\n" in description_text:
        markdown_lines.append("description: |")
        for line_content in description_text.split("\n"):
            markdown_lines.append(f"  {line_content}")
    else:
        markdown_lines.append(f'description: "{description_text}"')
    markdown_lines.append("---")
    markdown_lines.append("")  # Newline after frontmatter

    # Use book title as header
    markdown_lines.append(f'# "{parsed_data["book_title"]}"')

    # --- Notes ---
    for note_item in parsed_data["notes"]:
        if note_item["type"] == "section_header":
            markdown_lines.append(f"## {note_item['text']}")
            markdown_lines.append("")
        elif note_item["type"] == "highlight":
            heading_parts_list = []
            if note_item["chapter"] and note_item["chapter"] != "Unknown Chapter":
                heading_parts_list.append(note_item["chapter"])
            if note_item["page"]:
                heading_parts_list.append(f"Page {note_item['page']}")
            if note_item["location"]:
                heading_parts_list.append(f"Location {note_item['location']}")

            title_output_line = "### "
            if note_item["color"] and note_item["color"] != "no_color":
                title_output_line += f"Highlight ({note_item['color']})"
            else:
                title_output_line += "Note"

            if heading_parts_list:
                title_output_line += f" - {' · '.join(heading_parts_list)}"
            else:  # Fallback if no chapter/page/location parsed
                default_text = note_item.get(
                    "original_heading", "Details missing")
                title_output_line += f" - {default_text}"

            markdown_lines.append(title_output_line)

            if note_item["text"]:
                markdown_lines.append(f"> {note_item['text']}")
            markdown_lines.append("")
        elif note_item["type"] == "unknown_heading_format":
            original_heading_text = note_item.get(
                'original_heading', 'Unknown Details'
            )
            heading_line = f"### Note - {original_heading_text}"
            markdown_lines.append(heading_line)
            if note_item['text']:
                markdown_lines.append(f"> {note_item['text']}")
            markdown_lines.append("")
    return "\n".join(markdown_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Kindle HTML notebook export to Markdown."
    )
    parser.add_argument("input_html_file", help="Path to the input HTML file.")
    parser.add_argument(
        "output_markdown_file", help="Path to the output Markdown file."
    )

    args = parser.parse_args()

    try:
        with open(args.input_html_file, "r", encoding="utf-8") as f:
            html_content = f.read()  # Raw HTML content
    except FileNotFoundError:
        print(f"Error: Input HTML file not found at {args.input_html_file}")
        return
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        return

    parsed_data = parse_html_notebook(html_content)

    # Use all extracted highlight texts as sample_text_for_llm
    all_highlight_texts = [note["text"] for note in parsed_data["notes"]]
    sample_text_for_llm = "\n\n".join(all_highlight_texts)

    MAX_SAMPLE_TEXT_LENGTH = 1000  # Adjust this character limit as needed
    if len(sample_text_for_llm) > MAX_SAMPLE_TEXT_LENGTH:
        sample_text_for_llm = (
            sample_text_for_llm[:MAX_SAMPLE_TEXT_LENGTH] + "\n... (truncated)"
        )
        print(
            "[INFO] Sample text for LLM was truncated"
            f"to {MAX_SAMPLE_TEXT_LENGTH} characters."
        )
    elif not sample_text_for_llm:
        print(
            "[INFO] No highlight text found to use as sample for LLM. LLM might have less context."
        )

    llm_frontmatter_content = generate_frontmatter_content_with_llm(
        parsed_data["book_title"], sample_text_for_llm
    )

    markdown_output_content = format_to_markdown(
        parsed_data, llm_frontmatter_content)

    try:
        with open(args.output_markdown_file, "w", encoding="utf-8") as f:
            f.write(markdown_output_content)
        print(
            f"Successfully converted '{args.input_html_file}'"
            f"to '{args.output_markdown_file}'"
        )
    except Exception as e:
        print(f"Error writing Markdown file: {e}")


if __name__ == "__main__":
    main()
