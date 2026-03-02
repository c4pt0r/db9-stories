#!/usr/bin/env python3
"""
Translate all db9 stories to English using OpenAI API
"""
import httpx
import json
import os
import sys

API_URL = os.getenv("API_URL", "https://db9-stories.onrender.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def call_gpt(prompt: str, max_tokens: int = 1000) -> str:
    """Call OpenAI API"""
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens
        },
        timeout=60.0
    )
    
    if resp.status_code != 200:
        print(f"  ⚠️ API error: {resp.text[:100]}")
        return None
    
    return resp.json()["choices"][0]["message"]["content"].strip()

def translate_text(text: str, field_type: str = "content") -> str:
    """Translate Chinese text to English"""
    if not text or not any('\u4e00' <= c <= '\u9fff' for c in text):
        return text
    
    prompt = f"""Translate this {field_type} from Chinese to English. 
Keep technical terms (SQL, db9, HNSW, GIN, JSONB, pg_cron) as-is.
Be natural and concise. Output ONLY the translation.

{text}"""

    result = call_gpt(prompt)
    return result if result else text

def translate_code_comments(code: str) -> str:
    """Translate only comments in code"""
    if not code or not any('\u4e00' <= c <= '\u9fff' for c in code):
        return code
    
    prompt = f"""Translate ONLY the Chinese comments to English in this SQL code.
Keep ALL code exactly as-is. Only translate text after -- or inside /* */.
Output the complete code with translated comments, nothing else.

{code}"""

    result = call_gpt(prompt, 1500)
    return result if result else code

def translate_tags(tags) -> list:
    """Translate tags"""
    if not tags:
        return []
    
    if isinstance(tags, str):
        if tags.startswith('{') and tags.endswith('}'):
            tags = [t.strip() for t in tags[1:-1].split(',') if t.strip()]
        else:
            tags = [tags]
    
    has_chinese = any(any('\u4e00' <= c <= '\u9fff' for c in t) for t in tags)
    if not has_chinese:
        return tags
    
    prompt = f"""Translate these tags to English. Keep technical terms as-is.
Output ONLY comma-separated tags.

{', '.join(tags)}"""

    result = call_gpt(prompt, 200)
    if result:
        return [t.strip().lower().replace(' ', '-') for t in result.split(',')]
    return tags

def main():
    if not OPENAI_API_KEY:
        print("❌ Set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    print(f"📚 Fetching stories from {API_URL}...")
    resp = httpx.get(f"{API_URL}/stories?limit=100", timeout=30.0)
    stories = resp.json()["stories"]
    
    # Filter only Chinese stories (exclude [EN] ones)
    stories = [s for s in stories if not s['title'].startswith('[EN]')]
    print(f"   Found {len(stories)} Chinese stories\n")
    
    translated = []
    
    for i, story in enumerate(stories, 1):
        print(f"[{i}/{len(stories)}] 🔄 {story['title']}")
        
        title_en = translate_text(story["title"], "title")
        print(f"        → {title_en}")
        
        new_story = {
            "title": title_en,
            "content": translate_text(story["content"], "content"),
            "author": story.get("author", "anonymous"),
            "code_snippet": translate_code_comments(story.get("code_snippet")),
            "tags": translate_tags(story.get("tags")),
        }
        
        translated.append({"original": story, "translated": new_story})
    
    output_file = "translated_stories.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved {len(translated)} translations to {output_file}")
    print("\nTo upload, run: python translate.py --upload")

def upload_translations():
    """Upload translated stories"""
    with open("translated_stories.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"📤 Uploading {len(data)} stories...")
    
    for item in data:
        story = item["translated"]
        story["title"] = f"[EN] {story['title']}"
        story["author"] = f"{item['original'].get('author', 'anonymous')} (translated)"
        
        resp = httpx.post(f"{API_URL}/stories", json=story, timeout=30.0)
        status = "✅" if resp.status_code in (200, 201) else "❌"
        print(f"   {status} {story['title']}")
    
    print("\n✅ Done!")

if __name__ == "__main__":
    if "--upload" in sys.argv:
        upload_translations()
    else:
        main()
