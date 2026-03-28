---
name: skill-new-post-creator
description: >
  Creates a new Hugo blog post file under content/post/ with the correct front matter template.
  Use this skill whenever the user wants to create, add, or start a new blog post, article, or note —
  especially when they mention a category (tech, life, investment, books-reviews), a slug or title,
  or say things like "新增一篇文章", "幫我建立一篇", "create a new post", "add a post to tech",
  "start a new book review", "new investment post". Even if the user doesn't say "skill", trigger
  whenever they want a blank post scaffold created in the blog.
---

# Skill: New Post Creator

This skill creates a properly structured Hugo blog post file inside `content/post/` of the blog at `/Users/yujiezheng/yujie70338.github.io`.

## What you need from the user

Extract these two pieces of information from the user's prompt:

1. **Category** — one of `tech`, `life`, `investment`, `books-reviews`, or a new custom category.
2. **Slug** — a short, lowercase, hyphen-separated English string to use as the filename identifier (e.g. `my-new-post`). The user should provide this. If they didn't, ask them for it before proceeding.

If either is missing, ask before creating the file.

## Date

Always use today's date in `yyyy-mm-dd` format for both the filename prefix and the `date:` front matter field. Never ask the user for a date.

## Category → Directory mapping

| Category      | Directory                                                          |
|---------------|--------------------------------------------------------------------|
| `tech`        | `/Users/yujiezheng/yujie70338.github.io/content/post/tech/`        |
| `life`        | `/Users/yujiezheng/yujie70338.github.io/content/post/life/`        |
| `investment`  | `/Users/yujiezheng/yujie70338.github.io/content/post/investment/`  |
| `books-reviews` | `/Users/yujiezheng/yujie70338.github.io/content/post/books-reviews/` |

For any **new category not in the table above**, confirm with the user before creating a new subdirectory.

## Filename format

```
yyyy-mm-dd-<slug>.md
```

Example: if today is 2026-03-28 and the slug is `my-k8s-notes`, the filename is `2026-03-28-my-k8s-notes.md`.

## File content

Create the file with exactly this content (substitute `yyyy-mm-dd` and `<category>` with the real values, leave all other fields as empty strings):

```markdown
---
title: ""
subtitle: ""
description: ""
date: yyyy-mm-dd
author: "Yujie Zheng"
image: ""
tags: ["" ]
categories: [ "<category>" ]
---



---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
```

There should be **two blank lines** between the closing `---` of the front matter and the `---` horizontal rule at the bottom. This leaves space for the user to write their post body.

## After creating the file

Tell the user:
- The full path of the file created
- What category and slug were used
- That they can now open it and start writing
