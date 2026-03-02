#!/usr/bin/env python3
"""
Translate all db9 stories to English using free translation API
"""
import httpx
import json
import os
import sys
import time

API_URL = os.getenv("API_URL", "https://db9-stories.onrender.com")

def translate_text(text: str) -> str:
    """Translate Chinese text to English using MyMemory API (free)"""
    if not text or not any('\u4e00' <= c <= '\u9fff' for c in text):
        return text
    
    try:
        resp = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": "zh|en"},  # 500 char limit
            timeout=30.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("responseStatus") == 200:
                return data["responseData"]["translatedText"]
    except Exception as e:
        print(f"  ⚠️ Translation error: {e}")
    
    return text

def translate_long_text(text: str) -> str:
    """Translate longer text by chunking"""
    if not text or not any('\u4e00' <= c <= '\u9fff' for c in text):
        return text
    
    # Split by sentences (Chinese period)
    sentences = text.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
    sentences = [s.strip() for s in sentences if s.strip()]
    
    translated = []
    for s in sentences:
        t = translate_text(s)
        translated.append(t)
        time.sleep(0.5)  # Rate limit
    
    return ' '.join(translated)

def translate_code_comments(code: str) -> str:
    """Translate comments in code (best effort)"""
    if not code or not any('\u4e00' <= c <= '\u9fff' for c in code):
        return code
    
    lines = code.split('\n')
    result = []
    
    for line in lines:
        # Check if line has Chinese in comment
        if '--' in line:
            parts = line.split('--', 1)
            if len(parts) == 2 and any('\u4e00' <= c <= '\u9fff' for c in parts[1]):
                translated_comment = translate_text(parts[1].strip())
                line = f"{parts[0]}-- {translated_comment}"
                time.sleep(0.3)
        result.append(line)
    
    return '\n'.join(result)

def translate_tags(tags) -> list:
    """Translate tags"""
    if not tags:
        return []
    
    if isinstance(tags, str):
        if tags.startswith('{') and tags.endswith('}'):
            tags = [t.strip() for t in tags[1:-1].split(',') if t.strip()]
        else:
            tags = [tags]
    
    result = []
    for tag in tags:
        if any('\u4e00' <= c <= '\u9fff' for c in tag):
            t = translate_text(tag)
            result.append(t.lower().replace(' ', '-'))
            time.sleep(0.3)
        else:
            result.append(tag)
    
    return result

def main():
    print(f"📚 Fetching stories from {API_URL}...")
    resp = httpx.get(f"{API_URL}/stories?limit=100", timeout=30.0)
    stories = resp.json()["stories"]
    print(f"   Found {len(stories)} stories\n")
    
    translated = []
    
    for i, story in enumerate(stories, 1):
        print(f"[{i}/{len(stories)}] 🔄 {story['title']}")
        
        title_en = translate_text(story["title"])
        print(f"        → {title_en}")
        
        new_story = {
            "title": title_en,
            "content": translate_long_text(story["content"]),
            "author": story.get("author", "anonymous"),
            "code_snippet": translate_code_comments(story.get("code_snippet")),
            "tags": translate_tags(story.get("tags")),
        }
        
        translated.append({"original": story, "translated": new_story})
        time.sleep(1)  # Rate limit between stories
    
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
