from typing import Dict, Any
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import re


class PageFetcherService:
    """
    Fetches live web page HTML and extracts clean, readable text, titles, and metadata
    in a structured format for autonomous LLM research consumption.
    """

    @staticmethod
    async def fetch(url: str, max_chars: int = 4000) -> Dict[str, Any]:
        clean_url = (url or "").strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"

        domain = urllib.parse.urlparse(clean_url).netloc

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="123", "Not:A-Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(clean_url, headers=headers)
                if resp.status_code not in (200, 201, 202, 301, 302, 304):
                    return {
                        "url": clean_url,
                        "title": f"HTTP {resp.status_code}",
                        "domain": domain,
                        "status_code": resp.status_code,
                        "is_valid": False,
                        "content": f"Unable to fetch page. HTTP status code {resp.status_code}.",
                        "truncated": False,
                    }

                soup = BeautifulSoup(resp.text, "html.parser")

                # Remove non-content elements
                for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
                    element.decompose()

                title = ""
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
                elif soup.find("h1"):
                    title = soup.find("h1").get_text(strip=True)
                else:
                    title = domain

                # Extract main text
                text_content = soup.get_text(separator="\n", strip=True)
                # Clean multiple empty lines
                cleaned_text = re.sub(r"\n{3,}", "\n\n", text_content)

                limit = max(500, min(max_chars, 8000))
                is_truncated = len(cleaned_text) > limit
                truncated_content = cleaned_text[:limit] if is_truncated else cleaned_text

                return {
                    "url": clean_url,
                    "title": title,
                    "domain": domain,
                    "content": truncated_content,
                    "truncated": is_truncated,
                }
        except Exception as e:
            return {
                "url": clean_url,
                "title": "Fetch Error",
                "domain": domain,
                "content": f"Failed to retrieve page content: {str(e)}",
                "truncated": False,
            }
