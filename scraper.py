import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.glossier.com"

# Change this value to "IN" or "US".
LOCATION = "US"

if LOCATION == "IN":
    COLLECTION_URL = (
        "https://www.glossier.com/en-in/collections/all"
    )
    LOCALE = "en-IN"
    TIMEZONE = "Asia/Kolkata"
else:
    COLLECTION_URL = (
        "https://www.glossier.com/collections/all"
    )
    LOCALE = "en-US"
    TIMEZONE = "America/New_York"

OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(parents=True,exist_ok=True)


# =========================================================
# COMMON HELPERS
# =========================================================

def scraped_time():
    return datetime.now(timezone.utc).isoformat()


def clean_url(url):

    if not url:
        return ""

    return urljoin(BASE_URL, url)


# =========================================================
# SAVE ONE FINAL CSV
# =========================================================

def save_csv(rows):

    if not rows:
        print("No data found.")
        return

    if LOCATION == "IN":
        path = OUTPUT_DIR / "exercise1_products_india.csv"
    else:
        path = OUTPUT_DIR / "exercise1_products_us.csv"

    fieldnames = [
        "product_name",
        "product_id",
        "image",
        "url",
        "price",
        "scraped_at",
        "description",
        "variant_id",
        "variant_name",
        "variant_price"
    ]

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in rows:

            row = row.copy()

            # Image is an array of strings.
            # CSV stores the array as JSON text.
            if isinstance(row.get("image"), list):

                row["image"] = json.dumps(
                    row["image"]
                )

            writer.writerow(row)

    print(f"\nSaved: {path}")


# =========================================================
# GET PRODUCT LINKS
# =========================================================

def get_product_links(page):

    links = []

    for link in page.locator(
        'a[href*="/products/"]'
    ).all():

        href = link.get_attribute("href")

        if not href:
            continue

        full_url = clean_url(href)

        parsed = urlparse(full_url)

        # Only Glossier product pages
        if parsed.netloc != "www.glossier.com":
            continue

        if "/products/" not in parsed.path:
            continue

        # Remove query parameters
        product_url = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        )

        if product_url not in links:

            links.append(product_url)

    return links


# =========================================================
# TASK 1
# FIRST PAGE PRODUCTS
# =========================================================

def collect_first_page_products():

    print("\nTASK 1 - FIRST PAGE")

    print(
        f"Opening: {COLLECTION_URL}"
    )

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale=LOCALE,
            timezone_id=TIMEZONE
        )
        page = context.new_page()

        page.goto(
            COLLECTION_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        product_links = get_product_links(page)

        print(
            f"Products found on first page: "
            f"{len(product_links)}"
        )

        context.close()
        browser.close()

    products = []

    for product_url in product_links:

        try:

            product = get_product_json(
                product_url
            )

            row = product_to_row(
                product,
                product_url
            )

            products.append(row)

            print(
                f"Collected: "
                f"{row['product_name']}"
            )

        except Exception as error:

            print(
                f"Failed: "
                f"{product_url} - {error}"
            )

    return products


# =========================================================
# GET PRODUCT JSON
# =========================================================

def get_product_json(product_url):

    parsed = urlparse(product_url)

    path = parsed.path.rstrip("/")

    handle = path.split(
        "/products/"
    )[-1]

    parts = path.strip("/").split("/")

    locale = ""

    if parts[0] != "products":

        locale = "/" + parts[0]

    if locale:

        api_url = (
            f"{BASE_URL}"
            f"{locale}"
            f"/products/{handle}.js"
        )

    else:

        api_url = (
            f"{BASE_URL}"
            f"/products/{handle}.js"
        )

    response = requests.get(
        api_url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# CONVERT PRODUCT JSON
# =========================================================

def product_to_row(
    product,
    product_url
):

    images = []

    for image in product.get(
        "images",
        []
    ):

        if image:

            images.append(
                clean_url(image)
            )

    price = product.get("price")

    if isinstance(
        price,
        (int, float)
    ):

        price = f"{price / 100:.2f}"

    else:

        price = str(
            price or ""
        )

    return {

        "product_name": str(
            product.get(
                "title",
                ""
            )
        ),

        "product_id": str(
            product.get(
                "id",
                ""
            )
        ),

        "image": images,

        "url": product_url,

        "price": price,

        "scraped_at": scraped_time(),

        "description": "",

        "variant_id": "",

        "variant_name": "",

        "variant_price": ""
    }


# =========================================================
# TASK 2
# GET ALL PRODUCT LINKS
# =========================================================

def collect_all_product_links():

    print("\nTASK 2 - ALL PRODUCTS")

    all_links = []

    page_number = 1

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale=LOCALE,
            timezone_id=TIMEZONE
        )
        page = context.new_page()

        while True:

            if page_number == 1:

                url = COLLECTION_URL

            else:

                url = (
                    f"{COLLECTION_URL}"
                    f"?page={page_number}"
                )

            print(
                f"\nOpening collection page: "
                f"{url}"
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(3000)

            links = get_product_links(page)

            new_links = [
                link
                for link in links
                if link not in all_links
            ]

            print(
                f"Page {page_number}: "
                f"{len(new_links)} new products"
            )

            if not new_links:

                break

            all_links.extend(
                new_links
            )

            print(
                f"Total products so far: "
                f"{len(all_links)}"
            )

            page_number += 1

        context.close()
        browser.close()

    return all_links


# =========================================================
# GET ALL PRODUCT DATA
# =========================================================

def collect_products_from_links(
    product_links
):

    products = []

    for product_url in product_links:

        try:

            product = get_product_json(
                product_url
            )

            row = product_to_row(
                product,
                product_url
            )

            products.append(row)

            print(
                f"Collected: "
                f"{row['product_name']}"
            )

        except Exception as error:

            print(
                f"Failed: "
                f"{product_url} - {error}"
            )

    return products


# =========================================================
# TASK 3
# ADD DESCRIPTIONS
# =========================================================

def add_descriptions(
    all_products
):

    print(
        "\nTASK 3 - DESCRIPTIONS"
    )

    rows = []

    for product in all_products:

        try:

            data = get_product_json(
                product["url"]
            )

            description_html = data.get(
                "description",
                ""
            )

            soup = BeautifulSoup(
                description_html,
                "html.parser"
            )

            description = soup.get_text(
                " ",
                strip=True
            )

            row = product.copy()

            row["description"] = description

            rows.append(row)

            print(
                f"Description collected: "
                f"{product['product_name']}"
            )

        except Exception as error:

            print(
                f"Failed description: "
                f"{product['product_name']} "
                f"- {error}"
            )

    return rows


# =========================================================
# TASK 4
# ADD VARIANTS
# =========================================================

def add_variants(
    products
):

    print(
        "\nTASK 4 - VARIANTS"
    )

    rows = []

    for product in products:

        try:

            data = get_product_json(
                product["url"]
            )

            variants = data.get(
                "variants",
                []
            )

            # If product has no variants,
            # keep the product row.
            if not variants:

                rows.append(product)

                continue

            for variant in variants:

                row = product.copy()

                row["variant_id"] = str(
                    variant.get(
                        "id",
                        ""
                    )
                )

                row["variant_name"] = str(
                    variant.get(
                        "title",
                        ""
                    )
                )

                variant_price = variant.get(
                    "price"
                )

                if isinstance(
                    variant_price,
                    (int, float)
                ):

                    row["variant_price"] = (
                        f"{variant_price / 100:.2f}"
                    )

                else:

                    row["variant_price"] = str(
                        variant_price or ""
                    )

                rows.append(row)

                print(
                    f"Variant collected: "
                    f"{product['product_name']} - "
                    f"{row['variant_name']}"
                )

        except Exception as error:

            print(
                f"Failed variants: "
                f"{product['product_name']} - "
                f"{error}"
            )

    return rows



# =========================================================
# TASK 5
# LOCATION-BASED SCRAPING
# =========================================================

def run_selected_location():
    print("\nSELECTED LOCATION")
    print("=================")
    print(f"Location: {LOCATION}")
    print(f"Collection URL: {COLLECTION_URL}")

    # The same scraper is reused for either IN or US.
    product_links = collect_all_product_links()

    print(
        f"\nTotal unique {LOCATION} product links found: "
        f"{len(product_links)}"
    )

    products = collect_products_from_links(
        product_links
    )

    print(
        f"Products collected for {LOCATION}: "
        f"{len(products)}"
    )

    products_with_descriptions = add_descriptions(
        products
    )

    print(
        f"Products with descriptions for {LOCATION}: "
        f"{len(products_with_descriptions)}"
    )

    final_rows = add_variants(
        products_with_descriptions
    )

    print(
        f"Final {LOCATION} rows: "
        f"{len(final_rows)}"
    )

    save_csv(final_rows)

    return final_rows


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "Glossier Exercise 1 Scraper"
    )

    print(
        "============================"
    )

    print(
        f"Selected location: {LOCATION}"
    )

    # -----------------------------------------------------
    # TASK 1
    # First page
    # -----------------------------------------------------

    first_page_products = (
        collect_first_page_products()
    )

    print(
        f"\nTask 1 products: "
        f"{len(first_page_products)}"
    )

    # -----------------------------------------------------
    # TASK 2
    # All products
    # -----------------------------------------------------

    all_product_links = (
        collect_all_product_links()
    )

    print(
        f"\nTotal unique product links found: "
        f"{len(all_product_links)}"
    )

    all_products = (
        collect_products_from_links(
            all_product_links
        )
    )

    print(
        f"Task 2 products: "
        f"{len(all_products)}"
    )

    # -----------------------------------------------------
    # TASK 3
    # Descriptions
    # -----------------------------------------------------

    products_with_descriptions = (
        add_descriptions(
            all_products
        )
    )

    print(
        f"\nTask 3 products: "
        f"{len(products_with_descriptions)}"
    )

    # -----------------------------------------------------
    # TASK 4
    # Variants
    # -----------------------------------------------------

    final_rows = add_variants(
        products_with_descriptions
    )

    print(
        f"\nTask 4 rows: "
        f"{len(final_rows)}"
    )

    # -----------------------------------------------------
    # TASK 5
    # Location selection using if/else
    # -----------------------------------------------------

    run_selected_location()

    print(
        f"\nScraping completed for {LOCATION}."
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()