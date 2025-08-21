# Hippocratic AI — Bedtime Story Generator

An interactive web app that generates bedtime stories for children (ages 5–10) using OpenAI's GPT models.  
Supports **short stories** or **multi-arc stories** with user-directed tweaks between chapters.

![Flowchart](flowchart.png)

## Features

- **Short Story Mode**: Generates a complete story in one go.
- **Multi-Arc Mode**: Generates stories chapter-by-chapter, with options to continue, end in next chapter, or end now.
- **Tweak Support**: Apply changes to the story at any time.
- **Clean Output**: Titles and story text are stripped of markdown formatting.
- **Loading Feedback**: Spinner overlay while generating content.
- **Hosted on Heroku**: [Live Demo](https://hippocratic-takehome-3de9c586b201.herokuapp.com)

## Tech Stack

- **Frontend**: HTML, CSS, JavaScript (Flask templates)
- **Backend**: Python (Flask)
- **LLM**: OpenAI `gpt-3.5-turbo`
- **Hosting**: Heroku (Gunicorn)
