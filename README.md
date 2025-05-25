Yeah I know nobody will use it but if you don't know what to do with the HTML notes you export from kindle and email to yourself then why not convert it to a markdown file (and maybe add it to your obsidian vault)?

If you have your Anthropic API key exported as an environment variable then you are good to go. If not there will not be cleverly generated tags and descriptions in the frontmatter.

```bash
python kindleclip2md.py path/to/input/html path/to/output/md
```

It's written by Gemini, I have nothing to do with it. (Well I simplified it a bit but still)
