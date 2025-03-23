import requests
import re
import json
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)


def scrape_product(url, store=None):
    """
    Scrape product information from various e-commerce platforms.
    """
    # Determine store from URL if not provided
    if not store:
        domain = urlparse(url).netloc
        if "daraz" in domain:
            store = "daraz"
        elif "amazon" in domain:
            store = "amazon"
        elif "aliexpress" in domain:
            store = "aliexpress"
        elif "flipkart" in domain:
            store = "flipkart"
        else:
            store = "generic"

    logger.info(f"Scraping product from {store}: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes

        # Save raw HTML for debugging
        with open(f"{store}_raw.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        logger.info(f"Saved raw HTML for {store}")

        # Route to appropriate scraper based on store
        if store == "daraz":
            result = scrape_daraz(response)
        elif store == "amazon":
            result = scrape_amazon(response)
        elif store == "aliexpress":
            result = scrape_aliexpress(response)
        elif store == "flipkart":
            result = scrape_flipkart(response)
        else:
            result = scrape_generic(response)

        # Double-check if price is 0 and try generic method as fallback
        if result and result.get("price", 0) == 0:
            logger.warning(
                f"{store} scraper returned price 0.0, trying fallback extraction"
            )
            fallback_prices = extract_any_price(response.text)
            if fallback_prices:
                # Use median price if we have multiple
                fallback_prices.sort()
                if len(fallback_prices) > 2:
                    result["price"] = fallback_prices[
                        len(fallback_prices) // 2
                    ]  # median
                else:
                    result["price"] = fallback_prices[0]
                logger.info(f"Fallback price extraction found: {result['price']}")

        logger.info(f"Final scraped data: {result}")
        return result

    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}", exc_info=True)
        return None


def extract_price(price_str):
    """
    Helper function to safely extract price from string.
    """
    logger.info(
        f"Starting price extraction from: '{price_str}' (type: {type(price_str).__name__})"
    )

    if not price_str:
        logger.warning("Empty price string provided")
        return 0.0

    # Ensure price_str is a string
    price_str = str(price_str)

    # Print the raw string for debugging
    logger.info(f"Raw price string: '{price_str}'")

    # Remove currency symbols, commas, and other non-numeric characters except decimal point
    clean_price = re.sub(r"[^\d.]", "", price_str)
    logger.info(f"Cleaned price string: '{clean_price}'")

    # Check if we have a valid string
    if not clean_price:
        logger.warning(f"No numeric values found in: '{price_str}'")
        return 0.0

    # Check if there are multiple decimal points
    if clean_price.count(".") > 1:
        logger.warning(f"Multiple decimal points found: '{clean_price}'")
        # Keep only the first decimal point
        parts = clean_price.split(".")
        clean_price = parts[0] + "." + "".join(parts[1:])
        logger.info(f"Fixed decimal points: '{clean_price}'")

    try:
        price = float(clean_price)
        logger.info(f"Successfully extracted price: {price}")
        return price
    except (ValueError, TypeError) as e:
        logger.error(
            f"Failed to convert price: '{price_str}' -> '{clean_price}', Error: {str(e)}"
        )
        return 0.0


def extract_any_price(html_content):
    """
    Extract any price-like patterns from HTML content.
    """
    # Common price patterns for different currencies
    patterns = [
        # Existing patterns...
        r'data-price="([0-9,]+(?:\.[0-9]{1,2})?)"',  # data-price attribute
        r'price"?\s*:\s*"?([0-9,]+(?:\.[0-9]{1,2})?)"?',  # price in JSON
        r'value"?\s*:\s*"?([0-9,]+(?:\.[0-9]{1,2})?)"?',  # value in JSON
        r"Rs\.\s*([0-9,]+(?:\.[0-9]{1,2})?)",  # Rs. format
        r"Rs\s*([0-9,]+(?:\.[0-9]{1,2})?)",  # Rs format without dot
    ]

    found_prices = []
    for pattern in patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for match in matches:
            try:
                clean_match = re.sub(r"[,]", "", match)
                price = float(clean_match)
                found_prices.append(price)
            except (ValueError, TypeError):
                continue

    logger.info(f"Found potential prices: {found_prices}")
    return found_prices


def scrape_daraz(response):
    """
    Scrape Daraz product page.
    """
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        # Debug: Save HTML to analyze
        with open("daraz_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)

        # Set default values
        title = ""
        price = 0.0
        image_url = ""
        description = ""

        # Try script-based parsing first - look for the data-module="item-price" attribute
        price_data_script = soup.find("script", attrs={"data-module": "item-price"})
        if price_data_script:
            try:
                script_text = price_data_script.string
                if script_text:
                    match = re.search(
                        r"data:\s*({.+?}),\s*exports:", script_text, re.DOTALL
                    )
                    if match:
                        price_data = json.loads(match.group(1))
                        if price_data and "price" in price_data:
                            price_str = str(price_data.get("price", "0"))
                            price = extract_price(price_str)
                            logger.info(f"Found price from data-module script: {price}")
                            if price > 0:
                                # Continue with other data extraction
                                # Ensure we have a title
                                title_elem = soup.find(
                                    "h1", class_="pdp-mod-product-badge-title"
                                )
                                if not title_elem:
                                    title_elem = soup.find("span", class_="pdp-title")
                                if title_elem:
                                    title = title_elem.text.strip()

                                # Extract image URL and description as in original code
                                image_elem = soup.find(
                                    "img", class_="pdp-mod-common-image"
                                )
                                if not image_elem:
                                    image_elem = soup.find(
                                        "img", attrs={"data-src": True}
                                    )
                                image_url = (
                                    image_elem.get("src") or image_elem.get("data-src")
                                    if image_elem
                                    else ""
                                )

                                desc_elem = soup.find("div", class_="html-content")
                                if not desc_elem:
                                    desc_elem = soup.find(
                                        "div", class_="pdp-product-detail"
                                    )
                                description = (
                                    desc_elem.text.strip() if desc_elem else ""
                                )

                                return {
                                    "title": title,
                                    "price": price,
                                    "image_url": image_url,
                                    "description": description,
                                }
            except Exception as e:
                logger.error(f"Error parsing price data-module script: {str(e)}")

        # Try the app.run approach as before
        scripts = soup.find_all("script", type="text/javascript")
        for script in scripts:
            script_text = script.string
            if script_text and "app.run" in script_text:
                match = re.search(r"app\.run\((.*?)\);", script_text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        product_data = (
                            data.get("data", {}).get("root", {}).get("fields", {})
                        )
                        if product_data:
                            title = product_data.get("title", "")
                            price_info = product_data.get("price", {})
                            if isinstance(price_info, dict):
                                # Try to get the actual price value rather than display text
                                price_str = str(
                                    price_info.get("value", price_info.get("text", "0"))
                                )
                            else:
                                price_str = str(price_info)

                            logger.info(f"Found price from app.run: {price_str}")
                            price = extract_price(price_str)
                            images = product_data.get("images", [])
                            image_url = images[0] if images else ""
                            description = product_data.get("description", "")

                            # If price was successfully extracted, return immediately
                            if price > 0:
                                return {
                                    "title": title,
                                    "price": price,
                                    "image_url": image_url,
                                    "description": description,
                                }
                    except Exception as e:
                        logger.error(f"Daraz JSON parse error: {str(e)}")

        # HTML fallback parsing - improved to find more price elements
        logger.info(
            "JSON extraction failed or returned 0 price, trying HTML extraction"
        )

        # Try to find the title first
        title_elem = soup.find("h1", class_="pdp-mod-product-badge-title")
        if not title_elem:
            title_elem = soup.find("span", class_="pdp-title")
        if title_elem:
            title = title_elem.text.strip()
            logger.info(f"Found title: {title}")

        # Enhanced price element search - try multiple class patterns
        price_candidates = [
            # First try the price with 'color_orange' class which usually indicates the current price
            soup.find(
                "span", class_=lambda x: x and "color_orange" in x and "pdp-price" in x
            ),
            soup.find("span", class_="pdp-price_type_normal pdp-price_color_orange"),
            # Then try the general selectors
            soup.find("span", class_="pdp-price_type_normal"),
            soup.find("span", class_=lambda x: x and "pdp-price_type_normal" in x),
            soup.find("span", class_=lambda x: x and "pdp-price" in x),
            soup.find("div", class_=lambda x: x and "pdp-price" in x),
            soup.find("span", class_="price-val"),
            # Try the special price if it exists (but this is usually the crossed-out price)
            soup.find("span", class_="pdp-price_type_deleted"),
        ]

        for price_elem in price_candidates:
            if price_elem:
                price_str = price_elem.text.strip()
                logger.info(f"Found price element text: '{price_str}'")
                # Remove 'Rs.' and any commas
                price_str = price_str.replace("Rs.", "").replace(",", "").strip()
                try:
                    price = float(price_str)
                    logger.info(f"Successfully converted Daraz price to float: {price}")
                    if price > 0:
                        break
                except ValueError as e:
                    logger.error(
                        f"Failed to convert price string '{price_str}' to float: {str(e)}"
                    )

        # Add a specific check for the price container which often has multiple elements
        if price == 0.0:
            price_container = soup.find("div", class_="pdp-product-price")
            if price_container:
                # Try to find the most prominent price in the container
                price_spans = price_container.find_all("span")
                for span in price_spans:
                    span_text = span.text.strip()
                    if "Rs." in span_text or "₹" in span_text:
                        price_str = (
                            span_text.replace("Rs.", "")
                            .replace("₹", "")
                            .replace(",", "")
                            .strip()
                        )
                        try:
                            price = float(price_str)
                            logger.info(f"Found price from price container: {price}")
                            if price > 0:
                                break
                        except ValueError:
                            continue

        # Extract image URL
        image_elem = soup.find("img", class_="pdp-mod-common-image")
        if not image_elem:
            image_elem = soup.find("img", attrs={"data-src": True})
        image_url = (
            image_elem.get("src") or image_elem.get("data-src") if image_elem else ""
        )

        # Extract description
        desc_elem = soup.find("div", class_="html-content")
        if not desc_elem:
            desc_elem = soup.find("div", class_="pdp-product-detail")
        description = desc_elem.text.strip() if desc_elem else ""

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "description": description,
        }

    except Exception as e:
        logger.error(f"Daraz parsing failed: {str(e)}", exc_info=True)
        return None


def scrape_amazon(response):
    """Scrape Amazon product page"""
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        title_elem = soup.find("span", id="productTitle")
        title = title_elem.text.strip() if title_elem else ""

        # Try different price elements
        price_elem = soup.find("span", class_="a-price-whole")
        price_fraction = soup.find("span", class_="a-price-fraction")

        price = 0.0
        if price_elem:
            price_str = price_elem.text.strip().replace(",", "")
            fraction = price_fraction.text.strip() if price_fraction else "00"
            price_str = f"{price_str}.{fraction}"
            logger.info(f"Amazon price string: '{price_str}'")
            price = extract_price(price_str)

        if price == 0.0:
            # Try alternative price elements
            for price_class in [
                "priceblock_ourprice",
                "priceblock_dealprice",
                "a-offscreen",
            ]:
                alt_price = soup.find("span", id=price_class) or soup.find(
                    "span", class_=price_class
                )
                if alt_price:
                    price_str = alt_price.text.strip()
                    logger.info(f"Alternative Amazon price string: '{price_str}'")
                    price = extract_price(price_str)
                    if price > 0:
                        break

            # If still zero, try the deal price
            if price == 0.0:
                deal_price = soup.find("span", id="priceblock_saleprice")
                if deal_price:
                    price_str = deal_price.text.strip()
                    logger.info(f"Amazon deal price string: '{price_str}'")
                    price = extract_price(price_str)

        image_elem = soup.find("img", id="landingImage")
        if not image_elem:
            image_elem = soup.find("img", id="imgBlkFront")
        image_url = image_elem.get("src") if image_elem else ""

        description_elem = soup.find("div", id="productDescription")
        description = description_elem.text.strip() if description_elem else ""

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "description": description,
        }
    except Exception as e:
        logger.error(f"Error parsing Amazon HTML: {str(e)}", exc_info=True)
        return None


def scrape_flipkart(response):
    """Scrape Flipkart product page"""
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        title_elem = soup.find("span", class_="B_NuCI")
        title = title_elem.text.strip() if title_elem else ""

        price_elem = soup.find("div", class_="_30jeq3 _16Jk6d")
        price = 0.0
        if price_elem:
            price_str = price_elem.text.strip()
            logger.info(f"Flipkart price string: '{price_str}'")
            price = extract_price(price_str)

        # Try alternative price selector if the first one fails
        if price == 0.0:
            alt_price_elem = soup.find("div", class_=lambda x: x and "_30jeq3" in x)
            if alt_price_elem:
                price_str = alt_price_elem.text.strip()
                logger.info(f"Alternative Flipkart price string: '{price_str}'")
                price = extract_price(price_str)

        image_elem = soup.find("img", class_="_396cs4")
        image_url = image_elem.get("src") if image_elem else ""

        description_elem = soup.find("div", class_="_1mXcCf RmoJUa")
        description = description_elem.text.strip() if description_elem else ""

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "description": description,
        }
    except Exception as e:
        logger.error(f"Error parsing Flipkart HTML: {str(e)}", exc_info=True)
        return None


def scrape_aliexpress(response):
    """Scrape AliExpress product page"""
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        # Try to extract structured data
        structured_data = None
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and "offers" in data:
                    structured_data = data
                    break
            except (json.JSONDecodeError, AttributeError):
                continue

        # Extract from structured data if available
        if structured_data:
            title = structured_data.get("name", "")
            if "offers" in structured_data:
                offers = structured_data["offers"]
                if isinstance(offers, dict):
                    price_str = offers.get("price", "0")
                    logger.info(f"AliExpress structured data price: '{price_str}'")
                    price = extract_price(price_str)
                elif isinstance(offers, list) and offers:
                    price_str = offers[0].get("price", "0")
                    logger.info(
                        f"AliExpress structured data price (from list): '{price_str}'"
                    )
                    price = extract_price(price_str)
                else:
                    price = 0.0
            else:
                price = 0.0

            image_url = structured_data.get("image", "")
            description = structured_data.get("description", "")

            if price > 0:
                return {
                    "title": title,
                    "price": price,
                    "image_url": image_url,
                    "description": description,
                }

        # Try to get product data from script tags
        scripts = soup.find_all("script", type="text/javascript")
        for script in scripts:
            script_text = script.string
            if script_text and "window.runParams" in script_text:
                match = re.search(
                    r"window\.runParams\s*=\s*({.*?});\s*window\.runParams",
                    script_text,
                    re.DOTALL,
                )
                if match:
                    try:
                        data = json.loads(match.group(1))
                        product_data = (
                            data.get("data", {}).get("root", {}).get("fields", {})
                        )

                        if product_data:
                            title = product_data.get("title", "")
                            price_str = product_data.get("formatedPrice", "")
                            logger.info(f"AliExpress script price: '{price_str}'")
                            price = extract_price(price_str)
                            image_url = product_data.get("imageUrl", "")
                            description = product_data.get("description", "")

                            return {
                                "title": title,
                                "price": price,
                                "image_url": image_url,
                                "description": description,
                            }
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.error(f"Error parsing AliExpress JSON: {str(e)}")

        # Fallback to HTML parsing
        title_elem = soup.find("h1", class_="product-title-text")
        if not title_elem:
            title_elem = soup.find("h1")
        title = title_elem.text.strip() if title_elem else ""

        price_elem = soup.find("span", class_="product-price-value")
        price = 0.0
        if price_elem:
            price_str = price_elem.text.strip()
            logger.info(f"AliExpress HTML price: '{price_str}'")
            price = extract_price(price_str)

        # Try alternative price elements
        if price == 0.0:
            price_candidates = [
                soup.find(
                    "span", class_=lambda x: x and "price" in x.lower() if x else False
                ),
                soup.find(
                    "div", class_=lambda x: x and "price" in x.lower() if x else False
                ),
            ]

            for candidate in price_candidates:
                if candidate:
                    price_str = candidate.text.strip()
                    logger.info(f"Alternative AliExpress price: '{price_str}'")
                    price = extract_price(price_str)
                    if price > 0:
                        break

        image_elem = soup.find("img", class_="magnifier-image")
        image_url = image_elem.get("src") if image_elem else ""

        description_elem = soup.find("div", class_="product-description")
        description = description_elem.text.strip() if description_elem else ""

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "description": description,
        }
    except Exception as e:
        logger.error(f"Error parsing AliExpress HTML: {str(e)}", exc_info=True)
        return None


def scrape_generic(response):
    """Generic scraper for unknown sites - tries common patterns"""
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        # Check for structured data first (best source if available)
        structured_data = None
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and ("offers" in data or "price" in data):
                    structured_data = data
                    break
            except (json.JSONDecodeError, AttributeError):
                continue

        if structured_data:
            # Extract from structured data
            if "name" in structured_data:
                title = structured_data["name"]
            else:
                title = ""

            price = 0.0
            if "offers" in structured_data:
                offers = structured_data["offers"]
                if isinstance(offers, dict):
                    price_str = offers.get("price", "0")
                    logger.info(f"Structured data price: '{price_str}'")
                    price = extract_price(price_str)
                elif isinstance(offers, list) and offers:
                    price_str = offers[0].get("price", "0")
                    logger.info(f"Structured data price from list: '{price_str}'")
                    price = extract_price(price_str)
            elif "price" in structured_data:
                price_str = structured_data["price"]
                logger.info(f"Direct structured data price: '{price_str}'")
                price = extract_price(price_str)

            image_url = structured_data.get("image", "")
            description = structured_data.get("description", "")

            if price > 0:
                return {
                    "title": title,
                    "price": price,
                    "image_url": image_url,
                    "description": description,
                }

        # Try to find title if not found in structured data
        title = ""
        title_candidates = [
            soup.find("h1"),
            soup.find(
                "h1", class_=lambda x: x and "title" in x.lower() if x else False
            ),
            soup.find(
                "div", class_=lambda x: x and "title" in x.lower() if x else False
            ),
            soup.find(
                "span", class_=lambda x: x and "title" in x.lower() if x else False
            ),
        ]

        for candidate in title_candidates:
            if candidate and candidate.text.strip():
                title = candidate.text.strip()
                break

        # Try to find price
        price = 0.0
        price_pattern = re.compile(
            r"(?:[$₹£€¥]|Rs\.?|USD|INR)\s*([0-9,]+(?:\.[0-9]{1,2})?)", re.IGNORECASE
        )
        price_text = None

        # Look for elements with price-related classes
        price_candidates = [
            soup.find(
                "span", class_=lambda x: x and "price" in x.lower() if x else False
            ),
            soup.find(
                "div", class_=lambda x: x and "price" in x.lower() if x else False
            ),
            soup.find("p", class_=lambda x: x and "price" in x.lower() if x else False),
            soup.find(
                "span", class_=lambda x: x and "amount" in x.lower() if x else False
            ),
            soup.find(
                "span", class_=lambda x: x and "current" in x.lower() if x else False
            ),
        ]

        for candidate in price_candidates:
            if candidate and candidate.text.strip():
                price_text = candidate.text.strip()
                logger.info(f"Found price text: '{price_text}'")
                if price_pattern.search(price_text):
                    match = price_pattern.search(price_text)
                    price_str = match.group(1)
                    price = extract_price(price_str)
                    if price > 0:
                        break
                else:
                    # Try direct conversion if no currency symbol
                    try:
                        clean_text = re.sub(r"[^\d.]", "", price_text)
                        if clean_text:
                            price = float(clean_text)
                            if price > 0:
                                break
                    except ValueError:
                        pass

        # If we still don't have a price, try a broader search
        if price == 0.0:
            # Look for any element containing currency symbols
            currency_elements = soup.find_all(
                string=re.compile(r"[$₹£€¥]|Rs\.?|USD|INR")
            )
            for elem in currency_elements:
                price_match = price_pattern.search(elem)
                if price_match:
                    price_str = price_match.group(1)
                    logger.info(f"Currency regex found price: '{price_str}'")
                    price = extract_price(price_str)
                    if price > 0:
                        break

        # Try meta tags as a last resort
        if price == 0.0:
            meta_price = soup.find(
                "meta", property="product:price:amount"
            ) or soup.find("meta", itemprop="price")
            if meta_price and meta_price.get("content"):
                price_str = meta_price.get("content", "0")
                logger.info(f"Meta tag price: '{price_str}'")
                price = extract_price(price_str)

        # Try to find image
        image_url = ""
        image_candidates = [
            soup.find(
                "img",
                class_=lambda x: (
                    x and ("product" in x.lower() or "main" in x.lower())
                    if x
                    else False
                ),
            ),
            soup.find(
                "img",
                id=lambda x: (
                    x and ("product" in x.lower() or "main" in x.lower())
                    if x
                    else False
                ),
            ),
            soup.find(
                "div",
                class_=lambda x: x and "product-image" in x.lower() if x else False,
            ),
        ]

        for candidate in image_candidates:
            if candidate:
                if candidate.name == "img" and candidate.get("src"):
                    image_url = candidate.get("src")
                    break
                elif candidate.find("img"):
                    img = candidate.find("img")
                    if img.get("src"):
                        image_url = img.get("src")
                        break

        # If still no image, try meta tags
        if not image_url:
            meta_image = soup.find("meta", property="og:image") or soup.find(
                "meta", itemprop="image"
            )
            if meta_image and meta_image.get("content"):
                image_url = meta_image.get("content", "")

        # Try to find description
        description = ""
        description_candidates = [
            soup.find(
                "div", class_=lambda x: x and "description" in x.lower() if x else False
            ),
            soup.find(
                "div", id=lambda x: x and "description" in x.lower() if x else False
            ),
            soup.find(
                "p", class_=lambda x: x and "description" in x.lower() if x else False
            ),
        ]

        for candidate in description_candidates:
            if candidate and candidate.text.strip():
                description = candidate.text.strip()
                break

        # Try meta description if no detailed description found
        if not description:
            meta_desc = soup.find("meta", property="og:description") or soup.find(
                "meta", name="description"
            )
            if meta_desc and meta_desc.get("content"):
                description = meta_desc.get("content", "")

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "description": description,
        }
    except Exception as e:
        logger.error(f"Error parsing generic HTML: {str(e)}", exc_info=True)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_url = "https://www.daraz.com.np/products/airpods-true-wirelees-bluetooth-super-sound-premium-quality-i290709810-s1342209012.html?scm=1007.51610.379274.0&pvid=ac7b5362-7946-4261-9ea6-719932e2975b&search=flashsale&spm=a2a0e.tm80335409.FlashSale.d_290709810"
    result = scrape_product(test_url)

    if result:
        print("Title:", result["title"])
        print("Price:", result["price"])
        print("Image URL:", result["image_url"])
        print(
            "Description:",
            result["description"][:100] + "..." if result["description"] else "",
        )
    else:
        print("Failed to scrape product information")
