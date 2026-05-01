#!/usr/bin/env python3
"""
SpendMoat SaaS Data Scraper
Scans NachoNacho.com weekly and extracts tool catalog to JSON.
"""

import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://nachonacho.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
OUTPUT_FILE = "data/saas-data.json"
REQUEST_DELAY = 1.5  # Seconds between requests (be polite)


def fetch_sitemap():
    """Fetch and parse the sitemap XML to get all product URLs."""
    print(f"Fetching sitemap: {SITEMAP_URL}")
    response = requests.get(SITEMAP_URL, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, "xml")
    urls = []
    
    for loc in soup.find_all("loc"):
        url = loc.get_text(strip=True)
        if "/product/" in url:
            urls.append(url)
    
    print(f"Found {len(urls)} product URLs")
    return urls


def extract_tool_data(product_url):
    """Visit a product page and extract tool metadata."""
    try:
        response = requests.get(product_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Tool name: usually in <h1> or meta title
        name = ""
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
        else:
            title = soup.find("title")
            if title:
                name = title.get_text(strip=True).split(" - ")[0].split(" | ")[0]
        
        # Clean up name (remove deal prefixes)
        name = re.sub(r'^(deal-|Deal-)', '', name, flags=re.IGNORECASE).strip()
        
        # Categories: from breadcrumb or meta
        categories = []
        breadcrumbs = soup.find_all("a", href=re.compile(r'/category/'))
        for crumb in breadcrumbs:
            cat_text = crumb.get_text(strip=True)
            if cat_text and cat_text not in categories:
                categories.append(cat_text)
        
        # If no breadcrumbs, try to infer from URL patterns
        if not categories:
            url_lower = product_url.lower()
            category_map = {
                'crm': 'CRM',
                'marketing': 'Marketing',
                'accounting': 'Accounting & Finance',
                'productivity': 'Productivity',
                'project-management': 'Project Management',
                'communication': 'Communication',
                'security': 'Security',
                'design': 'Design',
                'dev-tools': 'Development',
                'ecommerce': 'E-commerce',
                'hr-recruiting': 'HR & Recruiting',
                'ai-': 'AI & Automation',
                'analytics': 'Analytics',
                'legal': 'Legal & Compliance',
            }
            for key, cat in category_map.items():
                if key in url_lower:
                    categories.append(cat)
                    break
        
        # Description: meta description or first paragraph
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "").strip()
        else:
            first_p = soup.find("p")
            if first_p:
                description = first_p.get_text(strip=True)[:200]
        
        # Pricing: look for price patterns in page text
        pricing_text = soup.get_text()
        price_match = re.search(r'From\s+\$([\d,]+)(?:/mo)?', pricing_text, re.IGNORECASE)
        pricing_from = f"${price_match.group(1)}" if price_match else "Contact for pricing"
        
        # Determine pricing tier
        tier = "enterprise"
        if "free" in pricing_text.lower() or price_match and int(price_match.group(1).replace(',', '')) == 0:
            tier = "free"
        elif price_match and int(price_match.group(1).replace(',', '')) < 50:
            tier = "budget"
        elif price_match and int(price_match.group(1).replace(',', '')) < 200:
            tier = "standard"
        
        # Team size inference from pricing tier
        team_sizes = {
            "free": ["solo", "2-10"],
            "budget": ["solo", "2-10", "11-50"],
            "standard": ["2-10", "11-50", "51-200"],
            "enterprise": ["11-50", "51-200", "200+"]
        }
        
        # Logo: look for og:image or first product image
        logo = ""
        og_image = soup.find("meta", property="og:image")
        if og_image:
            logo = og_image.get("content", "")
        
        # Tool ID from URL slug
        tool_id = product_url.rstrip("/").split("/")[-1].lower()
        
        return {
            "id": tool_id,
            "name": name,
            "categories": categories if categories else ["Uncategorized"],
            "pricing": {
                "from": pricing_from,
                "tier": tier
            },
            "team_size": team_sizes.get(tier, ["2-10", "11-50"]),
            "description": description[:250],
            "nachonacho_url": product_url,
            "logo": logo
        }
        
    except Exception as e:
        print(f"  ✗ Failed: {product_url} — {e}")
        return None


def main():
    """Main execution."""
    print(f"\n{'='*60}")
    print(f"SpendMoat SaaS Scraper — {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    # Fetch all product URLs
    product_urls = fetch_sitemap()
    
    if not product_urls:
        print("No product URLs found. Exiting.")
        return
    
    # Scrape each product
    tools = []
    for i, url in enumerate(product_urls, 1):
        print(f"[{i}/{len(product_urls)}] Scraping: {url}")
        data = extract_tool_data(url)
        if data:
            tools.append(data)
            print(f"  ✓ {data['name']} ({', '.join(data['categories'])})")
        time.sleep(REQUEST_DELAY)
    
    # Build output
    output = {
        "last_updated": datetime.now().isoformat(),
        "total_tools": len(tools),
        "source": "nachonacho.com",
        "tools": tools
    }
    
    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"Done. Saved {len(tools)} tools to {OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()